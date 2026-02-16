import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import structlog

from kgbuilder.storage.neo4j_store import Neo4jGraphStore
from kgbuilder.storage.rdf import FusekiStore
from kgbuilder.storage.vector import QdrantStore

logger = structlog.get_logger()

def prep_smoke_test():
    from dotenv import load_dotenv
    load_dotenv()

    # Fuseki
    fuseki_url = os.getenv("FUSEKI_URL", "http://localhost:3030")
    fuseki_user = os.getenv("FUSEKI_USER", "admin")
    fuseki_password = os.getenv("FUSEKI_PASSWORD", "admin")
    dataset_name = "kgbuilder_test"

    # 1. Load Ontology
    onto_path = Path("data/smoke_test/decomm_ontology.ttl")
    with open(onto_path) as f:
        content = f.read()

    fuseki = FusekiStore(url=fuseki_url, dataset_name=dataset_name, username=fuseki_user, password=fuseki_password)
    fuseki.load_ontology(content)
    logger.info("ontology_loaded", dataset=dataset_name)

    # 2. Clear Neo4j
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "changeme")
    neo4j_db = "neo4j_test"

    # Try to create database if it doesn't exist (requires Enterprise or Neo4j 4.0+)
    system_neo4j = Neo4jGraphStore(uri=neo4j_uri, auth=(neo4j_user, neo4j_password), database="system")
    try:
        with system_neo4j._driver.session(database="system") as session:
            session.run(f"CREATE DATABASE {neo4j_db} IF NOT EXISTS")
        logger.info("neo4j_database_created", database=neo4j_db)
    except Exception as e:
        logger.warning("neo4j_database_creation_failed", error=str(e), fallback="using default neo4j database")
        neo4j_db = "neo4j"

    neo4j = Neo4jGraphStore(uri=neo4j_uri, auth=(neo4j_user, neo4j_password), database=neo4j_db)
    with neo4j._driver.session(database=neo4j_db) as session:
        session.run("MATCH (n) DETACH DELETE n")
    logger.info("neo4j_cleared", database=neo4j_db)

    # 3. Clear Qdrant
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    collection_name = "discovery_test"

    qdrant = QdrantStore(url=qdrant_url, collection_name=collection_name)
    try:
        qdrant.client.delete_collection(collection_name)
    except Exception as e:
        logger.warning("collection_delete_failed", error=str(e))
        pass

    logger.info("qdrant_prep_done", collection=collection_name)

if __name__ == "__main__":
    prep_smoke_test()
