"""Enricher protocols for semantic enrichment pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class EnrichedEntity:
    """Entity with enriched attributes."""

    entity_id: str
    label: str
    entity_type: str
    confidence: float
    description: str | None = None
    embedding: list[float] | None = None
    competency_questions: list[str] | None = None
    aliases: list[str] | None = None
    type_scores: dict[str, float] | None = None


@dataclass
class EnrichedRelation:
    """Relation with enriched attributes."""

    relation_id: str
    source_id: str
    target_id: str
    predicate: str
    confidence: float
    description: str | None = None
    embedding: list[float] | None = None
    type_scores: dict[str, float] | None = None


class Enricher(Protocol):
    """Protocol for entity/relation enrichers in the semantic enrichment pipeline."""

    def enrich_entities(self, entities: list[EnrichedEntity]) -> list[EnrichedEntity]:
        """Enrich entities with additional semantic information.

        Args:
            entities: List of entities to enrich

        Returns:
            List of enriched entities

        Raises:
            RuntimeError: If enrichment fails
        """
        ...

    def enrich_relations(self, relations: list[EnrichedRelation]) -> list[EnrichedRelation]:
        """Enrich relations with additional semantic information.

        Args:
            relations: List of relations to enrich

        Returns:
            List of enriched relations

        Raises:
            RuntimeError: If enrichment fails
        """
        ...
