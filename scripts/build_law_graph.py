"""Build a Legal Knowledge Graph from German federal law XML files.

Two-phase pipeline:
  Phase A (structural, no LLM): Parse XML → entities + structural relations → embed
  Phase B (semantic, LLM): Ontology-guided extraction → enrich entities + relations

Usage::

    # Phase A only (fast, no LLM needed)
    python scripts/build_law_graph.py --phase structural

    # Phase B only (requires LLM + ontology in Fuseki)
    python scripts/build_law_graph.py --phase semantic

    # Full pipeline (A then B)
    python scripts/build_law_graph.py --phase full

    # Specific laws only
    python scripts/build_law_graph.py --laws AtG StrlSchG StrlSchV
"""

from __future__ import annotations

import argparse
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Build a Legal Knowledge Graph from German federal law XML.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args(argv)


# =========================================================================
# Phase A: Structural Import
# =========================================================================

def run_phase_a(args: argparse.Namespace) -> dict:
    """Phase A: Structural import (no LLM).

    Steps:
    1. Parse all law XML files with LawXMLReader
    2. Convert to KGB Documents via LawDocumentAdapter
    3. Extract structural relations (TEIL_VON, REFERENZIERT)
    4. Create Gesetzbuch + Paragraf entity nodes
    5. Embed paragraph text into Qdrant
    6. Store entities + relations in Neo4j

    Returns:
        Stats dict with counts of entities, relations, documents.
    """
    raise NotImplementedError  # TODO: Step 3 implementation


# =========================================================================
# Phase B: Ontology-Guided Semantic Extraction
# =========================================================================

def run_phase_b(args: argparse.Namespace) -> dict:
    """Phase B: Ontology-guided LLM extraction.

    Steps:
    1. Load legal ontology from Fuseki
    2. Load embedded paragraphs from Qdrant
    3. For each paragraph, run ensemble extraction:
       a. Rule-based: §-refs, authorities, deontic modalities
       b. LLM-based: ontology-guided entity + relation extraction
       c. Merge with confidence calibration
    4. Enrich and validate extracted entities
    5. Store enriched entities + relations in Neo4j

    Returns:
        Stats dict with extraction counts.
    """
    raise NotImplementedError  # TODO: Step 6 implementation


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
