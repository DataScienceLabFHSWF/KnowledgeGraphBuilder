"""VCQ-driven validation subagent.

Consumes the CQType.VCQ research questions produced by
`QuestionGenerationAgent` (SCQ/RCQ are handled by extraction subagents
instead — see `ModuleExtractionAgent`). For each VCQ question, retrieves
evidence and asks a validator whether existing KG content correctly/
completely answers it.
"""

from __future__ import annotations

from typing import Any

from kgbuilder.agents.base_agent import BaseAgent
from kgbuilder.agents.question_generator import CQType
from kgbuilder.skills.question_validation_skill import QuestionValidationSkill

VALIDATION_CQ_TYPES = frozenset({CQType.VCQ})


class ValidationAgent(BaseAgent):
    """Runs VCQ-scoped validation over a list of research questions."""

    def __init__(self, retriever: Any, validator: Any, top_k: int = 10) -> None:
        """Initialize the validation subagent.

        Args:
            retriever: Retriever used to fetch evidence for a question.
            validator: Object exposing `validate_question(question, evidence)`.
            top_k: Documents to retrieve per research question.
        """
        super().__init__(name="validation_agent", skills=[QuestionValidationSkill])
        self._retriever = retriever
        self._validator = validator
        self._top_k = top_k

    def run(self, prompt: str, **kwargs: Any) -> Any:
        """Compatibility hook; prefer `run_questions()` for the real workflow."""
        raise NotImplementedError("ValidationAgent.run_questions() is the entry point")

    def run_questions(self, questions: list[Any]) -> list[Any]:
        """Validate the VCQ research questions assigned to this agent.

        Non-VCQ questions (SCQ/RCQ/FCQ/MpCQ) are skipped — they are routed to
        extraction or other pipeline stages instead.
        """
        results: list[Any] = []
        for question in questions:
            cq_type = getattr(question, "cq_type", CQType.SCQ)
            if cq_type not in VALIDATION_CQ_TYPES:
                continue
            results.append(
                self.run_skill(
                    "question_validation",
                    retriever=self._retriever,
                    validator=self._validator,
                    question=question,
                    top_k=self._top_k,
                )
            )
        return results
