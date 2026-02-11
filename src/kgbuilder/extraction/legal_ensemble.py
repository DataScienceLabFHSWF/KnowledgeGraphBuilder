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

import difflib
from dataclasses import dataclass, field

from kgbuilder.core.models import ExtractedEntity, ExtractedRelation, Evidence
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
        # Run rule-based extraction
        rule_entities, rule_relations = self.rule_extractor.extract(text, law_abbr, paragraph_id)

        # Run LLM extraction
        llm_entities, llm_relations = self.llm_extractor.extract(text, paragraph_id, law_abbr)

        # Merge results
        merged_entities = self._merge_entities(rule_entities, llm_entities)
        merged_relations = self._merge_relations(rule_relations, llm_relations)

        return merged_entities, merged_relations

    # ------------------------------------------------------------------
    # Merge logic
    # ------------------------------------------------------------------

    def _merge_entities(
        self,
        rule_entities: list[ExtractedEntity],
        llm_entities: list[ExtractedEntity],
    ) -> list[ExtractedEntity]:
        """Merge entity lists with deduplication and confidence calibration."""
        merged = []
        used_rule = set()
        used_llm = set()

        # First, match rule entities with LLM entities
        for rule_ent in rule_entities:
            best_match = None
            best_score = 0.0

            for i, llm_ent in enumerate(llm_entities):
                if i in used_llm:
                    continue
                if self._entities_match(rule_ent, llm_ent):
                    # Calculate match score (simple label similarity for now)
                    score = self._calculate_entity_similarity(rule_ent, llm_ent)
                    if score > best_score:
                        best_match = (i, llm_ent)
                        best_score = score

            if best_match:
                i, llm_ent = best_match
                # Merge the entities
                merged_ent = self._merge_single_entity(rule_ent, llm_ent)
                merged.append(merged_ent)
                used_rule.add(id(rule_ent))
                used_llm.add(i)
            else:
                # No match, add rule entity with weighted confidence
                rule_ent.confidence *= self.config.rule_weight
                merged.append(rule_ent)
                used_rule.add(id(rule_ent))

        # Add remaining LLM entities
        for i, llm_ent in enumerate(llm_entities):
            if i not in used_llm:
                llm_ent.confidence *= self.config.llm_weight
                merged.append(llm_ent)

        # Filter by minimum confidence
        filtered = [e for e in merged if e.confidence >= self.config.min_confidence]

        return filtered

    def _merge_relations(
        self,
        rule_relations: list[ExtractedRelation],
        llm_relations: list[ExtractedRelation],
    ) -> list[ExtractedRelation]:
        """Merge relation lists with deduplication."""
        merged = []
        used_rule = set()
        used_llm = set()

        # Match rule relations with LLM relations
        for rule_rel in rule_relations:
            best_match = None
            for i, llm_rel in enumerate(llm_relations):
                if i in used_llm and self._relations_match(rule_rel, llm_rel):
                    best_match = (i, llm_rel)
                    break

            if best_match:
                i, llm_rel = best_match
                # Merge the relations
                merged_rel = self._merge_single_relation(rule_rel, llm_rel)
                merged.append(merged_rel)
                used_rule.add(id(rule_rel))
                used_llm.add(i)
            else:
                # No match, add rule relation with weighted confidence
                rule_rel.confidence *= self.config.rule_weight
                merged.append(rule_rel)
                used_rule.add(id(rule_rel))

        # Add remaining LLM relations
        for i, llm_rel in enumerate(llm_relations):
            if i not in used_llm:
                llm_rel.confidence *= self.config.llm_weight
                merged.append(llm_rel)

        # Filter by minimum confidence
        filtered = [r for r in merged if r.confidence >= self.config.min_confidence]

        return filtered

    def _entities_match(self, a: ExtractedEntity, b: ExtractedEntity) -> bool:
        """Check if two entities refer to the same real-world thing."""
        # Simple matching: same normalized label and same type
        a_label = a.label.lower().strip()
        b_label = b.label.lower().strip()

        # Exact match
        if a_label == b_label and a.entity_type == b.entity_type:
            return True

        # Fuzzy match for similar labels
        if a.entity_type == b.entity_type:
            similarity = difflib.SequenceMatcher(None, a_label, b_label).ratio()
            return similarity > 0.8  # 80% similarity threshold

        return False

    def _relations_match(self, a: ExtractedRelation, b: ExtractedRelation) -> bool:
        """Check if two relations are equivalent."""
        return (a.source_label.lower() == b.source_label.lower() and
                a.target_label.lower() == b.target_label.lower() and
                a.relation_type == b.relation_type)

    def _merge_single_entity(self, rule_ent: ExtractedEntity, llm_ent: ExtractedEntity) -> ExtractedEntity:
        """Merge two matching entities."""
        # Use rule-based type if they conflict and config says to prefer rules
        entity_type = rule_ent.entity_type
        if rule_ent.entity_type != llm_ent.entity_type and not self.config.prefer_rule_on_conflict:
            entity_type = llm_ent.entity_type

        # Weighted confidence
        rule_conf = rule_ent.confidence * self.config.rule_weight
        llm_conf = llm_ent.confidence * self.config.llm_weight
        base_confidence = (rule_conf + llm_conf) / 2

        # Boost if both found the same entity
        confidence = min(1.0, base_confidence + self.config.overlap_boost)

        # Combine evidence
        combined_evidence = rule_ent.evidence + llm_ent.evidence

        return ExtractedEntity(
            id=rule_ent.id,  # Keep rule-based ID
            label=rule_ent.label,  # Prefer rule-based label
            entity_type=entity_type,
            confidence=confidence,
            evidence=combined_evidence
        )

    def _merge_single_relation(self, rule_rel: ExtractedRelation, llm_rel: ExtractedRelation) -> ExtractedRelation:
        """Merge two matching relations."""
        # Weighted confidence
        rule_conf = rule_rel.confidence * self.config.rule_weight
        llm_conf = llm_rel.confidence * self.config.llm_weight
        confidence = (rule_conf + llm_conf) / 2

        # Combine evidence
        combined_evidence = rule_rel.evidence + llm_rel.evidence

        return ExtractedRelation(
            id=rule_rel.id,  # Keep rule-based ID
            source_id=rule_rel.source_id,
            source_label=rule_rel.source_label,
            relation_type=rule_rel.relation_type,
            target_id=rule_rel.target_id,
            target_label=rule_rel.target_label,
            confidence=confidence,
            evidence=combined_evidence
        )

    def _calculate_entity_similarity(self, a: ExtractedEntity, b: ExtractedEntity) -> float:
        """Calculate similarity score between two entities."""
        label_sim = difflib.SequenceMatcher(None, a.label.lower(), b.label.lower()).ratio()
        type_match = 1.0 if a.entity_type == b.entity_type else 0.0
        return (label_sim + type_match) / 2
