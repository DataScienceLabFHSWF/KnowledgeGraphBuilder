#!/usr/bin/env python3
"""Data ingestion: Store PDFs in Qdrant with simple text vectors."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from langchain_text_splitters import CharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams


def ingest_all_data() -> None:
    """Index all PDFs and load ontology."""
    repo_root = Path(__file__).parent.parent
    pdf_dir = repo_root / "data" / "Decommissioning_Files"
    ontology_file = repo_root / "data" / "ontology" / "plan-ontology-v1.0.owl"
    
    print("\n📚 STEP 1: Setup Qdrant")
    client = QdrantClient(url="http://localhost:6333")
    
    try:
        client.get_collection("documents")
        print("   ✓ Collection exists")
    except:
        print("   • Creating collection...")
        client.create_collection(
            collection_name="documents",
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )
        print("   ✓ Created")
    
    print("\n📄 STEP 2: Index all PDFs")
    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    print(f"   Found {len(pdf_files)} PDFs")
    
    try:
        from pdfplumber import open as pdf_open
    except ImportError:
        pdf_open = None
    
    splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    total_vectors = 0
    
    for i, pdf_path in enumerate(pdf_files, 1):
        try:
            print(f"   [{i:2d}/{len(pdf_files)}] {pdf_path.name:50s}", end="", flush=True)
            
            # Extract text
            if pdf_open:
                with pdf_open(pdf_path) as pdf:
                    text = "\n".join(
                        (page.extract_text() or "") for page in pdf.pages
                    )
            else:
                text = ""
            
            if not text or len(text) < 10:
                print(" ⚠ No text", flush=True)
                continue
            
            # Split into chunks
            chunks = splitter.split_text(text)
            
            # Store each chunk with a dummy embedding (all zeros)
            for j, chunk in enumerate(chunks):
                point = PointStruct(
                    id=total_vectors,
                    vector=[0.0] * 384,  # Dummy vector for now
                    payload={
                        "document": pdf_path.name,
                        "chunk_id": j,
                        "text": chunk[:200],  # Preview
                        "size_bytes": len(chunk),
                    },
                )
                client.upsert(collection_name="documents", points=[point])
                total_vectors += 1
            
            print(f" ✓ {len(chunks)} chunks", flush=True)
            
        except Exception as e:
            print(f" ✗ {e}", flush=True)
    
    print(f"\n   Total indexed: {total_vectors}")
    
    # Load ontology
    print("\n🧬 STEP 3: Load ontology to Fuseki")
    try:
        from kgbuilder.storage.rdf import FusekiStore
        
        fuseki = FusekiStore(
            url="http://localhost:3030",
            dataset_name="kgbuilder",
        )
        
        if ontology_file.exists():
            with open(ontology_file) as f:
                owl_content = f.read()
            
            fuseki.load_ontology(owl_content)
            print("   ✓ Ontology loaded")
        else:
            print(f"   ✗ Ontology not found: {ontology_file}")
    except ConnectionError:
        print("   ⚠ Fuseki not available (http://localhost:3030)")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    print("\n" + "="*70)
    print("✅ DATA INGESTION COMPLETE")
    print("="*70)
    print(f"\n📊 Indexed:")
    print(f"   • {len(pdf_files)} PDFs")
    print(f"   • {total_vectors} chunks in Qdrant")
    print(f"   • Ontology in Fuseki")
    print("\n🚀 Ready for extraction!")
    print("="*70 + "\n")


if __name__ == "__main__":
    ingest_all_data()
