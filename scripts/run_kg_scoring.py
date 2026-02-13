"""Run KGQualityScorer against Neo4j (uses .env for connection)."""
from pathlib import Path
import os
# load .env if python-dotenv is available (optional)
try:
    import dotenv

    dotenv.load_dotenv()
except Exception:
    pass

from kgbuilder.storage.neo4j_store import Neo4jGraphStore
from kgbuilder.validation.scorer import KGQualityScorer


def main() -> None:
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    pwd = os.getenv("NEO4J_PASSWORD", "changeme")

    print(f"Connecting to Neo4j at {uri} as {user}...")
    try:
        # Neo4jGraphStore expects auth as a (user, password) tuple
        store = Neo4jGraphStore(uri, (user, pwd))
    except Exception as e:
        print("Failed to connect to Neo4j:", e)
        raise

    shapes_path = Path(os.getenv("STATIC_SHAPES_PATH", "./data/ontology/shapes.ttl"))
    scorer = KGQualityScorer()
    report = scorer.score_neo4j_store(store, shapes_path)

    print("KG quality report:")
    print(report)


if __name__ == "__main__":
    main()
