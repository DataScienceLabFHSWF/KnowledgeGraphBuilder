#!/usr/bin/env python3
"""Test Phase 2 FusionRAG with reranking vs Phase 1 baseline.

Compares:
- StandardRAGPipeline (Phase 1: dense only)
- EnhancedFusionRAGRetriever (Phase 2: dense + sparse + reranking)

Usage:
    python scripts/test_phase2_fusion.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import time
from typing import Any

import structlog
from dotenv import load_dotenv

logger = structlog.get_logger(__name__)


def main() -> None:
    """Test Phase 2 FusionRAG."""
    import os

    load_dotenv()

    logger.info("initializing_phase2_comparison")

    from kgbuilder.storage.vector import QdrantStore
    from kgbuilder.embedding.ollama import OllamaProvider
    from kgbuilder.rag import StandardRAGPipeline
    from kgbuilder.retrieval import EnhancedFusionRAGRetriever

    try:
        # Initialize components (localhost overrides for local testing)
        llm = OllamaProvider(
            model="qwen3",
            base_url="http://localhost:11434",
        )
        logger.info("llm_initialized", model=llm.model)

        qdrant = QdrantStore(
            url="http://localhost:6333",
            collection_name="kgbuilder",
        )
        logger.info("qdrant_initialized")

        # ===== Phase 1: Standard RAG =====
        logger.info("phase1_standard_rag_test")
        rag_phase1 = StandardRAGPipeline(
            vector_store=qdrant,
            llm_provider=llm,
            embedding_model="qwen3-embedding",
            ollama_base_url="http://localhost:11434",
            top_k=5,
        )

        # ===== Phase 2: Enhanced FusionRAG =====
        logger.info("phase2_enhanced_fusion_rag_test")

        # For Phase 2, we need to index documents in the retriever
        # For now, we'll create an enhanced retriever (without indexing BM25)
        # since we need document corpus to index
        retriever_phase2 = EnhancedFusionRAGRetriever(
            vector_store=qdrant,
            llm_provider=llm,
            embedding_model="qwen3-embedding",
            ollama_base_url="http://localhost:11434",
            top_k=5,
            dense_weight=0.6,
            sparse_weight=0.4,
            use_reranking=True,
        )

        # Test queries
        test_queries = [
            "What is Kernkraftwerk Emsland?",
            "What are the decommissioning requirements?",
            "Who is responsible for facility operations?",
        ]

        logger.info("starting_phase_comparison", query_count=len(test_queries))

        for i, query in enumerate(test_queries, 1):
            logger.info("testing_query", query=query, query_num=i)

            print("\n" + "=" * 70)
            print(f"Query {i}: {query}")
            print("=" * 70)

            # Phase 1: Standard RAG
            try:
                start_time = time.time()
                response_phase1 = rag_phase1.answer(query)
                phase1_time = (time.time() - start_time) * 1000

                print(f"\n[PHASE 1: Standard RAG]")
                print(f"  Retrieved docs: {len(response_phase1.retrieved_docs)}")
                print(f"  Retrieval time: {response_phase1.retrieval_time_ms:.1f}ms")
                print(f"  Generation time: {response_phase1.generation_time_ms:.1f}ms")
                print(f"  Total time: {phase1_time:.1f}ms")
                print(f"  Confidence: {response_phase1.confidence:.2f}")
                print(f"\n  Answer (first 200 chars):")
                print(f"  {response_phase1.answer[:200]}...")

                logger.info(
                    "phase1_complete",
                    query_num=i,
                    retrieval_ms=response_phase1.retrieval_time_ms,
                    generation_ms=response_phase1.generation_time_ms,
                    confidence=response_phase1.confidence,
                )

            except Exception as e:
                logger.exception("phase1_failed", query_num=i)
                print(f"\n[PHASE 1: Standard RAG] ERROR: {e}")

            # Phase 2: Enhanced FusionRAG (retrieval only for now)
            try:
                start_time = time.time()
                results_phase2 = retriever_phase2.retrieve(query, top_k=5)
                phase2_time = (time.time() - start_time) * 1000

                print(f"\n[PHASE 2: Enhanced FusionRAG]")
                print(f"  Retrieved docs: {len(results_phase2)}")
                print(f"  Retrieval time: {phase2_time:.1f}ms")

                # Show retrieval breakdown
                if results_phase2:
                    print(f"\n  Top retrieved document:")
                    top = results_phase2[0]
                    print(f"    Dense score: {top.dense_score:.4f}")
                    print(f"    Sparse score: {top.sparse_score:.4f}")
                    print(f"    Fusion score: {top.fusion_score:.4f}")
                    print(f"    Rerank score: {top.rerank_score:.4f}")
                    if top.content:
                        print(f"    Content (first 150 chars):")
                        print(f"    {top.content[:150]}...")
                    else:
                        print(f"    Content: (empty - old ingestion data)")

                logger.info(
                    "phase2_complete",
                    query_num=i,
                    retrieval_ms=phase2_time,
                    results_count=len(results_phase2),
                )

            except Exception as e:
                logger.exception("phase2_failed", query_num=i)
                print(f"\n[PHASE 2: Enhanced FusionRAG] ERROR: {e}")

            print()

        logger.info("phase_comparison_complete")

        print("\n" + "=" * 70)
        print("PHASE COMPARISON SUMMARY")
        print("=" * 70)
        print("""
Phase 1 (Standard RAG):
  - Dense retrieval only
  - Simple LLM generation
  - Baseline for comparison

Phase 2 (Enhanced FusionRAG):
  - Dense + Sparse (BM25) retrieval
  - Fusion scoring (0.6*dense + 0.4*sparse)
  - Cross-encoder reranking
  - Better ranking quality

Note: Phase 2 BM25 indexing currently disabled.
      Will be enabled in next iteration with full corpus.
""")

    except Exception as e:
        logger.exception("test_failed")
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
