#!/usr/bin/env python3
"""Test Standard RAG Pipeline with indexed documents.

Tests Phase 1 FusionRAG implementation:
- Document retrieval from Qdrant
- Answer generation with LLM
- End-to-end RAG pipeline

Usage:
    python scripts/test_standard_rag.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import structlog
from dotenv import load_dotenv

logger = structlog.get_logger(__name__)


def main() -> None:
    """Test standard RAG pipeline."""

    load_dotenv()

    logger.info("initializing_standard_rag_pipeline")

    # Initialize components
    from kgbuilder.embedding.ollama import OllamaProvider
    from kgbuilder.rag import StandardRAGPipeline
    from kgbuilder.storage.vector import QdrantStore

    try:
        ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:18134")
        # Initialize LLM provider
        llm = OllamaProvider(
            model="qwen3",
            base_url=ollama_url,  # Local test override
        )
        logger.info("llm_initialized", model=llm.model)

        # Initialize vector store (override QDRANT_URL for localhost)
        qdrant = QdrantStore(
            url="http://localhost:6333",  # Local test override
            collection_name="kgbuilder",
        )
        logger.info("qdrant_initialized")

        # Initialize RAG pipeline
        rag = StandardRAGPipeline(
            vector_store=qdrant,
            llm_provider=llm,
            embedding_model="qwen3-embedding",
            ollama_base_url=ollama_url,
            top_k=5,
        )
        logger.info("standard_rag_pipeline_ready")

        # Test queries
        test_queries = [
            "What is Kernkraftwerk Emsland?",
            "What are the decommissioning requirements?",
            "Who is responsible for facility operations?",
        ]

        logger.info("starting_rag_tests", query_count=len(test_queries))

        for i, query in enumerate(test_queries, 1):
            logger.info("testing_query", query_num=i, query=query)

            try:
                # Run RAG
                response = rag.answer(query)

                logger.info(
                    "rag_response",
                    query_num=i,
                    answer_len=len(response.answer),
                    docs_retrieved=len(response.retrieved_docs),
                    retrieval_ms=response.retrieval_time_ms,
                    generation_ms=response.generation_time_ms,
                    confidence=response.confidence,
                )

                # Print result
                print(f"\n{'='*70}")
                print(f"Query {i}: {query}")
                print(f"{'='*70}")
                print(f"Retrieved {len(response.retrieved_docs)} documents")
                print(f"Confidence: {response.confidence:.2f}")
                print(f"\nAnswer:\n{response.answer}")
                print(f"\nTiming: Retrieval {response.retrieval_time_ms:.1f}ms, Generation {response.generation_time_ms:.1f}ms")

            except Exception as e:
                logger.error("query_failed", query_num=i, error=str(e), exc_info=True)

        logger.info("rag_testing_complete")

    except Exception as e:
        logger.error("failed_to_initialize_rag", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
