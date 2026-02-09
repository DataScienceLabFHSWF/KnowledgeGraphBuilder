"""Ensemble extractor combining rule-based and LLM extraction for legal text.

Merges results from LegalRuleBasedExtractor (high precision, low recall) and
LegalLLMExtractor (higher recall, variable precision) with conflict resolution
and confidence calibration.

Usage::

    ensemble = LegalEnsembleExtractor(
        rule_extractor=LegalRuleBasedExtractor(),
        llm_extractor=LegalLLMExtractor(llm=provider, ontology=svc),
    )
    entities, relations = ensemble.extract(text, law_abbr="AtG", paragraph_id="§ 7")
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kgbuilder.core.models import ExtractedEntity, ExtractedRelation
from kgbuilder.extraction.legal_llm import LegalLLMExtractor
from kgbuilder.extraction.legal_rules import LegalRuleBasedExtractor


@dataclass
class EnsembleConfig:
    """Configuration for ensemble merging."""

    rule_weight: float = 0.7        # Weight for rule-based results
    llm_weight: float = 0.5         # Weight for LLM results
    overlap_boost: float = 0.15     # Confidence boost when both agree
    min_confidence: float = 0.4     # Minimum to keep after merge
    prefer_rule_on_conflict: bool = True  # Rule-based wins type conflicts


@dataclass
class LegalEnsembleExtractor:
    """Ensemble combining rule-based and LLM extraction for law text.

    Strategy:
    1. Run rule-based extractor (fast, high precision)
    2. Run LLM extractor (slower, higher recall)
    3. Merge: deduplicate, resolve conflicts, boost overlapping extractions
    """

    rule_extractor: LegalRuleBasedExtractor
    llm_extractor: LegalLLMExtractor
    config: EnsembleConfig = field(default_factory=EnsembleConfig)

    def extract(
        self,
        text: str,
        law_abbr: str = "",
        paragraph_id: str = "",
    ) -> tuple[list[ExtractedEntity], list[ExtractedRelation]]:
        """Run ensemble extraction on legal text.

        Args:
            text: Plain text of a law paragraph.
            law_abbr: Source law abbreviation.
            paragraph_id: Source paragraph identifier.

        Returns:
            Tuple of (merged_entities, merged_relations).
        """
        raise NotImplementedError  # TODO: Step 5 implementation

    # ------------------------------------------------------------------
    # Merge logic
    # ------------------------------------------------------------------

    def _merge_entities(
        self,
        rule_entities: list[ExtractedEntity],
        llm_entities: list[ExtractedEntity],
    ) -> list[ExtractedEntity]:
        """Merge entity lists with deduplication and confidence calibration."""
        raise NotImplementedError

    def _merge_relations(
        self,
        rule_relations: list[ExtractedRelation],
        llm_relations: list[ExtractedRelation],
    ) -> list[ExtractedRelation]:
        """Merge relation lists with deduplication."""
        raise NotImplementedError

    def _entities_match(self, a: ExtractedEntity, b: ExtractedEntity) -> bool:
        """Check if two entities refer to the same real-world thing."""
        raise NotImplementedError

    def _relations_match(self, a: ExtractedRelation, b: ExtractedRelation) -> bool:
        """Check if two relations are equivalent."""
        raise NotImplementedError
