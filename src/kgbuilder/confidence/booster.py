"""Confidence score boosting based on evidence."""

from __future__ import annotations

from dataclasses import replace

from kgbuilder.core.models import ExtractedEntity


class ConfidenceBooster:
    """Boost entity confidence based on evidence and type."""

    # Constants for boosting
    MULTI_SOURCE_BOOST = 0.15
    TYPE_PRIOR_BOOST = 0.05
    MAX_CONFIDENCE = 0.99

    HIGH_CONFIDENCE_TYPES = {"Action", "Parameter"}  # Domain-specific

    def boost_confidence(self, entity: ExtractedEntity) -> ExtractedEntity:
        """Boost confidence based on evidence and type.

        Args:
            entity: Entity to boost.

        Returns:
            Entity with updated confidence score.
        """
        boost = 0.0

        # Multi-source boost
        if entity.evidence:
            unique_sources = len(set(ev.source_id for ev in entity.evidence))
            if unique_sources >= 2:
                boost += self.MULTI_SOURCE_BOOST * (unique_sources - 1) / 2

        # Type-based prior
        if entity.entity_type in self.HIGH_CONFIDENCE_TYPES:
            boost += self.TYPE_PRIOR_BOOST

        # Cap at MAX_CONFIDENCE
        new_confidence = min(self.MAX_CONFIDENCE, entity.confidence + boost)

        return replace(entity, confidence=new_confidence)

    def boost_batch(self, entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
        """Boost confidence for multiple entities.

        Args:
            entities: List of entities to boost.

        Returns:
            List of entities with boosted confidence scores.
        """
        return [self.boost_confidence(e) for e in entities]
