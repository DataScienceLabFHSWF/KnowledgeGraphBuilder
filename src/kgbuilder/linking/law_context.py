"""Law Graph Context Provider.

Provides relevant German legal paragraph text as additional context
during entity extraction in the discovery loop.

When the discovery loop's context_provider is set to LawContextProvider.get_context,
each extracted document chunk is augmented with semantically relevant law paragraphs
retrieved from the Qdrant lawgraph collection.

This allows the LLM extractor to identify regulatory references and entities
that would otherwise be missed in purely technical documents.
"""
from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


class LawContextProvider:
    """Retrieves relevant law paragraph context for a given text chunk.

    Uses semantic search against the Qdrant ``lawgraph`` collection to find
    the most relevant paragraphs from the 17 German federal laws, then formats
    them as a concise context block appended to the extraction prompt.

    Args:
        qdrant_store: QdrantStore connected to the ``lawgraph`` collection.
        embedder: Embedding provider used to encode the query text.
        top_k: Number of law paragraphs to retrieve per document chunk.
        max_chars_per_para: Truncate each retrieved paragraph to this length.
    """

    def __init__(
        self,
        qdrant_store: object,
        embedder: object,
        top_k: int = 3,
        max_chars_per_para: int = 400,
    ) -> None:
        self._store = qdrant_store
        self._embedder = embedder
        self._top_k = top_k
        self._max_chars = max_chars_per_para

    def get_context(self, text: str) -> str:
        """Return relevant law paragraphs as a context string.

        Args:
            text: Source document chunk to find relevant law context for.

        Returns:
            Formatted context string with law paragraphs, or empty string
            if retrieval fails or returns no results.
        """
        try:
            query_vec = self._embedder.embed_query(text)
            results = self._store.search(query_vector=query_vec, limit=self._top_k)
        except Exception as exc:
            logger.warning("law_context_retrieval_failed", error=str(exc)[:120])
            return ""

        if not results:
            return ""

        lines: list[str] = ["--- Relevanter rechtlicher Kontext ---"]
        for hit in results:
            payload = getattr(hit, "payload", {}) or {}
            law = payload.get("law", "")
            para = payload.get("paragraph", "")
            title = payload.get("title", "")
            body = payload.get("text", "")[: self._max_chars]

            header = f"{para} {law}" if para else law
            if title:
                header = f"{header} ({title})"
            lines.append(f"{header}:\n  {body}")

        return "\n".join(lines)
