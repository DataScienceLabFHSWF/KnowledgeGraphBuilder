"""Phase 2: FusionRAG with BM25 sparse retrieval and cross-encoder reranking.

Implements advanced retrieval combining:
- Dense retrieval (vector similarity)
- Sparse retrieval (BM25)
- Cross-encoder reranking
- Fusion scoring strategy

See Planning/FUSIONRAG_INTEGRATION.md Section 2 for design.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import ollama
import structlog
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder

from kgbuilder.core import get_base_url

logger = structlog.get_logger(__name__)


@dataclass
class RerankedResult:
    """Result after reranking with cross-encoder."""

    doc_id: str
    content: str
    dense_score: float  # Original dense score
    sparse_score: float  # BM25 score
    fusion_score: float  # Fused score pre-reranking
    rerank_score: float  # Cross-encoder rerank score
    metadata: dict[str, Any]
    retrieval_method: str = "fusion_reranked"


class BM25Retriever:
    """Sparse retrieval using BM25."""

    def __init__(self) -> None:
        """Initialize BM25 retriever."""
        self.tokenized_corpus: list[list[str]] = []
        self.doc_ids: list[str] = []
        self.doc_content: dict[str, str] = {}
        self.bm25: BM25Okapi | None = None

    def index(
        self,
        documents: list[dict[str, Any]],
    ) -> None:
        """Index documents for BM25 retrieval.

        Args:
            documents: List of dicts with 'id' and 'content' keys
        """
        self.doc_ids = []
        self.tokenized_corpus = []
        self.doc_content = {}

        for doc in documents:
            doc_id = doc.get("id", "")
            content = doc.get("content", "")

            if not content:
                continue

            self.doc_ids.append(doc_id)
            self.doc_content[doc_id] = content

            # Simple tokenization: lowercase, split on whitespace
            tokens = content.lower().split()
            self.tokenized_corpus.append(tokens)

        # Build BM25 index
        if self.tokenized_corpus:
            self.bm25 = BM25Okapi(self.tokenized_corpus)
            logger.info("bm25_indexed", doc_count=len(self.doc_ids))

    def search(
        self,
        query: str,
        top_k: int = 10,
    ) -> list[tuple[str, float]]:
        """Search using BM25.

        Args:
            query: Query text
            top_k: Number of results

        Returns:
            List of (doc_id, score) tuples
        """
        if not self.bm25:
            logger.warning("bm25_not_indexed")
            return []

        # Tokenize query
        query_tokens = query.lower().split()

        # Score all documents
        scores = self.bm25.get_scores(query_tokens)

        # Get top-k
        top_indices = np.argsort(scores)[-top_k:][::-1]
        results = []

        for idx in top_indices:
            if scores[idx] > 0:
                doc_id = self.doc_ids[idx]
                results.append((doc_id, float(scores[idx])))

        return results


class CrossEncoderReranker:
    """Rerank candidates using cross-encoder."""

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-12-v2",
    ) -> None:
        """Initialize cross-encoder reranker.

        Args:
            model_name: HuggingFace model name for cross-encoder
        """
        self.model = CrossEncoder(model_name)
        logger.info("cross_encoder_loaded", model=model_name)

    def rerank(
        self,
        query: str,
        candidates: list[tuple[str, str]],
        top_k: int = 5,
    ) -> list[tuple[str, str, float]]:
        """Rerank candidates.

        Args:
            query: Query text
            candidates: List of (doc_id, content) tuples
            top_k: Number of results

        Returns:
            List of (doc_id, content, score) tuples
        """
        if not candidates:
            return []

        # Prepare pairs for cross-encoder
        candidate_pairs = [(query, content) for _, content in candidates]

        # Score all pairs
        scores = self.model.predict(candidate_pairs)

        # Get top-k
        top_indices = np.argsort(scores)[-top_k:][::-1]
        results = []

        for idx in top_indices:
            doc_id, content = candidates[idx]
            results.append((doc_id, content, float(scores[idx])))

        return results


class EnhancedFusionRAGRetriever:
    """Phase 2: Advanced FusionRAG with sparse retrieval and reranking."""

    def __init__(
        self,
        vector_store: Any,  # QdrantStore
        llm_provider: Any,  # OllamaProvider
        embedding_model: str = "qwen3-embedding",
        ollama_base_url: str | None = None,
        top_k: int = 10,
        dense_weight: float = 0.6,
        sparse_weight: float = 0.4,
        use_reranking: bool = True,
    ) -> None:
        """Initialize enhanced FusionRAG retriever.

        Args:
            vector_store: QdrantStore instance
            llm_provider: OllamaProvider instance
            embedding_model: Ollama embedding model
            ollama_base_url: Ollama API URL
            top_k: Number of results
            dense_weight: Weight for dense retrieval in fusion
            sparse_weight: Weight for sparse retrieval in fusion
            use_reranking: Enable cross-encoder reranking
        """
        self.vector_store = vector_store
        self.llm = llm_provider
        self.embedding_model = embedding_model
        self.ollama_base_url = get_base_url(ollama_base_url)
        self.top_k = top_k
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight
        self.use_reranking = use_reranking

        # Initialize Ollama client
        self.ollama_client = ollama.Client(host=ollama_base_url)

        # Initialize BM25 and reranker
        self.bm25 = BM25Retriever()
        self.reranker = CrossEncoderReranker() if use_reranking else None

        # Indexed documents cache
        self._indexed_docs: dict[str, dict[str, Any]] = {}

        logger.info(
            "enhanced_fusion_rag_initialized",
            dense_weight=dense_weight,
            sparse_weight=sparse_weight,
            use_reranking=use_reranking,
        )

    def index_documents(
        self,
        documents: list[dict[str, Any]],
    ) -> None:
        """Index documents for both dense and sparse retrieval.

        Args:
            documents: List of dicts with 'id' and 'content'
        """
        # Cache documents
        self._indexed_docs = {doc["id"]: doc for doc in documents}

        # Index for BM25
        self.bm25.index(documents)

        logger.info("documents_indexed", doc_count=len(documents))

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
    ) -> list[RerankedResult]:
        """Retrieve with fusion and optional reranking.

        Args:
            query: Query text
            top_k: Override default top_k

        Returns:
            List of reranked results
        """
        k = top_k or self.top_k

        # Dense retrieval
        dense_results = self._dense_retrieve(query, k * 2)
        dense_dict = {r["id"]: r for r in dense_results}

        # Sparse retrieval
        sparse_results = self._sparse_retrieve(query, k * 2)
        sparse_dict = {r["id"]: r for r in sparse_results}

        # Fuse results
        fused = self._fuse_results(dense_dict, sparse_dict, k * 2)

        # Rerank if enabled
        if self.use_reranking and self.reranker:
            fused = self._apply_reranking(query, fused, k)

        # Convert to results
        results = [
            RerankedResult(
                doc_id=r["id"],
                content=r["content"],
                dense_score=r.get("dense_score", 0.0),
                sparse_score=r.get("sparse_score", 0.0),
                fusion_score=r["score"],
                rerank_score=r.get("rerank_score", 0.0),
                metadata=r.get("metadata", {}),
            )
            for r in fused[:k]
        ]

        logger.info(
            "retrieval_complete",
            query_len=len(query),
            results_count=len(results),
            used_reranking=self.use_reranking,
        )

        return results

    def _dense_retrieve(
        self,
        query: str,
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Retrieve using dense vectors."""
        try:
            response = self.ollama_client.embed(
                model=self.embedding_model,
                input=query,
            )
            query_embedding = np.array(
                response.embeddings[0] if response.embeddings else [],
                dtype=np.float32,
            )

            results = self.vector_store.search(query_embedding, top_k=top_k)
            docs = []

            for result_id, score, metadata in results:
                docs.append({
                    "id": result_id,
                    "content": metadata.get("content", "") if metadata else "",
                    "dense_score": float(score),
                    "metadata": metadata or {},
                })

            return docs
        except Exception:
            logger.exception("dense_retrieval_failed")
            return []

    def _sparse_retrieve(
        self,
        query: str,
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Retrieve using BM25."""
        try:
            results = self.bm25.search(query, top_k=top_k)
            docs = []

            for doc_id, score in results:
                if doc_id in self._indexed_docs:
                    doc = self._indexed_docs[doc_id]
                    docs.append({
                        "id": doc_id,
                        "content": doc.get("content", ""),
                        "sparse_score": float(score),
                        "metadata": doc.get("metadata", {}),
                    })

            return docs
        except Exception:
            logger.exception("sparse_retrieval_failed")
            return []

    def _fuse_results(
        self,
        dense_dict: dict[str, dict[str, Any]],
        sparse_dict: dict[str, dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Fuse dense and sparse results."""
        # Normalize scores to [0, 1]
        dense_scores = [r["dense_score"] for r in dense_dict.values()]
        sparse_scores = [r["sparse_score"] for r in sparse_dict.values()]

        dense_max = max(dense_scores) if dense_scores else 1.0
        sparse_max = max(sparse_scores) if sparse_scores else 1.0

        # Combine all doc IDs
        all_ids = set(dense_dict.keys()) | set(sparse_dict.keys())

        # Compute fusion scores
        fused = []
        for doc_id in all_ids:
            dense = dense_dict.get(doc_id, {})
            sparse = sparse_dict.get(doc_id, {})

            # Normalize
            d_score = (dense.get("dense_score", 0) / dense_max) if dense_max > 0 else 0
            s_score = (sparse.get("sparse_score", 0) / sparse_max) if sparse_max > 0 else 0

            # Weighted fusion
            fusion_score = self.dense_weight * d_score + self.sparse_weight * s_score

            # Merge metadata
            metadata = {**dense.get("metadata", {}), **sparse.get("metadata", {})}
            content = dense.get("content", "") or sparse.get("content", "")

            fused.append({
                "id": doc_id,
                "content": content,
                "score": fusion_score,
                "dense_score": d_score,
                "sparse_score": s_score,
                "metadata": metadata,
            })

        # Sort by fusion score
        fused.sort(key=lambda x: x["score"], reverse=True)
        return fused[:top_k]

    def _apply_reranking(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Apply cross-encoder reranking."""
        if not self.reranker or not candidates:
            return candidates

        try:
            # Prepare candidate pairs
            pairs = [(c["id"], c["content"]) for c in candidates]

            # Rerank
            reranked = self.reranker.rerank(query, pairs, top_k=top_k)

            # Map back to original candidates
            reranked_dict = {doc_id: score for doc_id, _, score in reranked}

            # Update scores
            for c in candidates:
                if c["id"] in reranked_dict:
                    c["rerank_score"] = reranked_dict[c["id"]]

            # Re-sort by rerank score
            candidates.sort(
                key=lambda x: x.get("rerank_score", x["score"]),
                reverse=True,
            )

            return candidates[:top_k]
        except Exception:
            logger.exception("reranking_failed")
            return candidates
