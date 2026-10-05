"""Retrieval tool wrapping retriever implementations (FusionRAG / StandardRAG)."""

from __future__ import annotations

from typing import Any

from kgbuilder.tools.base import AgentTool


def _retrieval_handler(retriever: Any, query: str, top_k: int = 10) -> Any:
    """Retrieve documents relevant to a query using the bound retriever."""
    return retriever.retrieve(query=query, top_k=top_k)


RetrievalTool = AgentTool(
    name="document_retrieval",
    description="Retrieve top-k documents relevant to a query using the configured retriever backend.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "top_k": {"type": "integer", "minimum": 1},
        },
        "required": ["query"],
    },
    handler=_retrieval_handler,
)
