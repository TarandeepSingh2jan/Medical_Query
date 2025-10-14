import os
import re
import logging
import time
from flask import Flask, render_template, request, jsonify
from neo4j import GraphDatabase
from openai import OpenAI
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Environment variables
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = "openai/gpt-oss-20b:free"

# Initialize OpenAI client
try:
    openai_client = OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1"
    )
    logger.info("OpenAI client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {str(e)}")
    openai_client = None

class Neo4jDriver:
    def __init__(self, uri, user, password):
        try:
            logger.info(f"Connecting to Neo4j with URI: {uri}, User: {user}")
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
        except Exception as e:
            logger.error(f"Neo4j connection error: {str(e)}")
            raise Exception(f"Neo4j connection error: {str(e)}")
        
    def close(self):
        if hasattr(self, 'driver'):
            self.driver.close()
            
    def run_query(self, query, parameters=None):
        try:
            with self.driver.session() as session:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
        except Exception as e:
            logger.error(f"Neo4j query issue: {str(e)}")
            return None

class RAGSystem:
    def __init__(self, neo4j_uri, neo4j_user, neo4j_password, openrouter_api_key):
        self.neo4j = Neo4jDriver(neo4j_uri, neo4j_user, neo4j_password)
        self.schema = """
        Node Labels: Disease, Symptom, Precaution
        Relationships: 
        - (Symptom)-[:HAS_SYMPTOM]->(Disease)
        - (Disease)-[:HAS_PRECAUTION]->(Precaution)
        Properties:
        - Disease: name (string)
        - Symptom: name (string)
        - Precaution: name (string)
        """
    
    def generate_cypher(self, user_query):
        prompt = f"""
        Generate only a Cypher query based on the schema and user query.
        Return only the query enclosed in triple backticks.
        Schema: {self.schema}
        User Query: {user_query}
        """
        try:
            response = openai_client.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=[
                    {"role": "system", "content": "Generate only Cypher queries strictly."},
                    {"role": "user", "content": prompt}
                ],
            )
            full_response = response.choices[0].message.content
            start = full_response.find("```")
            end = full_response.rfind("```")
            if start == -1 or end == -1 or start == end:
                return self.fallback_cypher(user_query)
            query = full_response[start + 3:end].strip()
            if not query.upper().startswith("MATCH"):
                return self.fallback_cypher(user_query)
            return query, {}
        except Exception as e:
            logger.error(f"LLM error: {str(e)}")
            return self.fallback_cypher(user_query)

    def fallback_cypher(self, user_query):
        intent, entities = self.parse_query_intent(user_query)
        if not isinstance(entities, list):
            entities = [entities]
        if intent == "symptoms":
            return (
                f"""
                MATCH (s:Symptom)-[:HAS_SYMPTOM]->(d:Disease)
                WHERE toLower(d.name) CONTAINS '{entities[0]}'
                RETURN d.name AS Disease, COLLECT(DISTINCT s.name) AS Symptoms
                """, {}
            )
        elif intent == "precautions":
            return (
                f"""
                MATCH (d:Disease)-[:HAS_PRECAUTION]->(p:Precaution)
                WHERE toLower(d.name) CONTAINS '{entities[0]}'
                RETURN d.name AS Disease, COLLECT(DISTINCT p.name) AS Precautions
                """, {}
            )
        elif intent == "diseases":
            ents = "', '".join(entities)
            return (
                f"""
                MATCH (s:Symptom)-[:HAS_SYMPTOM]->(d:Disease)
                WHERE toLower(s.name) IN ['{ents}']
                RETURN d.name AS Disease, COLLECT(DISTINCT s.name) AS Symptoms
                """, {}
            )
        else:
            return ("MATCH (d:Disease) RETURN d.name LIMIT 10", {})

    def parse_query_intent(self, user_query):
        """Always returns a tuple (intent, entities)"""
        try:
            q = (user_query or "").lower().strip()
            # Fetch diseases and symptoms from Neo4j
            disease_list = [rec["d.name"].lower() for rec in self.neo4j.run_query("MATCH (d:Disease) RETURN d.name") or []]
            symptom_list = [rec["s.name"].lower() for rec in self.neo4j.run_query("MATCH (s:Symptom) RETURN s.name") or []]
            
            if any(w in q for w in ['symptom', 'symptoms', 'cause']):
                for disease in disease_list:
                    if disease in q or (len(q) > 3 and disease.startswith(q[:4])):
                        return ("symptoms", disease)
            elif any(w in q for w in ['prevent', 'precaution', 'precautions', 'avoid']):
                for disease in disease_list:
                    if disease in q or (len(q) > 3 and disease.startswith(q[:4])):
                        return ("precautions", disease)
            elif any(w in q for w in ['diseases', 'disease', 'involve', 'cause']):
                symptoms_found = [s for s in symptom_list if s in q]
                if symptoms_found:
                    return ("diseases", symptoms_found)
            return ("precautions", q)
        except Exception:
            return ("general", "")

    def format_prompt(self, neo4j_data, user_query):
        if not neo4j_data:
            return (
                f"No data found for '{user_query}'. Please rephrase or try a different query. "
                "Consult a healthcare professional for medical advice."
            )
        data_str = "\n".join([str(record) for record in neo4j_data])
        return (
            f'Data for query: "{user_query}":\n{data_str}\n\n'
            "Summarize the info in simple language. No external info."
        )

    def call_llm(self, prompt):
        try:
            response = openai_client.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful medical assistant."},
                    {"role": "user", "content": prompt}
                ],
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM response error: {str(e)}")
            return "Sorry, failed to process response."

    def process_query(self, user_query):
        query, params = self.generate_cypher(user_query)
        data = self.neo4j.run_query(query, params)
        if data is None:
            return {"warning": "Failed to query database, try again."}
        if not data:
            # fallback: list some diseases
            default_data = self.neo4j.run_query("MATCH (d:Disease) RETURN d.name LIMIT 10")
            disease_names = [rec['d.name'] for rec in default_data] if default_data else []
            return {
                "warning": f"No info for '{user_query}'. Try 'Fungal Infection' or these diseases: {', '.join(disease_names)}"
            }
        prompt = self.format_prompt(data, user_query)
        response_text = self.call_llm(prompt)
        return {"response": response_text, "data": data}

# Initialize RAG system
try:
    rag_system = RAGSystem(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, OPENROUTER_API_KEY)
except Exception as e:
    logger.error(f"Failed to initialize RAG system: {str(e)}")
    rag_system = None

@app.route('/')
def index():
    if not rag_system:
        logger.error("System failed to start")
        return "System failed to start. Check logs.", 500
    return render_template('index.html')

@app.route('/query', methods=['POST'])
def query():
    if not rag_system:
        logger.error("System not initialized")
        return jsonify({"warning": "System not initialized."}), 500
    data = request.get_json()
    user_query = data.get('query', '').strip()
    if not user_query:
        logger.warning("Empty query received")
        return jsonify({"warning": "Query is empty."}), 400
    result = rag_system.process_query(user_query)
    return jsonify(result)

@app.teardown_appcontext
def cleanup(error=None):
    global rag_system
    if rag_system:
        rag_system.neo4j.close()
        logger.info("Neo4j connection closed")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)