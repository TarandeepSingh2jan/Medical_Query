import logging
import spacy
from .neo4j_driver import Neo4jDriver

logger = logging.getLogger(__name__)

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
        return list(set(diseases)) or [text.split()[-1]]
