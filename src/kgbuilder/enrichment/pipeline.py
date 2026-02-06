"""Semantic enrichment pipeline orchestrator.

Coordinates 5 enrichment phases in sequence:
1. Descriptions (LLM)
2. Embeddings (Ollama)
3. Competency Questions (LLM)
4. Type Constraints (Ontology)
5. Aliases (LLM)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from kgbuilder.core.protocols import LLMProvider, EmbeddingProvider
from kgbuilder.enrichment.enrichers import (
    AliasEnricher,
    CompetencyQuestionEnricher,
    DescriptionEnricher,
    EmbeddingEnricher,
    TypeConstraintEnricher,
)
from kgbuilder.enrichment.protocols import Enricher, EnrichedEntity, EnrichedRelation

logger = logging.getLogger(__name__)


@dataclass
class EnrichmentMetrics:
    """Metrics from enrichment pipeline run."""

    total_entities: int = 0
    total_relations: int = 0
    descriptions_added: int = 0
    embeddings_added: int = 0
    competency_questions_added: int = 0
    aliases_added: int = 0
    type_scores_assigned: int = 0
    duration_seconds: float = 0.0


class SemanticEnrichmentPipeline:
    """Orchestrates multi-phase semantic enrichment of entities and relations."""

    def __init__(
        self,
        llm: LLMProvider,
        embedding_provider: EmbeddingProvider,
        ontology_classes: dict[str, object] | None = None,
    ) -> None:
        """Initialize enrichment pipeline.

        Args:
            llm: Language model for descriptions, CQs, aliases
            embedding_provider: Embedding provider for semantic vectors
            ontology_classes: Optional ontology class definitions for type constraint enrichment
        """
        self.llm = llm
        self.embedding_provider = embedding_provider
        self.ontology_classes = ontology_classes or {}

        # Initialize enrichers in order
        self.enrichers: list[tuple[str, Enricher]] = [
            ("descriptions", DescriptionEnricher(llm)),
            ("embeddings", EmbeddingEnricher(embedding_provider)),
            ("competency_questions", CompetencyQuestionEnricher(llm)),
            ("type_constraints", TypeConstraintEnricher(self.ontology_classes)),
            ("aliases", AliasEnricher(llm)),
        ]

    def enrich(
        self,
        entities: list[EnrichedEntity],
        relations: list[EnrichedRelation] | None = None,
    ) -> tuple[list[EnrichedEntity], list[EnrichedRelation], EnrichmentMetrics]:
        """Run full enrichment pipeline on entities and relations.

        Args:
            entities: List of entities to enrich
            relations: Optional list of relations to enrich

        Returns:
            Tuple of (enriched entities, enriched relations, metrics)
        """
        if relations is None:
            relations = []

        start_time = time.time()
        metrics = EnrichmentMetrics(
            total_entities=len(entities),
            total_relations=len(relations),
        )

        logger.info(
            f"Starting enrichment pipeline: {len(entities)} entities, {len(relations)} relations"
        )

        # Run each enrichment phase
        for phase_name, enricher in self.enrichers:
            logger.info(f"Phase: {phase_name}")
            try:
                # Enrich entities
                entities = enricher.enrich_entities(entities)

                # Enrich relations if applicable
                if relations:
                    relations = enricher.enrich_relations(relations)

                # Track metrics
                for ent in entities:
                    if phase_name == "descriptions" and ent.description:
                        metrics.descriptions_added += 1
                    elif phase_name == "embeddings" and ent.embedding:
                        metrics.embeddings_added += 1
                    elif phase_name == "competency_questions" and ent.competency_questions:
                        metrics.competency_questions_added += 1
                    elif phase_name == "aliases" and ent.aliases:
                        metrics.aliases_added += 1
                    elif phase_name == "type_constraints" and ent.type_scores:
                        metrics.type_scores_assigned += 1

                logger.debug(f"✓ Phase {phase_name} complete")

            except Exception as e:
                logger.error(f"Enrichment phase '{phase_name}' failed: {e}", exc_info=True)
                # Continue with next phase on error
                continue

        metrics.duration_seconds = time.time() - start_time

        logger.info(
            f"✓ Enrichment complete in {metrics.duration_seconds:.2f}s: "
            f"descriptions={metrics.descriptions_added}, "
            f"embeddings={metrics.embeddings_added}, "
            f"cqs={metrics.competency_questions_added}, "
            f"aliases={metrics.aliases_added}, "
            f"type_scores={metrics.type_scores_assigned}"
        )

        return entities, relations, metrics
