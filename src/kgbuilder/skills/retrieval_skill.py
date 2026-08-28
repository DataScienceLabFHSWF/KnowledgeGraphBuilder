"""Retrieval + evaluation skill."""

from __future__ import annotations

from typing import Any

from kgbuilder.skills.base import AgentSkill
from kgbuilder.tools.evaluation_tool import EvaluationTool
from kgbuilder.tools.retrieval_tool import RetrievalTool


def _retrieval_skill_handler(retriever: Any, query: str, top_k: int = 10) -> Any:
    """Retrieve documents for a query (delegates to the retrieval tool)."""
    return RetrievalTool.handler(retriever, query=query, top_k=top_k)


def _retrieval_evaluation_skill_handler(
    retrieved_ids: list[str],
    relevant_ids: list[str],
    scores: list[float] | None = None,
) -> Any:
    """Score a retrieval result set against known-relevant document IDs."""
    return EvaluationTool.handler(retrieved_ids=retrieved_ids, relevant_ids=relevant_ids, scores=scores)


RetrievalSkill = AgentSkill(
    name="document_retrieval",
    description="Retrieve documents relevant to a research question or query.",
    handler=_retrieval_skill_handler,
)

RetrievalEvaluationSkill = AgentSkill(
    name="retrieval_evaluation",
    description="Evaluate retrieval quality (recall/precision/ndcg/mrr) against ground truth.",
    handler=_retrieval_evaluation_skill_handler,
)
