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
    ) -> None:
        """Initialize a module extraction subagent.

        Args:
            module_name: Name of the ontology module this agent is scoped to.
            ontology_classes: Ontology class definitions belonging to this module.
            retriever: Retriever used to fetch source documents.
            extractor: EntityExtractor used to extract module-scoped entities.
            top_k: Documents to retrieve per research question.
        """
        super().__init__(name=f"module_extraction_agent:{module_name}", skills=[ModuleExtractionSkill])
        self.module_name = module_name
        self.ontology_classes = ontology_classes
        self._retriever = retriever
        self._extractor = extractor
        self._top_k = top_k

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
            entities.extend(self.run(query_text, existing_entities=entities))
        return entities
