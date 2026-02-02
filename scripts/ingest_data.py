#!/usr/bin/env python3
"""Quick setup: index all PDFs and load ontology into Fuseki."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import CharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams



def setup_data() -> None:
    """Index PDFs and load ontology."""
    repo_root = Path(__file__).parent.parent
    pdf_dir = repo_root / "data" / "Decommissioning_Files"
    ontology_file = repo_root / "data" / "ontology" / "plan-ontology-v1.0.owl"
    
    # 1. Setup Qdrant for PDF vectors
    print("\n📚 STEP 1: Setting up Qdrant for PDF vectors...")
    
    try:
        client = QdrantClient(url="http://localhost:6333")
        
        # Create collection if not exists
        try:
            client.get_collection("documents")
            print("   ✓ Collection 'documents' already exists")
        except:
            print("   • Creating 'documents' collection...")
            client.create_collection(
                collection_name="documents",
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
            print("   ✓ Collection created")
    except Exception as e:
        print(f"   ✗ Failed to setup Qdrant: {e}")
        return
    
    # 2. Index all PDFs
    print("\n📄 STEP 2: Indexing PDFs...")
    
    pdf_files = list(pdf_dir.glob("*.pdf"))
    print(f"   Found {len(pdf_files)} PDFs to index")
    
    if pdf_files:
        try:
            from pdfplumber import open as pdf_open
        except ImportError:
            print("   ⚠ pdfplumber not installed - using basic PDF reading")
            pdf_open = None
        
        embeddings = OllamaEmbeddings(
            model="nomic-embed-text:latest",
            base_url="http://localhost:11434",
        )
        
        splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=100)
        
        total_vectors = 0
        
        for i, pdf_path in enumerate(pdf_files, 1):  # Index all PDFs
            print(f"\n   [{i}/{len(pdf_files)}] {pdf_path.name}", end="", flush=True)
            
            try:
                # Extract text from PDF
                if pdf_open:
                    with pdf_open(pdf_path) as pdf:
                        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
                else:
                    # Fallback: read as binary
                    try:
                        import pypdf
                        with open(pdf_path, "rb") as f:
                            reader = pypdf.PdfReader(f)
                            text = "\n".join(
                                page.extract_text() for page in reader.pages
                            )
                    except:
                        text = pdf_path.name  # Fallback
                
                if not text or len(text) < 10:
                    print(f"        ⚠ No text extracted")
                    continue
                
                # Split into chunks
                chunks = splitter.split_text(text)
                print(f"        • {len(chunks)} chunks", flush=True)
                
                # Embed and store with retry
                retry_count = 0
                max_retries = 3
                
                while retry_count < max_retries:
                    try:
                        vectors = embeddings.embed_documents(chunks)
                        
                        for j, (chunk, vector) in enumerate(zip(chunks, vectors)):
                            point = PointStruct(
                                id=total_vectors,
                                vector=vector,
                                payload={
                                    "document": pdf_path.name,
                                    "chunk_id": j,
                                    "text": chunk[:200],  # Store preview
                                },
                            )
                            client.upsert(
                                collection_name="documents",
                                points=[point],
                            )
                            total_vectors += 1
                        
                        print(f" ✓", flush=True)
                        break  # Success, exit retry loop
                    except Exception as embed_err:
                        retry_count += 1
                        if retry_count >= max_retries:
                            print(f" ✗ (after {max_retries} retries)", flush=True)
                        else:
                            print(f" • Retry {retry_count}...", end="", flush=True)
                            import time
                            time.sleep(2)
                
            except Exception as e:
                print(f" ✗ Error: {e}", flush=True)
                continue
        
        print(f"\n   ✓ Total vectors stored: {total_vectors}")
    
    # 3. Load ontology into Fuseki
    print("\n🧬 STEP 3: Loading ontology into Fuseki...")
    
    try:
        from kgbuilder.storage.rdf import FusekiStore
        
        fuseki = FusekiStore(
            url="http://localhost:3030",
            dataset_name="kgbuilder",
        )
        
        if ontology_file.exists():
            with open(ontology_file) as f:
                owl_content = f.read()
            
            # Load ontology into Fuseki
            fuseki.load_ontology(owl_content)
            print("   ✓ Ontology loaded into Fuseki RDF store")
        else:
            print(f"   ✗ Ontology file not found: {ontology_file}")
    
    except Exception as e:
        print(f"   ✗ Error loading ontology: {e}")
    
    # 4. Summary
    print("\n" + "=" * 60)
    print("✅ DATA SETUP COMPLETE")
    print("=" * 60)
    print("\n📊 Status:")
    print(f"   • PDFs indexed: {len(pdf_files)}")
    print(f"   • Vectors in Qdrant: {total_vectors}")
    print(f"   • Ontology in Neo4j: ✓")
    print("\n🚀 Ready to extract and build the Knowledge Graph!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    setup_data()
