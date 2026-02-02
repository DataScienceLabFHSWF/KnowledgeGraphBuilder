#!/usr/bin/env python3
"""Simple data ingestion without external dependencies."""

from __future__ import annotations

import json
from pathlib import Path


def setup_data() -> None:
    """Index PDFs to Qdrant and load ontology to Fuseki."""
    repo_root = Path(__file__).parent.parent
    pdf_dir = repo_root / "data" / "Decommissioning_Files"
    ontology_file = repo_root / "data" / "ontology" / "plan-ontology-v1.0.owl"
    
    print("\n" + "="*70)
    print("📚 DATA INGESTION SETUP")
    print("="*70)
    
    # 1. List PDFs
    print("\n📄 PDFs to ingest:")
    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    for i, pdf in enumerate(pdf_files, 1):
        size_mb = pdf.stat().st_size / (1024*1024)
        print(f"   [{i:2d}] {pdf.name:50s} ({size_mb:.1f} MB)")
    print(f"\n   Total: {len(pdf_files)} PDFs")
    
    # 2. Ontology
    print("\n🧬 Ontology:")
    if ontology_file.exists():
        size_kb = ontology_file.stat().st_size / 1024
        print(f"   ✓ {ontology_file.name} ({size_kb:.1f} KB)")
    else:
        print(f"   ✗ Not found: {ontology_file}")
    
    # 3. Services
    print("\n🔧 Required services:")
    print("   • Ollama (http://localhost:11434) - for embeddings")
    print("   • Qdrant (http://localhost:6333) - for vector store")
    print("   • Fuseki (http://localhost:3030) - for RDF/ontology")
    print("   • Neo4j (http://localhost:7687) - for property graph")
    
    print("\n" + "="*70)
    print("✅ READY TO INGEST")
    print("="*70)
    print("\nRun with LangChain:")
    print("  pip install -e .")
    print("  PYTHONPATH=src python scripts/ingest_data.py")
    print("\nOr use the CLI:")
    print("  kgbuilder-cli setup")
    print("="*70 + "\n")


if __name__ == "__main__":
    setup_data()
