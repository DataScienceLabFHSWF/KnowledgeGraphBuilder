"""Build a Legal Knowledge Graph from German federal law XML files.

This script is a **thin orchestrator** that composes the same KGB pipeline
modules used by full_kg_pipeline.py, but adds a law-specific Phase A
(structural import) before the standard ontology-guided extraction.

Architecture note:
    The KGB pipeline is designed to be ontology-agnostic. It reads whatever
    ontology is in Fuseki and generates extraction prompts from it. For the
    law graph we:
    1. Add a pre-processing Phase A that parses XML and creates structural
       entities/relations without any LLM (fast, deterministic).
    2. Reuse the standard FullKGPipeline for Phase B by configuring it with
       the legal ontology dataset, law document directory, and lawgraph
       Qdrant collection.

    The law-specific extractors (legal_rules, legal_llm, legal_ensemble)
    are registered as additional extractors in the tiered/ensemble pipeline,
    not as replacements.

Usage::

    # Phase A only (fast, no LLM needed)
    python scripts/build_law_graph.py --phase structural

    # Phase B only (reuses full_kg_pipeline with legal profile)
    python scripts/build_law_graph.py --phase semantic

    # Full pipeline (A then B)
    python scripts/build_law_graph.py --phase full

    # Specific laws only
    python scripts/build_law_graph.py --laws AtG StrlSchG StrlSchV

    # Use the existing full_kg_pipeline directly with a profile:
    python scripts/full_kg_pipeline.py --profile data/profiles/legal.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Default paths
DEFAULT_LAW_DATA_DIR = Path("data/law_html")
DEFAULT_ONTOLOGY_PATH = Path("data/ontology/law/law-ontology-v1.0.owl")
DEFAULT_OUTPUT_DIR = Path("output/law_results")
DEFAULT_QDRANT_COLLECTION = "lawgraph"
DEFAULT_FUSEKI_DATASET = "lawgraph"

# Legal profile config for full_kg_pipeline.py reuse
LEGAL_PROFILE = {
    "ontology_dataset": "lawgraph",
    "ontology_path": "data/ontology/law/law-ontology-v1.0.owl",
    "document_dir": "data/law_html",
    "document_extensions": [".xml"],
    "vector_collection": "lawgraph",
    "output_dir": "output/law_results",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Build a Legal Knowledge Graph from German federal law XML.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "For Phase B, this script configures and launches the same\n"
            "FullKGPipeline used by full_kg_pipeline.py with legal-domain\n"
            "settings. You can also run the standard pipeline directly:\n\n"
            "  python scripts/full_kg_pipeline.py --profile data/profiles/legal.json"
        ),
    )
    parser.add_argument(
        "--phase",
        choices=["structural", "semantic", "full"],
        default="full",
        help="Pipeline phase to run (default: full)",
    )
    parser.add_argument(
        "--law-data",
        type=Path,
        default=DEFAULT_LAW_DATA_DIR,
        help="Directory containing law XML files",
    )
    parser.add_argument(
        "--laws",
        nargs="*",
        help="Filter to specific law abbreviations (e.g. AtG StrlSchG)",
    )
    parser.add_argument(
        "--ontology",
        type=Path,
        default=DEFAULT_ONTOLOGY_PATH,
        help="Path to legal ontology OWL file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory for results",
    )
    parser.add_argument(
        "--collection",
        default=DEFAULT_QDRANT_COLLECTION,
        help="Qdrant collection name",
    )
    parser.add_argument(
        "--fuseki-dataset",
        default=DEFAULT_FUSEKI_DATASET,
        help="Fuseki dataset name",
    )
    parser.add_argument(
        "--skip-embed",
        action="store_true",
        help="Skip Qdrant embedding step",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and extract but don't write to databases",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=1,
        help="Number of discovery iterations for Phase B",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args(argv)


# =========================================================================
# Phase A: Structural Import (law-specific, no LLM)
# =========================================================================

def run_phase_a(args: argparse.Namespace) -> dict:
    """Phase A: Structural import (no LLM).

    This phase is law-specific and has no equivalent in the standard
    full_kg_pipeline. It exploits the highly structured XML format of
    gesetze-im-internet.de to create a structural graph deterministically.

    Steps:
    1. Parse all law XML files with LawXMLReader
    2. Convert to KGB Documents via LawDocumentAdapter
    3. Extract structural relations (TEIL_VON, REFERENZIERT) from XML
    4. Create Gesetzbuch + Paragraf entity nodes (ExtractedEntity)
    5. Embed paragraph text into Qdrant (reuses OllamaProvider)
    6. Store entities + relations in Neo4j (reuses Neo4jGraphStore)

    All entities get ``graph_type: "law"`` in their properties for namespace
    separation from the decommissioning KG in the same Neo4j database.

    Returns:
        Stats dict with counts of entities, relations, documents.
    """
    raise NotImplementedError  # TODO: Step 3 implementation


# =========================================================================
# Phase B: Ontology-Guided Semantic Extraction (reuses standard pipeline)
# =========================================================================

def run_phase_b(args: argparse.Namespace) -> dict:
    """Phase B: Ontology-guided LLM extraction.

    This phase reuses the standard FullKGPipeline from full_kg_pipeline.py
    with a legal-domain PipelineConfig. The only law-specific addition is
    registering the LegalRuleBasedExtractor and LegalLLMExtractor as
    additional extractors in the tiered extraction pipeline.

    Config overrides applied:
    - ontology_dataset → "lawgraph" (separate Fuseki dataset)
    - vector_collection → "lawgraph" (separate Qdrant collection)
    - output_dir → "output/law_results"
    - document_extensions → [".xml"]

    Steps:
    1. Build PipelineConfig with legal overrides
    2. Register legal extractors (rule-based + LLM) in the pipeline
    3. Run FullKGPipeline.run() — same discovery loop, enrichment, validation
    4. Return extraction stats

    Returns:
        Stats dict with extraction counts.
    """
    raise NotImplementedError  # TODO: Step 6 implementation


def write_legal_profile() -> Path:
    """Write the legal profile JSON for full_kg_pipeline.py reuse."""
    profile_path = Path("data/profiles/legal.json")
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(json.dumps(LEGAL_PROFILE, indent=2), encoding="utf-8")
    logger.info("Written legal profile to %s", profile_path)
    return profile_path


# =========================================================================
# Main
# =========================================================================

def main(argv: list[str] | None = None) -> None:
    """Main entry point."""
    args = parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("Law Graph Builder — phase=%s", args.phase)
    logger.info("Law data: %s", args.law_data)

    if args.phase in ("structural", "full"):
        stats_a = run_phase_a(args)
        logger.info("Phase A complete: %s", stats_a)

    if args.phase in ("semantic", "full"):
        stats_b = run_phase_b(args)
        logger.info("Phase B complete: %s", stats_b)

    logger.info("Done.")


if __name__ == "__main__":
    main()
