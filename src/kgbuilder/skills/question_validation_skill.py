"""Validation skill: retrieve evidence then validate a VCQ research question."""

from __future__ import annotations

from typing import Any

from kgbuilder.skills.base import AgentSkill
from kgbuilder.tools.retrieval_tool import RetrievalTool
from kgbuilder.tools.validation_tool import ValidationTool


def _question_validation_handler(
    retriever: Any,
    validator: Any,
    question: Any,
    top_k: int = 10,
) -> Any:
    """Retrieve evidence for a VCQ question, then validate existing KG content against it."""
    retrieved = RetrievalTool.handler(retriever, query=question.text, top_k=top_k)
    return ValidationTool.handler(validator, question=question, evidence=retrieved)


QuestionValidationSkill = AgentSkill(
    name="question_validation",
    description=(
        "Retrieve evidence relevant to a VCQ research question, then validate whether "
        "existing KG content correctly/completely answers it."
    ),
    handler=_question_validation_handler,
)
