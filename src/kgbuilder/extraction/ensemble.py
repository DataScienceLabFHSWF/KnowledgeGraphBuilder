"""Ensemble entity extraction combining multiple extraction strategies.

Combines multiple entity extractors using voting and confidence-based ranking.

Key features:
- Run multiple extractors in parallel
- Combine predictions via voting
- Confidence adjustment based on agreement
- Fallback strategies (if one method fails)
- Flexible configuration
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from kgbuilder.core.models import ExtractedEntity
from kgbuilder.extraction.entity import OntologyClassDef

logger = logging.getLogger(__name__)


class EnsembleExtractor:
    """Ensemble entity extractor combining multiple strategies.

    Combines predictions from multiple EntityExtractor implementations:
    - Run all extractors in parallel
    - Merge results by (label, type)
    - Adjust confidence based on voting
    - Higher confidence when multiple methods agree
    """

    def __init__(self, extractors: list[Any]) -> None:
        """Initialize ensemble with multiple extractors.

        Args:
            extractors: List of EntityExtractor instances to combine
        """
        if not extractors:
            raise ValueError("At least one extractor required")

        self.extractors = extractors
        self.names = [e.__class__.__name__ for e in extractors]
        logger.info(
            f"✓ Initialized EnsembleExtractor with {len(extractors)} extractors: "
            f"{', '.join(self.names)}"
        )

    def extract(
        self,
        text: str,
        ontology_classes: list[OntologyClassDef],
        existing_entities: list[ExtractedEntity] | None = None,
    ) -> list[ExtractedEntity]:
        """Extract entities using ensemble of methods.

        Strategy:
        1. Run all extractors
        2. Collect results by (label, entity_type)
        3. Merge with confidence voting:
           - 2+ extractors agree → high confidence (0.9)
           - 1 extractor → medium confidence (keep as-is)
        4. Return merged entities

        Args:
            text: Source text to extract from
            ontology_classes: Valid entity types from ontology
            existing_entities: Known entities for deduplication

        Returns:
            List of extracted entities with merged confidence scores
        """
        if not text or not text.strip():
            logger.debug("Empty text provided to ensemble extractor")
            return []

        logger.info(f"Running ensemble extraction with {len(self.extractors)} methods")

        # Run all extractors
        all_results: dict[tuple[str, str], list[ExtractedEntity]] = defaultdict(list)
        failed_extractors = []

        for extractor in self.extractors:
            try:
                logger.debug(f"Running {extractor.__class__.__name__}...")
                results = extractor.extract(
                    text=text,
                    ontology_classes=ontology_classes,
                    existing_entities=existing_entities,
                )
                logger.debug(f"  → {len(results)} entities")

                # Group by (label, type)
                for entity in results:
                    key = (entity.label.lower().strip(), entity.entity_type)
                    all_results[key].append(entity)

            except Exception as e:
                logger.warning(f"Extractor {extractor.__class__.__name__} failed: {e}")
                failed_extractors.append(extractor.__class__.__name__)

        # Log failures
        if failed_extractors:
            logger.warning(
                f"Failed extractors: {', '.join(failed_extractors)} "
                f"({len(failed_extractors)}/{len(self.extractors)})"
            )

        # Merge results with voting
        merged_entities = []
        for (label, entity_type), entities in all_results.items():
            # Calculate voting confidence
            num_votes = len(entities)
            avg_confidence = sum(e.confidence for e in entities) / num_votes

            # Boost confidence if multiple methods agree
            if num_votes > 1:
                # Agreement boost: more methods agree → higher confidence
                agreement_boost = min(0.25, (num_votes - 1) * 0.1)
                merged_confidence = min(0.99, avg_confidence + agreement_boost)
                logger.debug(
                    f"Merged {num_votes} votes for '{label}' "
                    f"(avg={avg_confidence:.2f}, merged={merged_confidence:.2f})"
                )
            else:
                merged_confidence = avg_confidence

            # Use best entity as base (highest original confidence)
            best_entity = max(entities, key=lambda e: e.confidence)

            # Create merged entity with updated confidence
            merged = ExtractedEntity(
                id=best_entity.id,
                label=best_entity.label,
                entity_type=best_entity.entity_type,
                description=best_entity.description,
                confidence=merged_confidence,
                aliases=best_entity.aliases,
                properties={
                    **best_entity.properties,
                    "ensemble_votes": num_votes,
                    "ensemble_methods": [e.__class__.__name__ for e in entities],
                },
                evidence=best_entity.evidence,
            )
            merged_entities.append(merged)

        logger.info(
            f"✓ Ensemble extracted {len(merged_entities)} entities "
            f"({sum(1 for e in all_results.values() if len(e) > 1)} with agreement)"
        )
        return merged_entities
