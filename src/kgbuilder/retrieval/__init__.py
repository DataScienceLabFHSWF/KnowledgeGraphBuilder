"""FusionRAG Retriever - Multi-strategy retrieval for KG construction.

Implements hybrid retrieval combining:
- Dense vector similarity (Qdrant)
- Sparse keyword search (BM25)  
- Reranking with semantic relevance

See Planning/FUSIONRAG_INTEGRATION.md for architecture.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Result from retrieval operation."""

    doc_id: str
    content: str
    score: float
    metadata: dict[str, Any] | None = None
    retrieval_method: str = "unknown"  # dense, sparse, reranked


class FusionRAGRetriever:
    """Multi-strategy retriever combining dense, sparse, and semantic ranking.

    Phase 1 of FusionRAG for Knowledge Graph construction.
    """

    def __init__(
        self,
        qdrant_store: Any,
        llm_provider: Any,
        dense_weight: float = 0.6,
        sparse_weight: float = 0.4,
        top_k: int = 10,
    ) -> None:
        """Initialize FusionRAG retriever.

        Args:
            qdrant_store: QdrantStore instance for dense retrieval
            llm_provider: LLMProvider for semantic understanding
            dense_weight: Weight for dense retrieval in fusion (0.0-1.0)
            sparse_weight: Weight for sparse retrieval in fusion
            top_k: Default number of results to return
        """
        self.qdrant = qdrant_store
        self.llm = llm_provider
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight
        self.top_k = top_k

        # Sparse retrieval: simple BM25-like keyword matching
        self._index_built = False
        self._documents: dict[str, str] = {}  # doc_id -> content
        self._metadata: dict[str, dict[str, Any]] = {}  # doc_id -> metadata

        logger.info(
            "fusionrag_retriever_initialized",
            dense_weight=dense_weight,
            sparse_weight=sparse_weight,
        )

    def index_documents(
        self,
        documents: dict[str, str],
        metadata: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """Index documents for sparse retrieval.

        Args:
            documents: Mapping of doc_id -> content
            metadata: Optional metadata for each document
        """
        self._documents = documents
        self._metadata = metadata or {doc_id: {} for doc_id in documents}
        self._index_built = True

        logger.info("documents_indexed_for_fusion", count=len(documents))

    def retrieve(
        self,
        query: str,
        query_embedding: NDArray[np.float32] | None = None,
        top_k: int | None = None,
    ) -> list[RetrievalResult]:
        """Retrieve documents using fusion strategy.

        Args:
            query: Text query
            query_embedding: Pre-computed query embedding (optional)
            top_k: Number of results to return

        Returns:
            List of retrieval results ranked by fusion score
        """
        top_k = top_k or self.top_k

        # 1. Dense retrieval
        dense_results = self._dense_retrieve(query, query_embedding, top_k * 2)

        # 2. Sparse retrieval
        sparse_results = self._sparse_retrieve(query, top_k * 2)

        # 3. Fuse and rerank
        fused = self._fuse_results(dense_results, sparse_results)
        ranked = sorted(fused.values(), key=lambda r: r.score, reverse=True)[:top_k]

        logger.info(
            "retrieval_complete",
            query_len=len(query),
            dense_count=len(dense_results),
            sparse_count=len(sparse_results),
            final_count=len(ranked),
        )

        return ranked

    def retrieve_with_expansion(
        self,
        query: str,
        query_embedding: NDArray[np.float32] | None = None,
        top_k: int | None = None,
    ) -> list[RetrievalResult]:
        """Retrieve with query expansion using LLM.

        Generates alternative queries to improve recall.

        Args:
            query: Original query
            query_embedding: Pre-computed embedding
            top_k: Number of results

        Returns:
            Expanded retrieval results
        """
        top_k = top_k or self.top_k

        # Generate query variants
        variants = self._expand_query(query)
        logger.info("query_expanded", original=query, variants=len(variants))

        # Retrieve for each variant
        all_results: dict[str, RetrievalResult] = {}

        for variant_query in [query] + variants:
            results = self.retrieve(variant_query, top_k=top_k * 2)
            for result in results:
                if result.doc_id not in all_results:
                    all_results[result.doc_id] = result
                else:
                    # Average scores for documents found in multiple queries
                    existing = all_results[result.doc_id]
                    existing.score = (existing.score + result.score) / 2

        # Return top-k
        ranked = sorted(all_results.values(), key=lambda r: r.score, reverse=True)[
            :top_k
        ]
        return ranked

    def _dense_retrieve(
        self,
        query: str,
        query_embedding: NDArray[np.float32] | None = None,
        top_k: int = 20,
    ) -> dict[str, RetrievalResult]:
        """Dense vector similarity retrieval."""
        try:
            if query_embedding is None:
                # Use LLM to embed query
                query_embedding = self.llm.embed_query(query)

            results = self.qdrant.search(query_embedding, top_k=top_k)

            dense_results = {}
            for i, result in enumerate(results):
                # Normalize score to [0, 1] (assuming cosine similarity)
                score = max(0.0, min(1.0, (result.score + 1.0) / 2.0))
                dense_results[result.id] = RetrievalResult(
                    doc_id=result.id,
                    content=result.content,
                    score=score,
                    metadata=result.metadata,
                    retrieval_method="dense",
                )

            logger.debug("dense_retrieval_complete", count=len(dense_results))
            return dense_results

        except Exception as e:
            logger.error("dense_retrieval_failed", error=str(e))
            return {}

    def _sparse_retrieve(
        self,
        query: str,
        top_k: int = 20,
    ) -> dict[str, RetrievalResult]:
        """Sparse keyword-based retrieval (BM25-like)."""
        if not self._index_built:
            logger.warning("documents_not_indexed_for_sparse_retrieval")
            return {}

        try:
            # Simple keyword matching
            query_terms = set(query.lower().split())
            scores: dict[str, float] = {}

            for doc_id, content in self._documents.items():
                doc_terms = set(content.lower().split())
                # Jaccard similarity
                intersection = len(query_terms & doc_terms)
                union = len(query_terms | doc_terms)

                if union > 0:
                    score = intersection / union
                    if score > 0:
                        scores[doc_id] = score

            # Sort and return top-k
            sparse_results = {}
            for doc_id, score in sorted(
                scores.items(), key=lambda x: x[1], reverse=True
            )[:top_k]:
                sparse_results[doc_id] = RetrievalResult(
                    doc_id=doc_id,
                    content=self._documents[doc_id],
                    score=score,
                    metadata=self._metadata.get(doc_id),
                    retrieval_method="sparse",
                )

            logger.debug("sparse_retrieval_complete", count=len(sparse_results))
            return sparse_results

        except Exception as e:
            logger.error("sparse_retrieval_failed", error=str(e))
            return {}

    def _fuse_results(
        self,
        dense_results: dict[str, RetrievalResult],
        sparse_results: dict[str, RetrievalResult],
    ) -> dict[str, RetrievalResult]:
        """Fuse dense and sparse results with weighted scoring."""
        fused: dict[str, RetrievalResult] = {}

        # Add dense results
        for doc_id, result in dense_results.items():
            fused[doc_id] = RetrievalResult(
                doc_id=result.doc_id,
                content=result.content,
                score=result.score * self.dense_weight,
                metadata=result.metadata,
                retrieval_method="fused",
            )

        # Add/combine sparse results
        for doc_id, result in sparse_results.items():
            if doc_id in fused:
                # Combine with existing dense score
                fused[doc_id].score += result.score * self.sparse_weight
            else:
                # Add new sparse result
                fused[doc_id] = RetrievalResult(
                    doc_id=result.doc_id,
                    content=result.content,
                    score=result.score * self.sparse_weight,
                    metadata=result.metadata,
                    retrieval_method="fused",
                )

        # Normalize scores to [0, 1]
        if fused:
            max_score = max(r.score for r in fused.values())
            for result in fused.values():
                result.score = result.score / max_score if max_score > 0 else 0.0

        return fused

    def _expand_query(self, query: str) -> list[str]:
        """Generate alternative query formulations.

        Uses LLM to rephrase query for better recall.
        """
        try:
            prompt = f"""Generate 2-3 alternative ways to ask this question that might retrieve different relevant documents:

Original question: {query}

Alternative questions:"""

            response = self.llm.generate(prompt, max_tokens=200)
            variants = [q.strip() for q in response.split("\n") if q.strip()]
            return variants[:2]  # Limit to 2 variants

        except Exception as e:
            logger.debug("query_expansion_failed", error=str(e))
            return []


__all__ = ["FusionRAGRetriever", "RetrievalResult"]
