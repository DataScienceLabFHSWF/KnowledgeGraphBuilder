"""Validation skill: retrieve evidence then validate a VCQ research question."""

from __future__ import annotations

from typing import Any

from kgbuilder.skills.base import AgentSkill
from kgbuilder.tools.cq_sparql_tool import CQSparqlTool
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


def _sparql_question_validation_handler(
    translator: Any,
    runner: Any,
    question: Any,
    store: Any,
) -> Any:
    """Translate a CQ to SPARQL and run it as a functional test (see `evaluation.cq_sparql`)."""
    return CQSparqlTool.handler(translator, runner, question=question, store=store)


QuestionValidationSkill = AgentSkill(
    name="question_validation",
    description=(
        "Retrieve evidence relevant to a VCQ research question, then validate whether "
        "existing KG content correctly/completely answers it."
    ),
    handler=_question_validation_handler,
)

SparqlQuestionValidationSkill = AgentSkill(
    name="question_validation_sparql",
    description=(
        "Translate a VCQ research question into a SPARQL ASK/SELECT query and execute it "
        "against the RDF store as a functional test (CQ4OE/MASEO-style CQ-to-SPARQL check)."
    ),
    handler=_sparql_question_validation_handler,
)
