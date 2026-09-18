"""Per-module extraction subagent.

Scoped to a single ontology module (e.g. "Radiological Characterization"):
holds that module's ontology class definitions and drives an internal
retrieve -> extract loop over the research questions assigned to it.

Each module subagent is independent and can be bound to a different
retriever/extractor pair, so different modules can use different (e.g.
smaller/cheaper) models without affecting other modules.
"""

from __future__ import annotations

from typing import Any

from kgbuilder.agents.base_agent import BaseAgent
from kgbuilder.agents.question_generator import CQType
from kgbuilder.core.models import ExtractedEntity
from kgbuilder.provenance.rationale_log import RationaleLog
from kgbuilder.skills.module_extraction_skill import ModuleExtractionSkill

# CQ types this subagent acts on: SCQ (scoping -> "what exists") and RCQ
# (relationship -> "how things relate"). VCQ questions are routed to the
# validation stage instead; FCQ/MpCQ are not yet wired to any pipeline stage.
EXTRACTION_CQ_TYPES = frozenset({CQType.SCQ, CQType.RCQ})


class ModuleExtractionAgent(BaseAgent):
    """Runs module-scoped extraction over a list of research questions."""

    def __init__(
        self,
        module_name: str,
        ontology_classes: list[Any],
        retriever: Any,
        extractor: Any,
        top_k: int = 10,
        rationale_log: RationaleLog | None = None,
    ) -> None:
        """Initialize a module extraction subagent.

        Args:
            module_name: Name of the ontology module this agent is scoped to.
            ontology_classes: Ontology class definitions belonging to this module.
            retriever: Retriever used to fetch source documents.
            extractor: EntityExtractor used to extract module-scoped entities.
            top_k: Documents to retrieve per research question.
            rationale_log: Optional `RationaleLog` to record why each entity
                was extracted (which agent, which question). See
                `Planning/SEMANTICS2026_IMPROVEMENT_PLAN.md` Phase A.
        """
        super().__init__(name=f"module_extraction_agent:{module_name}", skills=[ModuleExtractionSkill])
        self.module_name = module_name
        self.ontology_classes = ontology_classes
        self._retriever = retriever
        self._extractor = extractor
        self._top_k = top_k
        self._rationale_log = rationale_log

    def run(self, prompt: str, **kwargs: Any) -> list[ExtractedEntity]:
        """Run module extraction for a single research question (`prompt` = query text)."""
        return self.run_skill(
            "module_extraction",
            retriever=self._retriever,
            extractor=self._extractor,
            query=prompt,
            ontology_classes=self.ontology_classes,
            top_k=self._top_k,
            **kwargs,
        )

    def run_questions(self, questions: list[Any]) -> list[ExtractedEntity]:
        """Run module extraction across the SCQ/RCQ research questions assigned to this module.

        VCQ/FCQ/MpCQ questions (see `CQType`) are skipped here — they are not
        extraction requests and are routed to other pipeline stages instead.
        """
        entities: list[ExtractedEntity] = []
        for question in questions:
            cq_type = getattr(question, "cq_type", CQType.SCQ)
            if cq_type not in EXTRACTION_CQ_TYPES:
                continue
            query_text = getattr(question, "text", question)
            new_entities = self.run(query_text, existing_entities=entities)
            if self._rationale_log is not None:
                question_id = getattr(question, "question_id", None)
                for entity in new_entities:
                    self._rationale_log.record(
                        entity,
                        agent=self.name,
                        action="extracted",
                        reason=f"matched module '{self.module_name}' for question: {query_text}",
                        triggered_by=question_id,
                    )
            entities.extend(new_entities)
        return entities
