"""Retrieval evaluation tool wrapping metric functions in retrieval.evaluation."""

from __future__ import annotations

from typing import Any

from kgbuilder.retrieval.evaluation import evaluate_retrieval
from kgbuilder.tools.base import AgentTool


def _evaluation_handler(
    retrieved_ids: list[str],
    relevant_ids: list[str],
) -> Any:
    """Compute retrieval quality metrics (recall/precision/ndcg/mrr)."""
    return evaluate_retrieval(retrieved_ids=retrieved_ids, relevant_ids=set(relevant_ids))


EvaluationTool = AgentTool(
    name="retrieval_evaluation",
    description="Compute recall@k, precision@k, NDCG, and MRR for a retrieval result set.",
    parameters={
        "type": "object",
        "properties": {
            "retrieved_ids": {"type": "array", "items": {"type": "string"}},
            "relevant_ids": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["retrieved_ids", "relevant_ids"],
    },
    handler=_evaluation_handler,
)
