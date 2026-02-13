"""Run KGQualityScorer against Neo4j (uses .env for connection).

Always runs pySHACL validation.  SHACL shapes are generated from the OWL
ontology when no pre-built ``shapes.ttl`` exists.
"""

from __future__ import annotations

import os
from pathlib import Path

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
    store = Neo4jGraphStore(uri, (user, pwd))

    shapes_path = Path(os.getenv("STATIC_SHAPES_PATH", "./data/ontology/shapes.ttl"))
    owl_path = Path(os.getenv("ONTOLOGY_OWL_PATH", "./data/ontology/law/law-ontology-v1.0.owl"))

    scorer = KGQualityScorer(
        ontology_owl_path=owl_path,
        sample_limit=500,
    )
    report = scorer.score_neo4j_store(store, shapes_path)

    print("\n=== KG Quality Report ===")
    print(f"  consistency:    {report.consistency}")
    print(f"  acceptance:     {report.acceptance_rate}")
    print(f"  class_coverage: {report.class_coverage}")
    print(f"  shacl_score:    {report.shacl_score}")
    print(f"  violations:     {report.violations}")
    print(f"  combined_score: {report.combined_score}")
    print(f"  shacl_report:   {report.shacl_report_path}")
    if report.details.get("sampling"):
        s = report.details["sampling"]
        print(f"  sampled:        {s['entities']} entities, {s['relations']} relations")


if __name__ == "__main__":
    main()
