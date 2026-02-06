"""Semantic enrichers for entity and relation enhancement.

Five enrichment phases:
1. DescriptionEnricher — LLM-generated descriptions
2. EmbeddingEnricher — 384-dim semantic embeddings
3. CompetencyQuestionEnricher — 3-5 CQs per entity
4. TypeConstraintEnricher — Type compatibility scores
5. AliasEnricher — Synonyms and abbreviations
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from pydantic import BaseModel

from kgbuilder.core.protocols import LLMProvider, EmbeddingProvider
from kgbuilder.enrichment.protocols import Enricher, EnrichedEntity, EnrichedRelation

logger = logging.getLogger(__name__)


class DescriptionEnricher(Enricher):
    """Generates human-readable descriptions via LLM."""

    def __init__(self, llm: LLMProvider) -> None:
        """Initialize description enricher.

        Args:
            llm: LLM provider for description generation
        """
        self.llm = llm

    def enrich_entities(self, entities: list[EnrichedEntity]) -> list[EnrichedEntity]:
        """Generate descriptions for entities.

        Args:
            entities: List of entities to enrich

        Returns:
            Entities with descriptions added
        """
        for entity in entities:
            if entity.description:
                continue  # Skip if already has description

            try:
                prompt = (
                    f"Generate a concise (1-2 sentence) description for this entity:\n"
                    f"Label: {entity.label}\n"
                    f"Type: {entity.entity_type}\n"
                    f"\nDescription:"
                )
                description = self.llm.generate(prompt, temperature=0.5)
                entity.description = description.strip()
                logger.debug(f"✓ Generated description for {entity.label}")
            except Exception as e:
                logger.warning(f"Failed to generate description for {entity.label}: {e}")

        return entities

    def enrich_relations(self, relations: list[EnrichedRelation]) -> list[EnrichedRelation]:
        """Generate descriptions for relations.

        Args:
            relations: List of relations to enrich

        Returns:
            Relations with descriptions added
        """
        for relation in relations:
            if relation.description:
                continue

            try:
                prompt = (
                    f"Generate a concise description for this relationship:\n"
                    f"Predicate: {relation.predicate}\n"
                    f"Source Type: {relation.source_id}\n"
                    f"Target Type: {relation.target_id}\n"
                    f"\nDescription:"
                )
                description = self.llm.generate(prompt, temperature=0.5)
                relation.description = description.strip()
                logger.debug(f"✓ Generated description for {relation.predicate}")
            except Exception as e:
                logger.warning(f"Failed to generate description for {relation.predicate}: {e}")

        return relations


class EmbeddingEnricher(Enricher):
    """Generates semantic embeddings for entities and relations."""

    def __init__(self, embedding_provider: EmbeddingProvider) -> None:
        """Initialize embedding enricher.

        Args:
            embedding_provider: Embedding provider (e.g., Ollama)
        """
        self.embedding_provider = embedding_provider

    def enrich_entities(self, entities: list[EnrichedEntity]) -> list[EnrichedEntity]:
        """Generate embeddings for entities.

        Args:
            entities: List of entities to enrich

        Returns:
            Entities with embeddings added
        """
        for entity in entities:
            if entity.embedding:
                continue  # Skip if already has embedding

            try:
                # Use label + description for richer embedding
                text = entity.label
                if entity.description:
                    text = f"{entity.label}: {entity.description}"

                embedding = self.embedding_provider.embed_text(text)
                entity.embedding = embedding.tolist() if isinstance(embedding, np.ndarray) else embedding
                logger.debug(f"✓ Generated embedding for {entity.label}")
            except Exception as e:
                logger.warning(f"Failed to generate embedding for {entity.label}: {e}")

        return entities

    def enrich_relations(self, relations: list[EnrichedRelation]) -> list[EnrichedRelation]:
        """Generate embeddings for relations.

        Args:
            relations: List of relations to enrich

        Returns:
            Relations with embeddings added
        """
        for relation in relations:
            if relation.embedding:
                continue

            try:
                text = relation.predicate
                if relation.description:
                    text = f"{relation.predicate}: {relation.description}"

                embedding = self.embedding_provider.embed_text(text)
                relation.embedding = embedding.tolist() if isinstance(embedding, np.ndarray) else embedding
                logger.debug(f"✓ Generated embedding for {relation.predicate}")
            except Exception as e:
                logger.warning(f"Failed to generate embedding for {relation.predicate}: {e}")

        return relations


class CompetencyQuestionEnricher(Enricher):
    """Generates competency questions for entities."""

    def __init__(self, llm: LLMProvider) -> None:
        """Initialize competency question enricher.

        Args:
            llm: LLM provider for CQ generation
        """
        self.llm = llm

    def enrich_entities(self, entities: list[EnrichedEntity]) -> list[EnrichedEntity]:
        """Generate competency questions for entities.

        Args:
            entities: List of entities to enrich

        Returns:
            Entities with competency questions added
        """
        for entity in entities:
            if entity.competency_questions:
                continue

            try:
                prompt = (
                    f"Generate 3-5 competency questions that this entity helps answer:\n"
                    f"Entity: {entity.label}\n"
                    f"Type: {entity.entity_type}\n"
                    f"{f'Description: {entity.description}' if entity.description else ''}\n"
                    f"\nCompetency Questions (one per line):\n"
                )
                cq_text = self.llm.generate(prompt, temperature=0.6)
                cqs = [q.strip() for q in cq_text.strip().split('\n') if q.strip()]
                entity.competency_questions = cqs
                logger.debug(f"✓ Generated {len(cqs)} CQs for {entity.label}")
            except Exception as e:
                logger.warning(f"Failed to generate CQs for {entity.label}: {e}")

        return entities

    def enrich_relations(self, relations: list[EnrichedRelation]) -> list[EnrichedRelation]:
        """Relations don't typically have competency questions; skip."""
        return relations


class TypeConstraintEnricher(Enricher):
    """Assigns type compatibility scores based on domain/range constraints."""

    def __init__(self, ontology_classes: dict[str, Any]) -> None:
        """Initialize type constraint enricher.

        Args:
            ontology_classes: Dictionary mapping class names to class definitions
        """
        self.ontology_classes = ontology_classes

    def enrich_entities(self, entities: list[EnrichedEntity]) -> list[EnrichedEntity]:
        """Assign type scores to entities based on ontology.

        Args:
            entities: List of entities to enrich

        Returns:
            Entities with type scores added
        """
        for entity in entities:
            type_scores: dict[str, float] = {}

            # Check compatibility with each ontology class
            for class_name, class_def in self.ontology_classes.items():
                if entity.entity_type == class_name:
                    type_scores[class_name] = 1.0  # Perfect match
                else:
                    # Simple heuristic: check if type is subclass or related
                    type_scores[class_name] = 0.5 if self._is_related(entity.entity_type, class_name) else 0.0

            entity.type_scores = type_scores if type_scores else None
            logger.debug(f"✓ Computed type scores for {entity.label}")

        return entities

    def enrich_relations(self, relations: list[EnrichedRelation]) -> list[EnrichedRelation]:
        """Assign type scores to relations.

        Args:
            relations: List of relations to enrich

        Returns:
            Relations with type scores added
        """
        return relations

    def _is_related(self, entity_type: str, class_name: str) -> bool:
        """Check if entity_type is related to class_name."""
        # Simple substring match for now; could be extended with ontology reasoning
        return entity_type.lower() in class_name.lower() or class_name.lower() in entity_type.lower()


class AliasEnricher(Enricher):
    """Discovers and assigns aliases (synonyms, abbreviations) to entities."""

    def __init__(self, llm: LLMProvider) -> None:
        """Initialize alias enricher.

        Args:
            llm: LLM provider for alias generation
        """
        self.llm = llm

    def enrich_entities(self, entities: list[EnrichedEntity]) -> list[EnrichedEntity]:
        """Generate aliases for entities.

        Args:
            entities: List of entities to enrich

        Returns:
            Entities with aliases added
        """
        for entity in entities:
            if entity.aliases:
                continue

            try:
                prompt = (
                    f"Generate 2-4 aliases (synonyms, abbreviations, alternate names) for:\n"
                    f"Entity: {entity.label}\n"
                    f"Type: {entity.entity_type}\n"
                    f"Context: {entity.description or 'No description'}\n"
                    f"\nAliases (comma-separated):\n"
                )
                aliases_text = self.llm.generate(prompt, temperature=0.6)
                aliases = [a.strip() for a in aliases_text.strip().split(',') if a.strip()]
                entity.aliases = aliases if aliases else None
                logger.debug(f"✓ Generated {len(aliases or [])} aliases for {entity.label}")
            except Exception as e:
                logger.warning(f"Failed to generate aliases for {entity.label}: {e}")

        return entities

    def enrich_relations(self, relations: list[EnrichedRelation]) -> list[EnrichedRelation]:
        """Relations don't typically have aliases; skip."""
        return relations
