#!/usr/bin/env python3
"""Simple indexing: store PDF text in Qdrant without embeddings (for now)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams


def index_pdfs_simple() -> None:
    """Index PDFs to Qdrant without embeddings."""
    repo_root = Path(__file__).parent.parent
    pdf_dir = repo_root / "data" / "Decommissioning_Files"
    
    print("\n📚 Setting up Qdrant collection...")
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
    
    print("\n📄 Indexing PDFs...")
    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    print(f"   Found {len(pdf_files)} PDFs")
    
    total_chunks = 0
    
    try:
        from pdfplumber import open as pdf_open
    except ImportError:
        print("   ⚠ pdfplumber not installed")
        pdf_open = None
    
    for i, pdf_path in enumerate(pdf_files, 1):
        try:
            print(f"\n   [{i:2d}/{len(pdf_files)}] {pdf_path.name:50s}", end="", flush=True)
            
            # Extract text
            if pdf_open:
                with pdf_open(pdf_path) as pdf:
                    text = "\n".join(
                        (page.extract_text() or "") for page in pdf.pages
                    )
            else:
                try:
                    import pypdf
                    with open(pdf_path, "rb") as f:
                        reader = pypdf.PdfReader(f)
                        text = "\n".join(
                            page.extract_text() or "" for page in reader.pages
                        )
                except:
                    text = ""
            
            if not text or len(text) < 10:
                print(" ⚠ No text", flush=True)
                continue
            
            # Store as dummy vector (all zeros for now)
            point = PointStruct(
                id=total_chunks,
                vector=[0.0] * 384,  # Dummy vector
                payload={
                    "document": pdf_path.name,
                    "text": text[:500],  # Store preview
                    "size_bytes": len(text),
                },
            )
            
            client.upsert(collection_name="documents", points=[point])
            total_chunks += 1
            print(f" ✓ ({len(text):,} bytes)", flush=True)
            
        except Exception as e:
            print(f" ✗ {e}", flush=True)
            continue
    
    print(f"\n   ✅ Total indexed: {total_chunks}/{len(pdf_files)}")


if __name__ == "__main__":
    index_pdfs_simple()
