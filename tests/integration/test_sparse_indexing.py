#!/usr/bin/env python
"""Test script to build sparse index from Qdrant documents.

This script:
1. Connects to Qdrant
2. Creates a FusionRAGRetriever
3. Builds the sparse index by scrolling Qdrant
4. Reports statistics

Useful for verifying sparse retrieval will work in experiments.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kgbuilder.storage.vector import QdrantStore
from kgbuilder.retrieval import FusionRAGRetriever
from kgbuilder.embedding import OllamaProvider

def test_sparse_indexing():
    """Test sparse index building from Qdrant."""
    # Get environment config
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_collection = os.getenv("QDRANT_COLLECTION", "kgbuilder")
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:18134")
    
    print(f"Testing sparse index building...")
    print(f"  Qdrant URL: {qdrant_url}")
    print(f"  Collection: {qdrant_collection}")
    print(f"  Ollama URL: {ollama_url}")
    print()
    
    try:
        # Initialize services
        print("1. Connecting to Qdrant...")
        vector_store = QdrantStore(
            url=qdrant_url,
            collection_name=qdrant_collection
        )
        print("   ✓ Connected to Qdrant")
        
        print("\n2. Initializing LLM provider...")
        llm = OllamaProvider(
            model="qwen3",
            base_url=ollama_url
        )
        print("   ✓ LLM provider initialized")
        
        print("\n3. Creating FusionRAGRetriever...")
        retriever = FusionRAGRetriever(
            qdrant_store=vector_store,
            llm_provider=llm,
            dense_weight=0.7,
            sparse_weight=0.3
        )
        print("   ✓ Retriever created")
        
        print("\n4. Building sparse index from Qdrant...")
        retriever._build_sparse_index_from_qdrant()
        
        if retriever._index_built:
            print(f"   ✓ Sparse index built successfully!")
            print(f"   ✓ Documents indexed: {len(retriever._documents)}")
            
            # Show sample document IDs
            sample_docs = list(retriever._documents.keys())[:5]
            print(f"\n   Sample document IDs:")
            for doc_id in sample_docs:
                content_preview = retriever._documents[doc_id][:50].replace('\n', ' ')
                print(f"     - {doc_id}")
                print(f"       Content: {content_preview}...")
        else:
            print("   ✗ Sparse index not built (no documents found in Qdrant)")
            
        print("\n✓ Test completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n✗ Test failed with error:")
        print(f"  {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_sparse_indexing()
    sys.exit(0 if success else 1)
