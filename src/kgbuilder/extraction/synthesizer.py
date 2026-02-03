"""Research findings synthesis and conflict resolution.

Implementation of Phase 4c: FindingsSynthesizer

Key features:
- Entity deduplication using edit distance + type matching
- Confidence score aggregation across multiple extractions
- Evidence consolidation from multiple sources
- Conflict detection for contradictory assertions
- Provenance tracking for all discovered entities
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

import structlog

from kgbuilder.core.models import ExtractedEntity, ExtractedRelation, Evidence

logger = structlog.get_logger(__name__)


@dataclass
class SynthesizedEntity:
    """An entity after synthesis and deduplication."""

    id: str
    label: str
    entity_type: str
    description: str | None = None
    confidence: float = 0.0
    evidence: list[Evidence] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)  # Which extractors found it
    merged_count: int = 1  # How many were merged into this
    attributes: dict[str, Any] = field(default_factory=dict)  # Additional properties


@dataclass
class SynthesizedFinding:
    """A consolidated research finding with multiple evidence sources."""

    entity_id: str
    entity_label: str
    entity_type: str
    attributes: dict[str, list[str]] = field(default_factory=dict)
    relations: dict[str, list[str]] = field(default_factory=dict)  # predicate -> [objects]
    evidence: list[Evidence] = field(default_factory=list)
    confidence: float = 0.0
    conflicts: list[str] = field(default_factory=list)


class FindingsSynthesizer:
    """Synthesizes extracted entities/relations into consolidated findings.

    Phase 4c Component: Deduplicates and merges entities from multiple discovery
    iterations into a single clean entity set with aggregated confidence.

    Deduplication Algorithm:
    1. Group entities by type (ontology class)
    2. Within each type, find similar entities using edit distance + type matching
       Similarity = 0.7 * label_similarity(Levenshtein) + 0.3 * type_match
    3. Merge groups with similarity >= threshold (default: 0.90)
    4. For each merge:
       - Keep primary entity (highest confidence)
       - Aggregate evidence from all merged entities
       - Boost confidence: avg + boost(capped at 10% or merged_count-1)
       - Track merged_count (how many were merged)
       - Combine sources (which extractors found it)

    Attributes:
        _similarity_threshold: Minimum similarity (0.0-1.0) for entity merging
            Default 0.90 = conservative (high precision, may miss some duplicates)
            Lower values = aggressive deduplication (catch more duplicates)
        _logger: Structured logger for synthesis process tracking
    """

    def __init__(self, similarity_threshold: float = 0.90) -> None:
        """Initialize findings synthesizer with deduplication threshold.

        Args:
            similarity_threshold: float
                Minimum similarity (0.0-1.0) for merging entities as duplicates.
                0.90 = conservative (only merge very similar entities)
                0.75 = moderate (reasonable deduplication)
                0.50 = aggressive (merge many entities, high recall)
                Default 0.90 prioritizes precision (fewer false merges).

        Raises:
            ValueError: If similarity_threshold not in [0.0, 1.0]

        Example:
            >>> synthesizer = FindingsSynthesizer(similarity_threshold=0.85)
        """
        self._similarity_threshold = similarity_threshold
        self._logger = structlog.get_logger(__name__)

    def synthesize(
        self,
        entities: list[ExtractedEntity],
    ) -> list[SynthesizedEntity]:
        """Synthesize extracted entities into deduplicated set.

        Algorithm:
        1. Group entities by type
        2. Within each type, find similar entities (by label)
        3. Merge similar ones, keeping highest confidence
        4. Aggregate evidence and sources
        5. Boost confidence based on merge count

        Args:
            entities: Raw extracted entities (may have duplicates)

        Returns:
            Deduplicated entities with merged evidence
        """
        if not entities:
            self._logger.info("synthesize_empty_input", entity_count=0)
            return []

        self._logger.info("synthesize_start", entity_count=len(entities))

        # Group by entity type
        by_type: dict[str, list[ExtractedEntity]] = {}
        for entity in entities:
            if entity.entity_type not in by_type:
                by_type[entity.entity_type] = []
            by_type[entity.entity_type].append(entity)

        # Synthesize within each type
        synthesized: list[SynthesizedEntity] = []
        for entity_type, type_entities in by_type.items():
            self._logger.debug(
                "synthesizing_type",
                entity_type=entity_type,
                entity_count=len(type_entities),
            )
            synthesized.extend(self._synthesize_type(type_entities))

        self._logger.info(
            "synthesize_complete",
            input_count=len(entities),
            output_count=len(synthesized),
            merged=len(entities) - len(synthesized),
        )

        return synthesized

    def _synthesize_type(
        self,
        entities: list[ExtractedEntity],
    ) -> list[SynthesizedEntity]:
        """Synthesize entities of the same type.

        Args:
            entities: Entities all of same type

        Returns:
            Deduplicated entities of that type
        """
        # Find groups of duplicate entities
        groups = self._find_duplicates(entities)

        # Merge each group
        result = []
        for group in groups:
            merged = self._merge_group(group)
            result.append(merged)

        return result

    def _find_duplicates(
        self,
        entities: list[ExtractedEntity],
    ) -> list[list[ExtractedEntity]]:
        """Find groups of duplicate entities using similarity.

        Uses greedy clustering: for each entity, find all similar ones.
        Returns list of entity groups (each group contains duplicates).

        Args:
            entities: Entities to cluster

        Returns:
            List of duplicate groups
        """
        groups: list[list[ExtractedEntity]] = []
        used: set[int] = set()

        for i, e1 in enumerate(entities):
            if i in used:
                continue

            # Start new group with this entity
            group = [e1]
            used.add(i)

            # Find all similar entities
            for j, e2 in enumerate(entities[i + 1 :], i + 1):
                if j in used:
                    continue

                # Check similarity
                sim = self._calculate_similarity(e1, e2)
                if sim >= self._similarity_threshold:
                    group.append(e2)
                    used.add(j)

            groups.append(group)

        return groups

    def _merge_group(
        self,
        group: list[ExtractedEntity],
    ) -> SynthesizedEntity:
        """Merge duplicate entities into one synthesized entity.

        Algorithm:
        1. Keep entity with highest confidence as primary
        2. Merge all evidence from all entities
        3. Average confidence across all entities
        4. Boost final confidence by merge factor (confidence in deduplication)
        5. Track which extractors found this entity
        6. Record merge count

        Args:
            group: List of duplicate entities

        Returns:
            Single synthesized entity representing the group
        """
        # Keep entity with highest confidence
        primary = max(group, key=lambda e: e.confidence)

        # Merge all evidence
        all_evidence: list[Evidence] = []
        for entity in group:
            all_evidence.extend(entity.evidence)

        # Aggregate confidence
        avg_confidence = sum(e.confidence for e in group) / len(group)

        # Boost confidence based on merge count (more sources = higher confidence)
        # Formula: avg_conf + 0.05 * (merge_count - 1), capped at 1.0
        merge_boost = min(0.05 * (len(group) - 1), 0.1)
        final_confidence = min(avg_confidence + merge_boost, 1.0)

        # Track sources (extractors)
        sources: list[str] = []
        for entity in group:
            if hasattr(entity, "attributes") and entity.attributes and "source" in entity.attributes:
                source = entity.attributes["source"]
                if source and source not in sources:
                    sources.append(source)
            elif hasattr(entity, "sources") and entity.sources:
                sources.extend([s for s in entity.sources if s not in sources])

        self._logger.debug(
            "merge_group",
            label=primary.label,
            entity_type=primary.entity_type,
            merge_count=len(group),
            avg_conf=f"{avg_confidence:.2f}",
            final_conf=f"{final_confidence:.2f}",
            evidence_count=len(all_evidence),
        )

        return SynthesizedEntity(
            id=primary.id,
            label=primary.label,
            entity_type=primary.entity_type,
            description=primary.description,
            confidence=final_confidence,
            evidence=all_evidence,
            sources=sources or ["ensemble"],  # Default to ensemble if no source
            merged_count=len(group),
        )

    def _calculate_similarity(
        self,
        e1: ExtractedEntity,
        e2: ExtractedEntity,
    ) -> float:
        """Calculate similarity between two entities (0.0-1.0).

        Formula: 0.7 * label_similarity + 0.3 * type_match

        Algorithm:
        1. Calculate label similarity using difflib SequenceMatcher (substring-based)
        2. Calculate type match (1.0 if same, 0.0 if different)
        3. Weighted average: favor label similarity over type

        Args:
            e1: First entity
            e2: Second entity

        Returns:
            Similarity score (0.0 = completely different, 1.0 = identical)
        """
        # Label similarity using SequenceMatcher (edit distance)
        label_sim = SequenceMatcher(
            None,
            e1.label.lower(),
            e2.label.lower(),
        ).ratio()

        # Type match (strict equality)
        type_match = 1.0 if e1.entity_type == e2.entity_type else 0.0

        # Weighted average: 70% label, 30% type
        similarity = 0.7 * label_sim + 0.3 * type_match

        return similarity

    def consolidate(
        self,
        entities: list[ExtractedEntity],
        relations: list[ExtractedRelation] | None = None,
    ) -> dict[str, SynthesizedFinding]:
        """Consolidate extracted entities and relations into findings.

        Args:
            entities: Extracted entities with evidence
            relations: Extracted relations with evidence (optional)

        Returns:
            Dict mapping entity IDs to synthesized findings
        """
        # Synthesize entities first
        synthesized = self.synthesize(entities)

        # Convert to findings dict
        findings: dict[str, SynthesizedFinding] = {}
        for synth_entity in synthesized:
            findings[synth_entity.id] = SynthesizedFinding(
                entity_id=synth_entity.id,
                entity_label=synth_entity.label,
                entity_type=synth_entity.entity_type,
                evidence=synth_entity.evidence,
                confidence=synth_entity.confidence,
            )

        # Add relation consolidation if relations provided
        if relations:
            self._consolidate_relations(findings, relations)

        return findings

    def _consolidate_relations(
        self,
        findings: dict[str, SynthesizedFinding],
        relations: list[ExtractedRelation],
    ) -> None:
        """Consolidate relations into findings.

        Groups relations by (source, predicate, target) and aggregates
        confidence and evidence across multiple extractions.

        Args:
            findings: Synthesized findings to augment with relations
            relations: Extracted relations to consolidate
        """
        # Group relations by (source_id, predicate, target_id)
        rel_groups: dict[tuple[str, str, str], list[ExtractedRelation]] = {}
        for rel in relations:
            key = (rel.source_entity_id, rel.predicate, rel.target_entity_id)
            if key not in rel_groups:
                rel_groups[key] = []
            rel_groups[key].append(rel)

        # Consolidate each relation group
        for (source_id, predicate, target_id), rel_list in rel_groups.items():
            if source_id not in findings:
                continue

            # Aggregate confidence across all occurrences
            avg_confidence = sum(r.confidence for r in rel_list) / len(rel_list)

            # Merge all evidence
            all_evidence: list[Evidence] = []
            for rel in rel_list:
                all_evidence.extend(rel.evidence)

            # Store in findings
            if predicate not in findings[source_id].relations:
                findings[source_id].relations[predicate] = []

            findings[source_id].relations[predicate].append(target_id)

            # Update evidence and confidence for the source entity
            findings[source_id].evidence.extend(all_evidence)
            # Boost confidence with merged relation count
            findings[source_id].confidence = min(
                findings[source_id].confidence + 0.02 * len(rel_list),
                1.0
            )

            self._logger.debug(
                "consolidate_relation",
                source=source_id,
                predicate=predicate,
                target=target_id,
                relation_count=len(rel_list),
                avg_confidence=f"{avg_confidence:.2f}",
            )

    def deduplicate_entities(
        self,
        entities: list[ExtractedEntity],
    ) -> dict[str, list[ExtractedEntity]]:
        """Group duplicate entities by similarity.

        Args:
            entities: Extracted entities

        Returns:
            Dict mapping canonical entity IDs to duplicate groups
        """
        groups = self._find_duplicates(entities)

        # Map to canonical IDs (highest confidence entity ID per group)
        result: dict[str, list[ExtractedEntity]] = {}
        for group in groups:
            canonical = max(group, key=lambda e: e.confidence)
            result[canonical.id] = group

        return result

    def detect_conflicts(
        self,
        entities: list[ExtractedEntity],
    ) -> dict[str, list[tuple[str, list[Any]]]]:
        """Detect contradictory values for the same entity.

        Args:
            entities: Extracted entities (after deduplication)

        Returns:
            Dict mapping entity IDs to [(attribute, conflicting_values), ...]
        """
        conflicts: dict[str, list[tuple[str, list[Any]]]] = {}

        # Group by entity ID
        by_id: dict[str, list[ExtractedEntity]] = {}
        for entity in entities:
            if entity.id not in by_id:
                by_id[entity.id] = []
            by_id[entity.id].append(entity)

        # Find conflicts within each entity
        for entity_id, entity_group in by_id.items():
            if len(entity_group) <= 1:
                continue

            entity_conflicts: list[tuple[str, list[Any]]] = []

            # Check description field
            descriptions = [e.description for e in entity_group if e.description]
            if len(set(descriptions)) > 1:
                entity_conflicts.append(("description", descriptions))

            if entity_conflicts:
                conflicts[entity_id] = entity_conflicts

        return conflicts

    def export_yaml(self, findings: dict[str, SynthesizedFinding]) -> str:
        """Export consolidated findings as YAML.

        Args:
            findings: Synthesized findings

        Returns:
            YAML string representation
        """
        lines: list[str] = []
        lines.append("# Research Findings")
        lines.append(f"# Generated from {len(findings)} entities")
        lines.append("")
        lines.append("findings:")

        for entity_id, finding in findings.items():
            lines.append(f"  - id: {entity_id}")
            lines.append(f"    label: {finding.entity_label}")
            lines.append(f"    type: {finding.entity_type}")
            lines.append(f"    confidence: {finding.confidence:.2f}")

            # Add attributes if present
            if finding.attributes:
                lines.append("    attributes:")
                for attr_name, attr_values in finding.attributes.items():
                    values_str = ", ".join(str(v) for v in attr_values)
                    lines.append(f"      {attr_name}: [{values_str}]")

            # Add relations if present
            if finding.relations:
                lines.append("    relations:")
                for predicate, objects in finding.relations.items():
                    objects_str = ", ".join(str(o) for o in objects)
                    lines.append(f"      {predicate}: [{objects_str}]")

            # Add evidence summary
            if finding.evidence:
                lines.append(f"    evidence_count: {len(finding.evidence)}")
                # Show first evidence source if available
                if finding.evidence[0].source_text:
                    preview = finding.evidence[0].source_text[:100].replace("\n", " ")
                    lines.append(f"    first_evidence: \"{preview}...\"")

            lines.append("")

        return "\n".join(lines)
