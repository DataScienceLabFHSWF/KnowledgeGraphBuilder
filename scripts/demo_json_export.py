#!/usr/bin/env python3
"""Demo script: Build KG and export to JSON without Neo4j.

This script demonstrates the Phase 6 backend-agnostic architecture.
It uses InMemoryGraphStore to build a KG and export it to multiple formats
WITHOUT requiring a Neo4j database connection.

Usage:
    python scripts/demo_json_export.py
    
    # Or with custom output directory
    python scripts/demo_json_export.py --output-dir ./my-output

Output files created in output/:
    - kg_demo.json      (Simple JSON)
    - kg_demo.jsonld    (JSON-LD for Linked Data)
    - kg_demo.ttl       (RDF/Turtle for semantic web)
    - kg_demo.cypher    (Cypher statements for Neo4j import)
    - kg_demo.graphml   (GraphML for visualization tools)

This demonstrates that the pipeline CAN produce output even without
a running Neo4j database - enabling development, testing, and
interoperability with other tools.
"""

from __future__ import annotations

import argparse
from pathlib import Path

# Add src to path for local development
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kgbuilder.storage.protocol import InMemoryGraphStore, Node, Edge
from kgbuilder.storage.export import KGExporter, ExportConfig


def create_sample_graph() -> InMemoryGraphStore:
    """Create a sample knowledge graph for demonstration.
    
    This creates a small graph about nuclear decommissioning
    to show the output format without running the full pipeline.
    """
    store = InMemoryGraphStore()
    
    # Add facility nodes
    store.add_node(Node(
        id="facility_001",
        label="Grafenrheinfeld Nuclear Power Plant",
        node_type="NuclearFacility",
        properties={
            "confidence": 0.95,
            "description": "A pressurized water reactor facility in Bavaria, Germany",
            "evidence_count": 12,
            "status": "decommissioning",
        },
    ))
    
    store.add_node(Node(
        id="facility_002",
        label="Gundremmingen Nuclear Power Plant",
        node_type="NuclearFacility",
        properties={
            "confidence": 0.92,
            "description": "Former boiling water reactor facility in Bavaria",
            "evidence_count": 8,
        },
    ))
    
    # Add process nodes
    store.add_node(Node(
        id="process_001",
        label="Reactor Defueling",
        node_type="DecommissioningProcess",
        properties={
            "confidence": 0.88,
            "description": "Removal of nuclear fuel from reactor core",
            "evidence_count": 5,
        },
    ))
    
    store.add_node(Node(
        id="process_002",
        label="Contamination Assessment",
        node_type="DecommissioningProcess",
        properties={
            "confidence": 0.91,
            "description": "Radiological characterization of facility areas",
            "evidence_count": 7,
        },
    ))
    
    store.add_node(Node(
        id="process_003",
        label="Component Dismantling",
        node_type="DecommissioningProcess",
        properties={
            "confidence": 0.85,
            "description": "Physical removal of reactor components",
            "evidence_count": 4,
        },
    ))
    
    # Add regulatory nodes
    store.add_node(Node(
        id="reg_001",
        label="Federal Office for the Safety of Nuclear Waste Management",
        node_type="RegulatoryBody",
        properties={
            "confidence": 0.97,
            "description": "German federal authority (BASE)",
            "abbreviation": "BASE",
        },
    ))
    
    # Add waste type nodes
    store.add_node(Node(
        id="waste_001",
        label="Low-Level Radioactive Waste",
        node_type="WasteType",
        properties={
            "confidence": 0.93,
            "description": "Waste with low radioactivity levels",
            "abbreviation": "LLW",
        },
    ))
    
    store.add_node(Node(
        id="waste_002",
        label="Intermediate-Level Radioactive Waste",
        node_type="WasteType",
        properties={
            "confidence": 0.90,
            "description": "Waste requiring shielding but not cooling",
            "abbreviation": "ILW",
        },
    ))
    
    # Add relationships
    store.add_edge(Edge(
        id="e1",
        source_id="facility_001",
        target_id="process_001",
        edge_type="undergoes",
        properties={"confidence": 0.87},
    ))
    
    store.add_edge(Edge(
        id="e2",
        source_id="facility_001",
        target_id="process_002",
        edge_type="undergoes",
        properties={"confidence": 0.89},
    ))
    
    store.add_edge(Edge(
        id="e3",
        source_id="facility_001",
        target_id="process_003",
        edge_type="undergoes",
        properties={"confidence": 0.82},
    ))
    
    store.add_edge(Edge(
        id="e4",
        source_id="process_001",
        target_id="process_002",
        edge_type="precedes",
        properties={"confidence": 0.91},
    ))
    
    store.add_edge(Edge(
        id="e5",
        source_id="process_002",
        target_id="process_003",
        edge_type="precedes",
        properties={"confidence": 0.88},
    ))
    
    store.add_edge(Edge(
        id="e6",
        source_id="reg_001",
        target_id="facility_001",
        edge_type="regulates",
        properties={"confidence": 0.96},
    ))
    
    store.add_edge(Edge(
        id="e7",
        source_id="reg_001",
        target_id="facility_002",
        edge_type="regulates",
        properties={"confidence": 0.94},
    ))
    
    store.add_edge(Edge(
        id="e8",
        source_id="process_003",
        target_id="waste_001",
        edge_type="produces",
        properties={"confidence": 0.85},
    ))
    
    store.add_edge(Edge(
        id="e9",
        source_id="process_003",
        target_id="waste_002",
        edge_type="produces",
        properties={"confidence": 0.83},
    ))
    
    return store


def main() -> None:
    """Run the demo export."""
    parser = argparse.ArgumentParser(description="Demo KG export without Neo4j")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Output directory for exported files",
    )
    args = parser.parse_args()
    
    print("=" * 60)
    print("KGBuilder Phase 6 Demo: Export KG Without Neo4j")
    print("=" * 60)
    print()
    
    # Create sample graph
    print("Creating sample knowledge graph...")
    store = create_sample_graph()
    
    # Show statistics
    stats = store.get_statistics()
    print(f"  Nodes: {stats.node_count}")
    print(f"  Edges: {stats.edge_count}")
    print(f"  Node types: {dict(stats.nodes_by_type)}")
    print(f"  Edge types: {dict(stats.edges_by_type)}")
    print()
    
    # Create output directory
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure exporter
    config = ExportConfig(
        base_uri="http://example.org/decommissioning/",
        ontology_uri="http://example.org/decom-ontology#",
        pretty_print=True,
    )
    
    exporter = KGExporter(store, config)
    
    # Export to all formats
    formats = [
        ("json", "Simple JSON"),
        ("jsonld", "JSON-LD (Linked Data)"),
        ("turtle", "RDF/Turtle (Semantic Web)"),
        ("cypher", "Cypher (Neo4j import)"),
        ("graphml", "GraphML (Visualization)"),
    ]
    
    print("Exporting to multiple formats...")
    for fmt, description in formats:
        ext = "ttl" if fmt == "turtle" else fmt
        filepath = output_dir / f"kg_demo.{ext}"
        exporter.export_to_file(filepath, format=fmt)
        print(f"  ✓ {description}: {filepath}")
    
    print()
    print("=" * 60)
    print("SUCCESS: KG exported without Neo4j!")
    print("=" * 60)
    print()
    print("These files can be:")
    print("  - kg_demo.json:    Processed by any JSON tool")
    print("  - kg_demo.jsonld:  Loaded into Triple Stores")
    print("  - kg_demo.ttl:     Uploaded to Fuseki/Virtuoso")
    print("  - kg_demo.cypher:  Imported into Neo4j later")
    print("  - kg_demo.graphml: Opened in Gephi/yEd for visualization")
    print()


if __name__ == "__main__":
    main()
