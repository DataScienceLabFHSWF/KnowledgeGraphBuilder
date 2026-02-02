#!/usr/bin/env python3
"""Load decommissioning ontology into Fuseki RDF store.

This script reads the ontology file from data/ontology/plan-ontology-v1.0.owl
and uploads it to the Fuseki server configured in .env file.

Usage:
    python scripts/load_ontology_to_fuseki.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kgbuilder.storage.rdf import FusekiStore
import structlog


logger = structlog.get_logger(__name__)


def load_ontology() -> None:
    """Load ontology into Fuseki."""
    from dotenv import load_dotenv
    import os

    # Load environment variables
    load_dotenv()

    # Get Fuseki configuration from .env
    fuseki_url = os.getenv("FUSEKI_URL", "http://localhost:3030")
    fuseki_user = os.getenv("FUSEKI_USER", "admin")
    fuseki_password = os.getenv("FUSEKI_PASSWORD", "")

    ontology_path = Path(__file__).parent.parent / "data" / "ontology" / "plan-ontology-v1.0.owl"

    logger.info(
        "loading_ontology",
        fuseki_url=fuseki_url,
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
            dataset_name="kgbuilder",
            username=fuseki_user,
            password=fuseki_password,
        )
        logger.info("fuseki_connected")

        # Load ontology
        fuseki.load_ontology(ontology_content)
        logger.info("ontology_loaded_successfully")

        print(f"✓ Ontology loaded successfully to {fuseki_url}")
        print(f"  Dataset: kgbuilder")
        print(f"  File: {ontology_path}")
        print(f"  Size: {len(ontology_content) / 1024:.1f} KB")

    except Exception as e:
        logger.error("failed_to_load_ontology", error=str(e), exc_info=True)
        print(f"✗ Failed to load ontology: {e}")
        raise


if __name__ == "__main__":
    load_ontology()
