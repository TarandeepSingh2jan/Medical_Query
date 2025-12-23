import os
import logging
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)

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
