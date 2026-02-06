"""Vector store implementations using Qdrant and other backends.

Implementation of Issue #6.1: Vector Store Abstraction

Key features:
- Qdrant vector store for semantic search
- Embedding retrieval and management
- Collection management and schema definition
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray


@runtime_checkable
class VectorStore(Protocol):
    """Protocol for vector database implementations."""

    def store(
        self,
        ids: list[str],
        embeddings: list[NDArray[np.float32]],
        metadata: list[dict[str, Any]] | None = None,
    ) -> None:
        """Store embeddings with optional metadata.

        Args:
            ids: Document/entity IDs
            embeddings: Embedding vectors
            metadata: Optional metadata dicts
        """
        ...

    def search(
        self,
        query_embedding: NDArray[np.float32],
        top_k: int = 10,
        score_threshold: float | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        """Search for similar embeddings.

        Args:
            query_embedding: Query vector
            top_k: Number of results
            score_threshold: Optional min score

        Returns:
            List of (id, score, metadata)
        """
        ...

    def delete(self, ids: list[str]) -> None:
        """Delete embeddings by ID.

        Args:
            ids: IDs to delete
        """
        ...


class QdrantStore:
    """Qdrant vector database store implementation.

    TODO (Implementation):
    - [ ] Implement __init__() with Qdrant connection
    - [ ] Implement store() to upsert embeddings
    - [ ] Implement search() with cosine similarity
    - [ ] Implement delete() with ID batching
    - [ ] Implement collection lifecycle (create, list, delete)
    - [ ] Add batch operations for efficiency
    - [ ] Add error handling and retry logic
    - [ ] Add unit tests with mock Qdrant server

    Dependencies: qdrant-client>=2.0.0

    See Planning/INTERFACES.md Section 6.1 for protocol definition.
    See Planning/ISSUES_BACKLOG.md Issue #6.1 for acceptance criteria.
    """

    def __init__(
        self,
        url: str = "http://localhost:6333",
        api_key: str | None = None,
        collection_name: str = "kgbuilder",
    ) -> None:
        """Initialize Qdrant store.

        Args:
            url: Qdrant server URL
            api_key: Optional API key
            collection_name: Collection to use/create
        """
        import httpx
        from qdrant_client import QdrantClient

        self.url = url
        self.api_key = api_key
        self.collection_name = collection_name
        self.client = QdrantClient(url=url, api_key=api_key)
        self.http_client = httpx.Client(base_url=url)
        self._verify_connection()
        self._point_counter = 0

    def _verify_connection(self) -> None:
        """Verify Qdrant connection is working."""
        self.client.get_collections()

    def get_points_count(self) -> int:
        """Get number of points in the collection.
        
        Returns:
            Number of points, or 0 if collection doesn't exist
        """
        try:
            info = self.client.get_collection(self.collection_name)
            return info.points_count or 0
        except Exception:
            return 0

    def store(
        self,
        ids: list[str],
        embeddings: list[NDArray[np.float32]],
        metadata: list[dict[str, Any]] | None = None,
    ) -> None:
        """Store embeddings in Qdrant.

        Args:
            ids: Document/entity IDs
            embeddings: Embedding vectors
            metadata: Optional metadata dicts
        """
        from qdrant_client.models import Distance, PointStruct, VectorParams

        metadata = metadata or [{} for _ in ids]

        # Create collection if needed
        try:
            self.client.get_collection(self.collection_name)
        except Exception:
            vector_size = len(embeddings[0]) if embeddings else 768
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )

        # Convert to Qdrant points with sequential IDs
        points = []
        for i in range(len(ids)):
            self._point_counter += 1
            points.append(
                PointStruct(
                    id=self._point_counter,
                    vector=embeddings[i].tolist(),
                    payload={"id": ids[i], **metadata[i]},
                )
            )

        # Upsert points
        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )

    def search(
        self,
        query_embedding: NDArray[np.float32],
        top_k: int = 10,
        score_threshold: float | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        """Search Qdrant collection.

        Args:
            query_embedding: Query vector
            top_k: Number of results
            score_threshold: Optional min score

        Returns:
            List of (id, score, metadata)
        """
        import json

        # Use REST API for search
        search_request = {
            "vector": query_embedding.tolist(),
            "limit": top_k,
            "with_payload": True,
        }
        if score_threshold is not None:
            search_request["score_threshold"] = score_threshold

        response = self.http_client.post(
            f"/collections/{self.collection_name}/points/search",
            json=search_request,
        )

        if response.status_code != 200:
            return []

        data = response.json()
        results = data.get("result", [])

        return [
            (
                result["payload"].get("id", f"point_{result['id']}"),
                result["score"],
                {k: v for k, v in result["payload"].items() if k != "id"},
            )
            for result in results
        ]

    def delete(self, ids: list[str]) -> None:
        """Delete embeddings from Qdrant.

        Args:
            ids: IDs to delete
        """
        # Filter by payload ID to delete
        for str_id in ids:
            try:
                self.client.delete(
                    collection_name=self.collection_name,
                    points_selector={
                        "filter": {
                            "must": [{"key": "id", "match": {"value": str_id}}]
                        }
                    },
                )
            except Exception:
                pass

    def create_collection(
        self,
        vector_size: int,
        distance_metric: str = "cosine",
    ) -> None:
        """Create or verify collection exists.

        Args:
            vector_size: Dimensionality of embeddings
            distance_metric: Distance metric (cosine, euclidean, dot)
        """
        from qdrant_client.models import Distance, VectorParams

        distance_map = {
            "cosine": Distance.COSINE,
            "euclidean": Distance.EUCLID,
            "dot": Distance.DOT,
        }

        try:
            self.client.get_collection(self.collection_name)
        except Exception:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=distance_map.get(distance_metric, Distance.COSINE),
                ),
            )

    def list_collections(self) -> list[str]:
        """List all collections in Qdrant.

        Returns:
            Collection names
        """
        collections = self.client.get_collections()
        return [coll.name for coll in collections.collections]


class ChromaStore:
    """ChromaDB vector store implementation (alternative backend).

    TODO (Implementation):
    - [ ] Implement ChromaDB integration
    - [ ] Support in-memory and persistent modes
    - [ ] Implement same protocol as QdrantStore

    Dependencies: chromadb>=0.4.0
    """

    pass


class MilvusStore:
    """Milvus vector store implementation (alternative backend).

    TODO (Implementation):
    - [ ] Implement Milvus integration
    - [ ] Support cloud and self-hosted deployment
    - [ ] Implement same protocol as QdrantStore

    Dependencies: pymilvus>=2.0.0
    """

    pass
