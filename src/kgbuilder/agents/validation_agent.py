"""VCQ-driven validation subagent.

Consumes the CQType.VCQ research questions produced by
`QuestionGenerationAgent` (SCQ/RCQ are handled by extraction subagents
instead — see `ModuleExtractionAgent`). For each VCQ question, retrieves
evidence and asks a validator whether existing KG content correctly/
completely answers it. When a SPARQL translator/runner/store are supplied,
prefers an executable CQ-to-SPARQL functional test (SEMANTiCS 2026 Phase B,
CQ4OE/MASEO pattern — see `evaluation.cq_sparql`) and only falls back to the
LLM-judgment path for questions that don't translate cleanly to SPARQL.
"""

from __future__ import annotations

from typing import Any

from kgbuilder.agents.base_agent import BaseAgent
from kgbuilder.agents.question_generator import CQType
from kgbuilder.provenance.rationale_log import RationaleLog
from kgbuilder.skills.question_validation_skill import (
    QuestionValidationSkill,
    SparqlQuestionValidationSkill,
)

VALIDATION_CQ_TYPES = frozenset({CQType.VCQ})


class ValidationAgent(BaseAgent):
    """Runs VCQ-scoped validation over a list of research questions."""

    def __init__(
        self,
        retriever: Any,
        validator: Any,
        top_k: int = 10,
        rationale_log: RationaleLog | None = None,
        sparql_translator: Any | None = None,
        sparql_runner: Any | None = None,
        rdf_store: Any | None = None,
    ) -> None:
        """Initialize the validation subagent.

        Args:
            retriever: Retriever used to fetch evidence for a question.
            validator: Object exposing `validate_question(question, evidence)`.
            top_k: Documents to retrieve per research question.
            rationale_log: Optional `RationaleLog` to record each VCQ
                validation outcome, keyed by `question.question_id`. See
                `Planning/SEMANTICS2026_IMPROVEMENT_PLAN.md` Phase A.
            sparql_translator: Optional `CompetencyQuestionTranslator`. When
                supplied together with `sparql_runner` and `rdf_store`, each
                VCQ question is first attempted as an executable SPARQL
                functional test; the LLM-judgment path (`validator`) is used
                only when translation doesn't produce a usable query.
            sparql_runner: Optional `CQSparqlRunner`.
            rdf_store: Optional RDF store (`storage.rdf.RDFStore`-compatible)
                to execute translated SPARQL against.
        """
        super().__init__(
            name="validation_agent",
            skills=[QuestionValidationSkill, SparqlQuestionValidationSkill],
        )
        self._retriever = retriever
        self._validator = validator
        self._top_k = top_k
        self._rationale_log = rationale_log
        self._sparql_translator = sparql_translator
        self._sparql_runner = sparql_runner
        self._rdf_store = rdf_store

    def run(self, prompt: str, **kwargs: Any) -> Any:
        """Compatibility hook; prefer `run_questions()` for the real workflow."""
        raise NotImplementedError("ValidationAgent.run_questions() is the entry point")

    def _sparql_configured(self) -> bool:
        """Whether enough SPARQL resources are bound to attempt a functional test."""
        return (
            self._sparql_translator is not None
            and self._sparql_runner is not None
            and self._rdf_store is not None
        )

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

            result: Any = None
            used_sparql = False
            if self._sparql_configured():
                sparql_result = self.run_skill(
                    "question_validation_sparql",
                    translator=self._sparql_translator,
                    runner=self._sparql_runner,
                    question=question,
                    store=self._rdf_store,
                )
                if sparql_result.translation.sparql is not None:
                    result = sparql_result
                    used_sparql = True

            if result is None:
                result = self.run_skill(
                    "question_validation",
                    retriever=self._retriever,
                    validator=self._validator,
                    question=question,
                    top_k=self._top_k,
                )

            if self._rationale_log is not None:
                question_id = getattr(question, "question_id", "unknown")
                method = "sparql functional test" if used_sparql else "LLM judgment"
                self._rationale_log.record_for_id(
                    question_id,
                    agent=self.name,
                    action="validated",
                    reason=f"VCQ validation via {method}: {result}",
                    triggered_by=question_id,
                )
            results.append(result)
        return results
