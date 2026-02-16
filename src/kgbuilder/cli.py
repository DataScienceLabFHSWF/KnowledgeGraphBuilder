"""CLI interface for KnowledgeGraphBuilder."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

app = typer.Typer(help="KnowledgeGraphBuilder - Ontology-driven KG construction")


@app.command()
def setup(
    pdf_dir: Path = typer.Option(
        Path("data/Decommissioning_Files"),
        help="Directory containing PDFs to index",
    ),
    ontology_file: Path = typer.Option(
        Path("data/ontology/plan-ontology-v1.0.owl"),
        help="Path to ontology file",
    ),
) -> None:
    """Setup: Index PDFs and load ontology.
    
    This command:
    1. Indexes all PDFs into Qdrant vector store
    2. Loads ontology into Fuseki RDF store
    """
    # Import here to avoid circular dependencies
    from scripts.ingest_data import setup_data

    try:
        setup_data()
    except Exception as e:
        typer.echo(f"[ERROR] Setup failed: {e}", err=True)
        sys.exit(1)


@app.command()
def extract(
    config_path: Path = typer.Option(
        Path("config.yaml"),
        help="Path to extraction config",
    ),
) -> None:
    """Extract: Build Knowledge Graph from ingested PDFs.
    
    Runs the full extraction pipeline:
    1. Load PDFs from Qdrant
    2. Extract entities and relations using LLM
    3. Assemble into Neo4j Knowledge Graph
    4. Validate with SHACL
    """
    typer.echo("[WIP] Extraction pipeline not yet implemented")
    sys.exit(1)


@app.command()
def query(
    sparql_query: str = typer.Argument(
        ...,
        help="SPARQL query to execute",
    ),
    format: str = typer.Option(
        "json",
        help="Output format (json, csv, table)",
    ),
) -> None:
    """Query: Execute SPARQL queries on Knowledge Graph.
    
    Example:
    kgbuilder-cli query "SELECT ?entity WHERE { ?entity rdf:type ?type }"
    """
    from kgbuilder.storage.rdf import FusekiStore

    try:
        fuseki = FusekiStore(
            url="http://localhost:3030",
            dataset_name="kgbuilder",
        )
        results = fuseki.query_sparql(sparql_query)

        if format == "json":
            import json

            typer.echo(json.dumps(results, indent=2))
        elif format == "csv":
            import csv
            import io

            if results:
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=results[0].keys())
                writer.writeheader()
                writer.writerows(results)
                typer.echo(output.getvalue())
        else:
            # Table format
            from tabulate import tabulate

            if results:
                typer.echo(tabulate(results, headers="keys", tablefmt="grid"))

    except Exception as e:
        typer.echo(f"[ERROR] Query failed: {e}", err=True)
        sys.exit(1)


@app.command()
def export(
    format: str = typer.Option(
        "turtle",
        help="Export format (turtle, rdfxml, ntriples, jsonld)",
    ),
    output_file: Path = typer.Option(
        Path("kg_export.ttl"),
        help="Output file path",
    ),
) -> None:
    """Export: Export Knowledge Graph in RDF formats.
    
    Supports:
    - Turtle (.ttl)
    - RDF/XML (.rdf)
    - N-Triples (.nt)
    - JSON-LD (.jsonld)
    """
    from kgbuilder.storage.rdf import FusekiStore

    try:
        fuseki = FusekiStore(
            url="http://localhost:3030",
            dataset_name="kgbuilder",
        )
        rdf_data = fuseki.export_rdf(format=format)

        output_file.write_text(rdf_data)
        typer.echo(f"[OK] Exported to {output_file}")

    except Exception as e:
        typer.echo(f"[ERROR] Export failed: {e}", err=True)
        sys.exit(1)


@app.command()
def validate() -> None:
    """Validate: Check Knowledge Graph against ontology.
    
    Runs validation pipeline:
    1. SHACL shape validation
    2. Ontology consistency checks
    3. Competency question validation
    """
    typer.echo("[WIP] Validation pipeline not yet implemented")
    sys.exit(1)


@app.command()
def status() -> None:
    """Status: Show system and data statistics.
    
    Displays:
    - Neo4j store statistics
    - Qdrant vector store statistics
    - Fuseki RDF store statistics
    - Ingestion progress
    """
    typer.echo("[WIP] Status reporting not yet implemented")
    sys.exit(1)


def main() -> None:
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
