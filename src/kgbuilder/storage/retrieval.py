"""Semantic search and retrieval using LangChain + Qdrant.

Implementation of Issue #6.1: Vector Store + Retrieval

Key features:
- LangChain integration for standardized vector store interface
- Qdrant backend for semantic search
- Embedding persistence and retrieval
- Integration with document chunks and entity embeddings
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray


class SemanticRetriever:
    """Unified retriever using LangChain + Qdrant.

    Provides semantic search over document chunks and entities.
    """

    def __init__(
        self,
        qdrant_url: str = "http://localhost:6333",
        collection_name: str = "kgbuilder",
        embedding_provider: Any | None = None,
    ) -> None:
        """Initialize semantic retriever.

        Args:
            qdrant_url: Qdrant server URL
            collection_name: Collection name for vectors
            embedding_provider: Optional embedding provider (defaults to mock)
        """
        from langchain_community.vectorstores import Qdrant

        self.qdrant_url = qdrant_url
        self.collection_name = collection_name
        self.embedding_provider = embedding_provider

        # Use LangChain's Qdrant wrapper
        self._vector_store = None
        self._initialized = False

    def _ensure_initialized(self, embeddings: Any) -> None:
        """Lazy initialize vector store with embeddings."""
        if not self._initialized:
            from langchain_community.vectorstores import Qdrant

            self._vector_store = Qdrant.from_existing_collection(
                embedding=embeddings,
                collection_name=self.collection_name,
                url=self.qdrant_url,
            )
            self._initialized = True

    def add_documents(
        self,
        texts: list[str],
        metadata: list[dict[str, Any]] | None = None,
        embeddings: Any | None = None,
    ) -> list[str]:
        """Add documents/chunks to retrieval index.

        Args:
            texts: Document texts
            metadata: Optional metadata for each text
            embeddings: Embedding provider instance

        Returns:
            Document IDs
        """
        from kgbuilder.storage.vector import QdrantStore

        if embeddings is None:
            embeddings = self.embedding_provider

        metadata = metadata or [{} for _ in texts]

        # Get embeddings for all texts
        embeddings_list = embeddings.embed_documents(texts)
        
        # Initialize Qdrant store if needed
        if not self._initialized:
            self._vector_store = QdrantStore(
                url=self.qdrant_url,
                collection_name=self.collection_name
            )
            self._vector_store.connect()
            self._initialized = True
        
        # Store documents with embeddings
        doc_ids = []
        for i, (text, meta, emb) in enumerate(zip(texts, metadata, embeddings_list)):
            doc_id = f"doc_{i}"
            doc_ids.append(doc_id)
            
            # Store as point in Qdrant
            self._vector_store.store(
                texts=[text],
                embeddings=[emb],
                metadata=[{**meta, "doc_id": doc_id}]
            )
        
        return doc_ids

    def search(
        self,
        query: str,
        top_k: int = 5,
        embeddings: Any | None = None,
        score_threshold: float | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        """Semantic search for similar documents.

        Args:
            query: Query text
            top_k: Number of results
            embeddings: Embedding provider
            score_threshold: Optional minimum score threshold

        Returns:
            List of (document_text, similarity_score, metadata)
        """
        if embeddings is None:
            embeddings = self.embedding_provider

        self._ensure_initialized(embeddings)

        if not self._vector_store:
            return []

        # Search with similarity scores
        results = self._vector_store.similarity_search_with_score(
            query,
            k=top_k,
        )

        # Filter by threshold if provided
        if score_threshold is not None:
            results = [(doc, score) for doc, score in results if score >= score_threshold]

        return [
            (doc.page_content, score, doc.metadata) for doc, score in results
        ]

    def search_by_embedding(
        self,
        embedding: NDArray[np.float32],
        top_k: int = 5,
        score_threshold: float | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        """Search by embedding vector directly.

        Args:
            embedding: Query embedding vector
            top_k: Number of results
            score_threshold: Optional minimum score threshold

        Returns:
            List of (document_text, similarity_score, metadata)
        """
        from qdrant_client import QdrantClient

        client = QdrantClient(self.qdrant_url)

        # Use Qdrant search API directly
        results = client.search(
            collection_name=self.collection_name,
            query_vector=embedding.tolist(),
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True,
        )

        return [
            (
                result.payload.get("page_content", ""),
                result.score,
                {k: v for k, v in result.payload.items() if k != "page_content"},
            )
            for result in results
        ]


__all__ = ["SemanticRetriever"]
