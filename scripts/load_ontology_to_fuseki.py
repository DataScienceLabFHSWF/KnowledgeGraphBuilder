#!/usr/bin/env python3
"""Load ontology into Fuseki RDF store.

By default, this script reads the benchmark ontology from
data/ontology/domain/decommissioning.owl and uploads it to the
configured Fuseki dataset.

Usage:
    python scripts/load_ontology_to_fuseki.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import structlog

from kgbuilder.storage.rdf import FusekiStore

logger = structlog.get_logger(__name__)


def load_ontology() -> None:
    """Load ontology into Fuseki."""
    import os

    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv()

    # Get Fuseki configuration from .env
    fuseki_url = os.getenv("FUSEKI_URL", "http://localhost:3030")
    fuseki_user = os.getenv("FUSEKI_USER", "admin")
    fuseki_password = os.getenv("FUSEKI_PASSWORD", "")
    dataset_name = os.getenv("FUSEKI_DATASET", "kgbuilder")

    ontology_path = Path(
        os.getenv(
            "ONTOLOGY_OWL_PATH",
            str(Path(__file__).parent.parent / "data" / "ontology" / "domain" / "decommissioning.owl"),
        )
    )

    logger.info(
        "loading_ontology",
        fuseki_url=fuseki_url,
        dataset_name=dataset_name,
        ontology_path=str(ontology_path),
        ontology_size_kb=ontology_path.stat().st_size / 1024,
    )

    # Verify ontology file exists
    if not ontology_path.exists():
        logger.error("ontology_not_found", path=str(ontology_path))
        raise FileNotFoundError(f"Ontology file not found: {ontology_path}")

    # Read ontology content
    with open(ontology_path) as f:
        ontology_content = f.read()

    logger.info("ontology_read", size_bytes=len(ontology_content))

    # Connect to Fuseki and load ontology
    try:
        fuseki = FusekiStore(
            url=fuseki_url,
            dataset_name=dataset_name,
            username=fuseki_user,
            password=fuseki_password,
        )
        logger.info("fuseki_connected")

        # Load ontology
        fuseki.load_ontology(ontology_content)
        logger.info("ontology_loaded_successfully")

        print(f"[OK] Ontology loaded successfully to {fuseki_url}")
        print(f"  Dataset: {dataset_name}")
        print(f"  File: {ontology_path}")
        print(f"  Size: {len(ontology_content) / 1024:.1f} KB")

    except Exception as e:
        logger.error("failed_to_load_ontology", error=str(e), exc_info=True)
        print(f"[FAIL] Failed to load ontology: {e}")
        raise


if __name__ == "__main__":
    load_ontology()
