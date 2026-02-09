"""Merge and preprocess multiple OWL/TTL ontology files into a single OWL file.

LKIF-Core ships as 11 separate OWL modules with inter-module owl:imports.
ELI is a single large OWL file. Our pipeline (FusekiStore.load_ontology)
expects a single RDF document per upload.

This script:
1. Parses all source ontology files with rdflib
2. Merges selected triples into a unified graph
3. Cherry-picks only the classes/properties we actually need
4. Writes a single self-contained OWL/XML file

Modes:
- "full": Merge everything from all source files (large)
- "cherry-pick": Only extract specific classes/properties we map to (small, recommended)

Usage::

    # Cherry-pick only what we need (recommended)
    python scripts/merge_legal_ontologies.py --mode cherry-pick

    # Full merge of all LKIF-Core + ELI
    python scripts/merge_legal_ontologies.py --mode full

    # Custom output path
    python scripts/merge_legal_ontologies.py -o data/ontology/legal/merged.owl
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Source directories
LKIF_DIR = Path("data/ontology/legal/lkif-core")
ELI_DIR = Path("data/ontology/legal/eli")
OUTPUT_DEFAULT = Path("data/ontology/legal/legal-foundations-merged.owl")

# LKIF-Core modules to include (order matters for imports)
LKIF_MODULES = [
    "lkif-top.owl",
    "mereology.owl",
    "time.owl",
    "process.owl",
    "action.owl",
    "role.owl",
    "expression.owl",
    "legal-action.owl",
    "legal-role.owl",
    "norm.owl",
]

# Classes we actually use from LKIF-Core (for cherry-pick mode)
LKIF_CHERRY_PICK_CLASSES = {
    # From norm.owl
    "http://www.estrellaproject.org/lkif-core/norm.owl#Norm",
    "http://www.estrellaproject.org/lkif-core/norm.owl#Obligation",
    "http://www.estrellaproject.org/lkif-core/norm.owl#Permission",
    "http://www.estrellaproject.org/lkif-core/norm.owl#Prohibition",
    "http://www.estrellaproject.org/lkif-core/norm.owl#Right",
    "http://www.estrellaproject.org/lkif-core/norm.owl#Statute",
    "http://www.estrellaproject.org/lkif-core/norm.owl#Regulation",
    "http://www.estrellaproject.org/lkif-core/norm.owl#Legal_Document",
    "http://www.estrellaproject.org/lkif-core/norm.owl#Legal_Source",
    # From legal-action.owl
    "http://www.estrellaproject.org/lkif-core/legal-action.owl#Public_Body",
    "http://www.estrellaproject.org/lkif-core/legal-action.owl#Legal_Person",
    "http://www.estrellaproject.org/lkif-core/legal-action.owl#Natural_Person",
    "http://www.estrellaproject.org/lkif-core/legal-action.owl#Public_Act",
    "http://www.estrellaproject.org/lkif-core/legal-action.owl#Decision",
    # From legal-role.owl
    "http://www.estrellaproject.org/lkif-core/legal-role.owl#Legal_Role",
}

# Classes we use from ELI
ELI_CHERRY_PICK_CLASSES = {
    "http://data.europa.eu/eli/ontology#LegalResource",
    "http://data.europa.eu/eli/ontology#LegalExpression",
    "http://data.europa.eu/eli/ontology#LegalResourceSubdivision",
    "http://data.europa.eu/eli/ontology#Work",
    "http://data.europa.eu/eli/ontology#Agent",
}

# Properties we use from ELI
ELI_CHERRY_PICK_PROPERTIES = {
    "http://data.europa.eu/eli/ontology#cites",
    "http://data.europa.eu/eli/ontology#cited_by",
    "http://data.europa.eu/eli/ontology#amends",
    "http://data.europa.eu/eli/ontology#amended_by",
    "http://data.europa.eu/eli/ontology#is_part_of",
    "http://data.europa.eu/eli/ontology#has_part",
    "http://data.europa.eu/eli/ontology#repealed_by",
    "http://data.europa.eu/eli/ontology#date_document",
    "http://data.europa.eu/eli/ontology#title",
    "http://data.europa.eu/eli/ontology#title_short",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge LKIF-Core and ELI ontology files into a single OWL file.",
    )
    parser.add_argument(
        "--mode",
        choices=["full", "cherry-pick"],
        default="cherry-pick",
        help="Merge mode: 'full' merges everything, 'cherry-pick' selects only needed classes",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=OUTPUT_DEFAULT,
        help="Output file path",
    )
    parser.add_argument(
        "--include-eli",
        action="store_true",
        default=True,
        help="Include ELI ontology (default: True)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and report stats without writing output",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args(argv)


def merge_full(lkif_dir: Path, eli_dir: Path, include_eli: bool) -> str:
    """Full merge: load all modules into one rdflib Graph, serialize.

    Args:
        lkif_dir: Path to LKIF-Core OWL files.
        eli_dir: Path to ELI OWL files.
        include_eli: Whether to include ELI.

    Returns:
        Merged OWL/XML string.
    """
    try:
        import rdflib
    except ImportError:
        logger.error("rdflib is required: pip install rdflib")
        sys.exit(1)

    merged = rdflib.Graph()

    # Load LKIF-Core modules in dependency order
    for module in LKIF_MODULES:
        path = lkif_dir / module
        if path.exists():
            logger.info("Loading %s (%d bytes)", module, path.stat().st_size)
            try:
                merged.parse(str(path), format="xml")
            except Exception as e:
                logger.warning("Failed to parse %s: %s", module, e)

    # Load ELI
    if include_eli:
        eli_path = eli_dir / "eli.owl"
        if eli_path.exists():
            logger.info("Loading eli.owl (%d bytes)", eli_path.stat().st_size)
            try:
                merged.parse(str(eli_path), format="xml")
            except Exception as e:
                logger.warning("Failed to parse eli.owl: %s", e)

        eli_sdo = eli_dir / "eli-sdo.ttl"
        if eli_sdo.exists():
            logger.info("Loading eli-sdo.ttl")
            try:
                merged.parse(str(eli_sdo), format="turtle")
            except Exception as e:
                logger.warning("Failed to parse eli-sdo.ttl: %s", e)

    logger.info("Merged graph: %d triples", len(merged))
    return merged.serialize(format="xml")


def merge_cherry_pick(lkif_dir: Path, eli_dir: Path, include_eli: bool) -> str:
    """Cherry-pick merge: extract only specific classes and their annotations.

    For each cherry-picked class/property, extracts:
    - The rdf:type triple (owl:Class, owl:ObjectProperty, etc.)
    - rdfs:label, rdfs:comment annotations
    - rdfs:subClassOf (direct parent only)
    - rdfs:domain, rdfs:range (for properties)

    Args:
        lkif_dir: Path to LKIF-Core OWL files.
        eli_dir: Path to ELI OWL files.
        include_eli: Whether to include ELI.

    Returns:
        Cherry-picked OWL/XML string.
    """
    try:
        import rdflib
        from rdflib import OWL, RDF, RDFS, Namespace
    except ImportError:
        logger.error("rdflib is required: pip install rdflib")
        sys.exit(1)

    # Parse all source files into a source graph
    source = rdflib.Graph()
    for module in LKIF_MODULES:
        path = lkif_dir / module
        if path.exists():
            try:
                source.parse(str(path), format="xml")
            except Exception as e:
                logger.warning("Failed to parse %s: %s", module, e)

    if include_eli:
        eli_path = eli_dir / "eli.owl"
        if eli_path.exists():
            try:
                source.parse(str(eli_path), format="xml")
            except Exception as e:
                logger.warning("Failed to parse eli.owl: %s", e)

    # Build cherry-picked graph
    picked = rdflib.Graph()

    # Bind common prefixes
    picked.bind("owl", OWL)
    picked.bind("rdfs", RDFS)
    picked.bind("lkif-norm", Namespace("http://www.estrellaproject.org/lkif-core/norm.owl#"))
    picked.bind("lkif-la", Namespace("http://www.estrellaproject.org/lkif-core/legal-action.owl#"))
    picked.bind("lkif-lr", Namespace("http://www.estrellaproject.org/lkif-core/legal-role.owl#"))
    picked.bind("eli", Namespace("http://data.europa.eu/eli/ontology#"))

    # Predicates we want to keep for each resource
    keep_predicates = {
        RDF.type, RDFS.label, RDFS.comment,
        RDFS.subClassOf, RDFS.domain, RDFS.range,
        OWL.equivalentClass, OWL.inverseOf,
    }

    # Cherry-pick classes
    all_targets = LKIF_CHERRY_PICK_CLASSES.copy()
    if include_eli:
        all_targets |= ELI_CHERRY_PICK_CLASSES
        all_targets |= ELI_CHERRY_PICK_PROPERTIES

    for uri_str in all_targets:
        uri = rdflib.URIRef(uri_str)
        for pred, obj in source.predicate_objects(uri):
            if pred in keep_predicates:
                # Only keep simple (non-blank-node) objects for readability
                if isinstance(obj, (rdflib.URIRef, rdflib.Literal)):
                    picked.add((uri, pred, obj))

    logger.info(
        "Cherry-picked: %d classes/properties → %d triples",
        len(all_targets),
        len(picked),
    )
    return picked.serialize(format="xml")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.mode == "full":
        result = merge_full(LKIF_DIR, ELI_DIR, args.include_eli)
    else:
        result = merge_cherry_pick(LKIF_DIR, ELI_DIR, args.include_eli)

    if args.dry_run:
        logger.info("Dry run — would write %d bytes to %s", len(result), args.output)
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result, encoding="utf-8")
    logger.info("Written merged ontology to %s (%d bytes)", args.output, len(result))


if __name__ == "__main__":
    main()
