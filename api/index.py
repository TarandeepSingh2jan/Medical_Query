import os
import logging
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.rag_pipeline import RAGSystem

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__, 
           template_folder='../templates',
           static_folder='../static')

# Environment variables
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Initialize RAG system
try:
    rag_system = RAGSystem(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, OPENROUTER_API_KEY)
except Exception as e:
    logger.error(f"Init failed: {e}")
    rag_system = None

@app.route("/")
def index():
    return render_template("index.html") if rag_system else ("System error", 500)

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

# For Vercel
def handler(request):
    return app(request.environ, lambda status, headers: None)
