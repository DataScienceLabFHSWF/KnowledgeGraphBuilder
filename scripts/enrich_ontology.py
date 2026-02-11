#!/usr/bin/env python3
"""Enrich the decommissioning ontology based on discovered entity types.

Compares the entity types actually extracted by the KG pipeline (from Neo4j)
against the current ontology classes and generates an enriched v2.0 OWL file
with missing classes, subclass hierarchy, and new object properties.

Addresses Task 4 from NEXT_STEPS.md and wiki_alisa_kiko #100 (subclassing).

Usage:
    # Auto-discover missing classes from Neo4j and generate enriched ontology:
    python scripts/enrich_ontology.py \
        --input data/ontology/domain/plan-ontology-v1.0.owl \
        --output data/ontology/domain/plan-ontology-v2.0.owl

    # Dry run — show what would be added:
    python scripts/enrich_ontology.py --input data/ontology/domain/plan-ontology-v1.0.owl --dry-run

    # Supply a manual mapping file instead of Neo4j discovery:
    python scripts/enrich_ontology.py \
        --input data/ontology/domain/plan-ontology-v1.0.owl \
        --mapping data/ontology/enrichment-mapping.json \
        --output data/ontology/domain/plan-ontology-v2.0.owl

Environment variables:
    NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD  — for auto-discovery
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

try:
    from rdflib import OWL, RDF, RDFS, Graph, Literal, Namespace, URIRef
    from rdflib.namespace import DC, DCTERMS, XSD
except ImportError:
    print("rdflib is required: pip install rdflib", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Namespace
# ---------------------------------------------------------------------------

PLAN = Namespace("https://purl.org/ai4s/ontology/planning#")
DECOMM = Namespace("https://purl.org/ai4s/ontology/decommissioning#")


# ---------------------------------------------------------------------------
# Subclass mapping — maps discovered Neo4j labels → parent class
# ---------------------------------------------------------------------------
# Based on Neo4j label distribution from baseline (387 nodes, 29 types)
# and competency questions analysis.

DEFAULT_CLASS_HIERARCHY: dict[str, dict] = {
    # === Existing classes (already in v1.0) ===
    # "Activity", "Component", "Facility" are present

    # === New top-level classes ===
    "Organization": {
        "parent": None,
        "description_de": "Akteur, Behörde oder Organisation im Rückbauprozess",
        "description_en": "Actor, authority, or organization in the decommissioning process",
        "subclasses": ["Authority", "Operator", "Contractor"],
    },
    "Regulation": {
        "parent": None,
        "description_de": "Gesetz, Verordnung oder Vorschrift",
        "description_en": "Law, regulation, or legal provision",
        "subclasses": ["LegalProvision", "Permit", "License"],
    },
    "Process": {
        "parent": "Activity",
        "description_de": "Ein definierter Ablauf oder Verfahren",
        "description_en": "A defined process or procedure",
        "subclasses": ["DecommissioningPhase", "ApprovalProcess", "WasteManagement"],
    },
    "WasteCategory": {
        "parent": None,
        "description_de": "Kategorie radioaktiver oder konventioneller Abfälle",
        "description_en": "Category of radioactive or conventional waste",
        "subclasses": [],
    },
    "SafetySystem": {
        "parent": "Component",
        "description_de": "Sicherheitsrelevantes System oder Barriere",
        "description_en": "Safety-relevant system or barrier",
        "subclasses": [],
    },
    "Documentation": {
        "parent": None,
        "description_de": "Genehmigungsunterlage, Bericht oder Nachweis",
        "description_en": "Approval document, report, or proof",
        "subclasses": [],
    },
    "NuclearMaterial": {
        "parent": None,
        "description_de": "Kernbrennstoff oder sonstiges radioaktives Material",
        "description_en": "Nuclear fuel or other radioactive material",
        "subclasses": [],
    },
    "Transport": {
        "parent": "Activity",
        "description_de": "Transport von radioaktivem Material",
        "description_en": "Transport of radioactive material",
        "subclasses": [],
    },
    "State": {
        "parent": None,
        "description_de": "Zustand einer Anlage oder eines Prozesses",
        "description_en": "State of a facility or process",
        "subclasses": [],
    },
    "Measurement": {
        "parent": None,
        "description_de": "Messung, Grenzwert oder Messgröße",
        "description_en": "Measurement, threshold, or measured quantity",
        "subclasses": [],
    },
}


# New object properties linking the domain
DEFAULT_OBJECT_PROPERTIES: list[dict] = [
    {
        "name": "governedBy",
        "domain": "Activity",
        "range": "Regulation",
        "description_de": "Aktivität wird durch Vorschrift geregelt",
        "description_en": "Activity is governed by a regulation",
    },
    {
        "name": "requires",
        "domain": "Activity",
        "range": "Permit",
        "description_de": "Aktivität erfordert Genehmigung",
        "description_en": "Activity requires a permit",
    },
    {
        "name": "produces",
        "domain": "Activity",
        "range": "WasteCategory",
        "description_de": "Aktivität erzeugt Abfall(kategorie)",
        "description_en": "Activity produces waste (category)",
    },
    {
        "name": "referencesLaw",
        "domain": "Documentation",
        "range": "Regulation",
        "description_de": "Dokument verweist auf Gesetz",
        "description_en": "Document references a law",
    },
    {
        "name": "issuedBy",
        "domain": "Permit",
        "range": "Authority",
        "description_de": "Genehmigung wird von Behörde erteilt",
        "description_en": "Permit is issued by an authority",
    },
    {
        "name": "operatedBy",
        "domain": "Facility",
        "range": "Operator",
        "description_de": "Anlage wird von Betreiber betrieben",
        "description_en": "Facility is operated by an operator",
    },
    {
        "name": "hasState",
        "domain": "Facility",
        "range": "State",
        "description_de": "Anlage hat Zustand",
        "description_en": "Facility has a state",
    },
    {
        "name": "containsMaterial",
        "domain": "Facility",
        "range": "NuclearMaterial",
        "description_de": "Anlage enthält Material",
        "description_en": "Facility contains material",
    },
]


# ---------------------------------------------------------------------------
# Neo4j discovery
# ---------------------------------------------------------------------------

def discover_labels_from_neo4j() -> Counter[str]:
    """Query Neo4j for all node labels and their counts."""
    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("neo4j driver not installed; use --mapping instead", file=sys.stderr)
        return Counter()

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "changeme")

    # Law graph labels to skip
    skip = {"Paragraf", "Abschnitt", "Gesetzbuch"}

    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session() as session:
            result = session.run(
                "MATCH (n) UNWIND labels(n) AS lbl "
                "WITH lbl WHERE NOT lbl IN $skip "
                "RETURN lbl, count(*) AS cnt ORDER BY cnt DESC",
                skip=list(skip),
            )
            return Counter({r["lbl"]: r["cnt"] for r in result})
    finally:
        driver.close()


def find_existing_classes(g: Graph) -> set[str]:
    """Extract class local names from an OWL graph."""
    classes: set[str] = set()
    for s in g.subjects(RDF.type, OWL.Class):
        if isinstance(s, URIRef):
            name = s.rsplit("#", 1)[-1] if "#" in s else s.rsplit("/", 1)[-1]
            classes.add(name)
    return classes


# ---------------------------------------------------------------------------
# Enrichment
# ---------------------------------------------------------------------------

def enrich_ontology(
    input_path: Path,
    output_path: Path | None,
    hierarchy: dict[str, dict] | None = None,
    properties: list[dict] | None = None,
    dry_run: bool = False,
) -> None:
    """Add missing classes and properties to the ontology."""
    if hierarchy is None:
        hierarchy = DEFAULT_CLASS_HIERARCHY
    if properties is None:
        properties = DEFAULT_OBJECT_PROPERTIES

    g = Graph()
    g.parse(str(input_path))

    existing = find_existing_classes(g)
    print(f"Existing ontology classes ({len(existing)}): {sorted(existing)}")

    # Discover from Neo4j
    neo4j_labels = discover_labels_from_neo4j()
    if neo4j_labels:
        missing_in_ontology = set(neo4j_labels.keys()) - existing
        print(f"\nNeo4j labels not in ontology ({len(missing_in_ontology)}):")
        for lbl in sorted(missing_in_ontology):
            print(f"  - {lbl} ({neo4j_labels[lbl]} nodes)")

    # Add classes
    added_classes: list[str] = []
    for cls_name, info in hierarchy.items():
        cls_uri = DECOMM[cls_name]

        if cls_name in existing:
            print(f"  [skip] {cls_name} (already exists)")
            continue

        if dry_run:
            parent_str = f" rdfs:subClassOf {info.get('parent', 'owl:Thing')}"
            print(f"  [would add] {cls_name}{parent_str}")
            continue

        g.add((cls_uri, RDF.type, OWL.Class))
        g.add((cls_uri, RDFS.label, Literal(cls_name, lang="en")))

        if info.get("description_de"):
            g.add((cls_uri, RDFS.comment, Literal(info["description_de"], lang="de")))
        if info.get("description_en"):
            g.add((cls_uri, RDFS.comment, Literal(info["description_en"], lang="en")))

        parent = info.get("parent")
        if parent:
            parent_uri = (
                DECOMM[parent] if parent not in existing else _find_class_uri(g, parent)
            )
            g.add((cls_uri, RDFS.subClassOf, parent_uri))

        # Add subclasses
        for sub_name in info.get("subclasses", []):
            sub_uri = DECOMM[sub_name]
            g.add((sub_uri, RDF.type, OWL.Class))
            g.add((sub_uri, RDFS.label, Literal(sub_name, lang="en")))
            g.add((sub_uri, RDFS.subClassOf, cls_uri))
            added_classes.append(sub_name)

        added_classes.append(cls_name)

    # Add object properties
    added_props: list[str] = []
    for prop in properties:
        prop_uri = DECOMM[prop["name"]]

        if dry_run:
            print(f"  [would add property] {prop['name']}: "
                  f"{prop['domain']} → {prop['range']}")
            continue

        g.add((prop_uri, RDF.type, OWL.ObjectProperty))
        g.add((prop_uri, RDFS.label, Literal(prop["name"], lang="en")))
        if prop.get("description_de"):
            g.add((prop_uri, RDFS.comment, Literal(prop["description_de"], lang="de")))

        domain_uri = DECOMM[prop["domain"]]
        range_uri = DECOMM[prop["range"]]
        g.add((prop_uri, RDFS.domain, domain_uri))
        g.add((prop_uri, RDFS.range, range_uri))
        added_props.append(prop["name"])

    if dry_run:
        print(f"\nDry run complete. Would add {len(added_classes)} classes, "
              f"{len(added_props)} properties.")
        return

    # Serialize
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        g.serialize(str(output_path), format="xml")
        print(f"\nEnriched ontology saved: {output_path}")
        print(f"  Added {len(added_classes)} classes, {len(added_props)} properties")
        total = len(find_existing_classes(g))
        print(f"  Total classes now: {total}")


def _find_class_uri(g: Graph, name: str) -> URIRef:
    """Find a class URI by local name in the graph."""
    for s in g.subjects(RDF.type, OWL.Class):
        if isinstance(s, URIRef) and s.endswith(name):
            return s
    # Fallback to DECOMM namespace
    return DECOMM[name]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enrich decommissioning ontology from Neo4j data"
    )
    parser.add_argument(
        "--input", "-i", required=True,
        help="Path to current OWL ontology file",
    )
    parser.add_argument(
        "--output", "-o", default=None,
        help="Path for enriched OWL output (default: v2.0 variant of input)",
    )
    parser.add_argument(
        "--mapping", "-m", default=None,
        help="JSON file with custom class hierarchy (instead of defaults)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be added without writing",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Input ontology not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output) if args.output else (
        input_path.parent / input_path.name.replace("v1.0", "v2.0")
    )

    hierarchy = None
    properties = None
    if args.mapping:
        mapping = json.loads(Path(args.mapping).read_text())
        hierarchy = mapping.get("classes", DEFAULT_CLASS_HIERARCHY)
        properties = mapping.get("properties", DEFAULT_OBJECT_PROPERTIES)

    enrich_ontology(input_path, output_path, hierarchy, properties, args.dry_run)


if __name__ == "__main__":
    main()
