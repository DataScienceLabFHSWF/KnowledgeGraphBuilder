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

from kgbuilder.core.models import ExtractedEntity, ExtractedRelation
from kgbuilder.extraction.entity import OntologyClassDef

logger = logging.getLogger(__name__)


class TieredExtractor:
    """Tiered entity extractor that tries fast heuristics before slow LLMs.

    Strategy:
    1. Run rule-based extractor (deterministic, <1ms)
    2. If results found, return them (time saving)
    3. If no results found, run LLM extractor (fallback)
    """

    def __init__(
        self,
        rule_extractor: Any,
        llm_extractor: Any,
        min_entities_heuristic: int = 1,
    ) -> None:
        """Initialize tiered extractor.

        Args:
            rule_extractor: Fast heuristic extractor (e.g. RuleBasedExtractor)
            llm_extractor: Slow but thorough extractor (e.g. LLMEntityExtractor)
            min_entities_heuristic: If rules find at least this many, skip LLM
        """
        self.rule_extractor = rule_extractor
        self.llm_extractor = llm_extractor
        self.min_entities = min_entities_heuristic
        logger.info(
            f"✓ Initialized TieredExtractor (Rules -> {llm_extractor.__class__.__name__})"
        )

    def extract(
        self,
        text: str,
        ontology_classes: list[Any] | None = None,
        existing_entities: list[ExtractedEntity] | None = None,
    ) -> list[ExtractedEntity]:
        """Extract entities using tiered approach."""
        # 1. Try rules first (fast)
        rule_results = self.rule_extractor.extract(text, ontology_classes, existing_entities)

        # 2. If rules find enough, stop here (time savings)
        if rule_results and len(rule_results) >= self.min_entities:
            logger.info("heuristic_extraction_sufficient", count=len(rule_results))
            return rule_results

        # 3. Fallback to LLM (slow but thorough)
        logger.debug("heuristic_insufficient_falling_back_to_llm")
        llm_results = self.llm_extractor.extract(text, ontology_classes, existing_entities)

        return llm_results if llm_results else rule_results


class TieredRelationExtractor:
    """Tiered relation extractor (Rules -> LLM)."""

    def __init__(
        self,
        rule_extractor: Any,
        llm_extractor: Any,
        min_relations_heuristic: int = 1,
    ) -> None:
        """Initialize tiered relation extractor."""
        self.rule_extractor = rule_extractor
        self.llm_extractor = llm_extractor
        self.min_relations = min_relations_heuristic
        logger.info(
            f"✓ Initialized TieredRelationExtractor (Rules -> {llm_extractor.__class__.__name__})"
        )

    def extract(
        self,
        text: str,
        entities: list[ExtractedEntity],
        ontology_relations: list[Any],
    ) -> list[ExtractedRelation]:
        """Extract relations using tiered approach."""
        # 1. Try rules first
        rule_results = self.rule_extractor.extract(text, entities, ontology_relations)

        # 2. If skip threshold reached (optional, for now we usually want LLM too)
        # But per user request for "deterministic" first:
        if rule_results and len(rule_results) >= self.min_relations:
            logger.info("heuristic_relations_sufficient", count=len(rule_results))
            return rule_results

        # 3. Fallback to LLM
        return self.llm_extractor.extract(text, entities, ontology_relations)


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
