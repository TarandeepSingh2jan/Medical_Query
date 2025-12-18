import os
import logging
from flask import Flask, render_template, request, jsonify
from neo4j import GraphDatabase
from dotenv import load_dotenv
import requests
import spacy

# ---------------------------------------------------------
# Logging & Environment Setup
# ---------------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)

# Environment variables
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = "x-ai/grok-4.1-fast"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


# ---------------------------------------------------------
# Neo4j Driver
# ---------------------------------------------------------

class Neo4jDriver:
    def __init__(self, uri, user, password):
        try:
            logger.info(f"Connecting to Neo4j with URI: {uri}, User: {user}")
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
        except Exception as e:
            logger.error(f"Neo4j connection error: {str(e)}")
            raise

    def close(self):
        if hasattr(self, "driver"):
            self.driver.close()

    def run_query(self, query, parameters=None):
        try:
            with self.driver.session() as session:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
        except Exception as e:
            logger.error(f"Neo4j query issue: {str(e)}")
            return None


# ---------------------------------------------------------
# NLP Processor
# ---------------------------------------------------------

class NLPProcessor:
    def __init__(self, neo4j_driver: Neo4jDriver):
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.error("Run: python -m spacy download en_core_web_sm")
            raise

        self.neo4j = neo4j_driver
        disease_records = self.neo4j.run_query("MATCH (d:Disease) RETURN d.name") or []
        symptom_records = self.neo4j.run_query("MATCH (s:Symptom) RETURN s.name") or []

        self.diseases = [rec["d.name"] for rec in disease_records]
        self.symptoms = [rec["s.name"] for rec in symptom_records]

        logger.info(f"NLP cache loaded: {len(self.diseases)} diseases, {len(self.symptoms)} symptoms.")

        self.intent_keywords = {
            "symptoms": ["symptom", "symptoms", "signs", "indications"],
            "precautions": ["prevent", "precaution", "precautions", "avoid", "protection", "how to avoid"],
            "diseases": ["disease", "diseases", "condition", "illness", "what causes"],
        }

    def detect_intent(self, text: str) -> str:
        t = text.lower()
        for intent, words in self.intent_keywords.items():
            if any(w in t for w in words):
                return intent
        return "general"

    def extract_keywords(self, text: str):
        text_lower = text.lower()
        diseases = [d for d in self.diseases if d.lower() in text_lower or text_lower in d.lower()]
        return list(set(diseases)) or [text.split()[-1]]  # fallback to last word


# ---------------------------------------------------------
# RAG System 
# ---------------------------------------------------------

class RAGSystem:
    def __init__(self, neo4j_uri, neo4j_user, neo4j_password, openrouter_api_key):
        self.neo4j = Neo4jDriver(neo4j_uri, neo4j_user, neo4j_password)
        self.nlp = NLPProcessor(self.neo4j)


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
                OPENROUTER_URL,
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
                json={"model": OPENROUTER_MODEL, "messages": messages},
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


# ---------------------------------------------------------
# App Init & Routes
# ---------------------------------------------------------

try:
    rag_system = RAGSystem(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, OPENROUTER_API_KEY)
except Exception as e:
    logger.error(f"Init failed: {e}")
    rag_system = None


@app.route("/")
def index():
    return render_template("index.html") if rag_system else "System error", 500


@app.route("/query", methods=["POST"])
def query():
    if not rag_system:
        return jsonify({"warning": "System not ready"}), 500
    user_query = request.get_json().get("query", "").strip()
    if not user_query:
        return jsonify({"warning": "Empty query"}), 400
    return jsonify(rag_system.process_query(user_query))


# Clean shutdown
import atexit
atexit.register(lambda: rag_system.neo4j.close() if rag_system else None)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=False)