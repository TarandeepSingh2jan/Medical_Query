import os
import logging
import requests
from .neo4j_driver import Neo4jDriver
from .nlp_processor import NLPProcessor

logger = logging.getLogger(__name__)

class RAGSystem:
    def __init__(self, neo4j_uri, neo4j_user, neo4j_password, openrouter_api_key):
        self.neo4j = Neo4jDriver(neo4j_uri, neo4j_user, neo4j_password)
        self.nlp = NLPProcessor(self.neo4j)
        self.openrouter_api_key = openrouter_api_key
        self.openrouter_model = "x-ai/grok-4.1-fast"
        self.openrouter_url = "https://openrouter.ai/api/v1/chat/completions"

        self.schema = """
        Node labels: Disease, Symptom, Precaution
        Relationships:
          (Symptom)-[:HAS_SYMPTOM]->(Disease)
          (Disease)-[:HAS_PRECAUTION]->(Precaution)
        Properties: name (string)
        """

    def _call_openrouter(self, messages):
        try:
            response = requests.post(
                self.openrouter_url,
                headers={"Authorization": f"Bearer {self.openrouter_api_key}", "Content-Type": "application/json"},
                json={"model": self.openrouter_model, "messages": messages},
                timeout=20
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"LLM Error: {e}")
            return None

    def generate_cypher(self, user_query):
        messages = [
            {"role": "system", "content": "You are a Cypher expert. Always use toLower() and CONTAINS for flexible matching. Never use exact {name: '...'} unless 100% sure."},
            {"role": "user", "content": f"""
            Schema: {self.schema}
            User query: "{user_query}"
            Generate a Cypher query that finds relevant diseases/precautions using case-insensitive partial matching.
            Example: Use 'toLower(d.name) CONTAINS "fungal"' instead of exact match.
            Return ONLY the Cypher query.
            """}
        ]
        cypher = self._call_openrouter(messages)

        if cypher and "MATCH" in cypher.upper():
            return cypher.strip("` \n"), {}

        intent = self.nlp.detect_intent(user_query)
        keywords = self.nlp.extract_keywords(user_query)
        keyword = keywords[0].lower().replace("infections", "infection").replace("infection", "infection")

        if intent == "precautions":
            query = f"""
                MATCH (d:Disease)-[:HAS_PRECAUTION]->(p:Precaution)
                WHERE toLower(d.name) CONTAINS '{keyword}'
                RETURN d.name AS Disease, COLLECT(DISTINCT p.name) AS Precautions
                LIMIT 5
            """
        elif intent == "symptoms":
            query = f"""
                MATCH (s:Symptom)-[:HAS_SYMPTOM]->(d:Disease)
                WHERE toLower(d.name) CONTAINS '{keyword}'
                RETURN d.name AS Disease, COLLECT(DISTINCT s.name) AS Symptoms
                LIMIT 5
            """
        else:
            query = f"""
                MATCH (d:Disease)
                WHERE toLower(d.name) CONTAINS '{keyword}'
                OPTIONAL MATCH (d)-[:HAS_PRECAUTION]->(p:Precaution)
                OPTIONAL MATCH (s:Symptom)-[:HAS_SYMPTOM]->(d)
                RETURN d.name AS Disease, 
                       COLLECT(DISTINCT p.name) AS Precautions,
                       COLLECT(DISTINCT s.name) AS Symptoms
                LIMIT 5
            """
        return query, {}

    def format_prompt(self, data, query):
        if not data:
            return "No information found. Try rephrasing your question or consult a doctor."

        data_str = "\n".join([str(r) for r in data])
        return f"""
        Data: {data_str}

        Answer the user's question: "{query}"
        Use simple language and bullet points.
        End with: "This is for educational purposes only. Consult a doctor for medical advice."
        """

    def call_llm(self, prompt):
        messages = [
            {"role": "system", "content": "You are a helpful medical assistant. Be accurate and safe."},
            {"role": "user", "content": prompt}
        ]
        return self._call_openrouter(messages) or "Sorry, I couldn't generate a response."

    def process_query(self, user_query):
        cypher, params = self.generate_cypher(user_query)
        logger.info(f"Cypher: {cypher}")

        data = self.neo4j.run_query(cypher, params)
        if not data:
            fallback = self.neo4j.run_query("MATCH (d:Disease) RETURN d.name AS Disease LIMIT 10")
            names = [r["Disease"] for r in fallback] if fallback else []
            return {"warning": f"No info found for '{user_query}'. Try: {', '.join(names[:5])}"}

        prompt = self.format_prompt(data, user_query)
        answer = self.call_llm(prompt)

        return {"response": answer, "data": data}
