"""Semantic enrichment for discovered knowledge graph entities.

Enhances extracted entities and relations with:
- Semantic descriptions generated via LLM
- Competency questions for entity type guidance
- Semantic embeddings for similarity matching
- Discovery metadata (which question found it, confidence, evidence count)

This is a post-processing step applied AFTER extraction but BEFORE Neo4j storage,
enabling efficient reuse of expensive extraction phase.

Implementation of Planning/RETRIEVAL_SEMANTIC_ENRICHMENT.md Phase 1-2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import structlog
from numpy.typing import NDArray

from kgbuilder.core.models import ExtractedEntity, ExtractedRelation

logger = structlog.get_logger(__name__)


@dataclass
class EnrichedEntity:
    """Entity enriched with semantic metadata."""

    # Core extracted data
    entity: ExtractedEntity

    # Semantic data added by enrichment
    description: str = ""  # LLM-generated semantic description
    semantic_embedding: NDArray[np.float32] | None = None  # For similarity
    competency_questions: list[str] = field(default_factory=list)

    # Discovery metadata
    discovery_question_ids: list[str] = field(default_factory=list)
    evidence_count: int = 0
    discovery_confidence: float = 0.0  # Average of all discoveries


@dataclass
class EnrichedRelation:
    """Relation enriched with semantic metadata."""

    # Core extracted data
    relation: ExtractedRelation

    # Semantic data added by enrichment
    description: str = ""  # LLM-generated semantic description
    semantic_embedding: NDArray[np.float32] | None = None


class SemanticEnrichmentPipeline:
    """Enriches extracted entities and relations with semantic data.

    Strategy:
    1. Generate descriptions for each entity from its type + context
    2. Generate competency questions for validation
    3. Generate semantic embeddings for similarity matching
    4. Track discovery metadata (which questions found each entity)

    See Planning/RETRIEVAL_SEMANTIC_ENRICHMENT.md for full design.
    """

    def __init__(
        self,
        llm_provider: Any,  # LLMProvider
        embedding_provider: Any,  # EmbeddingProvider (e.g., Ollama)
        confidence_threshold: float = 0.5,
    ) -> None:
        """Initialize enrichment pipeline.

        Args:
            llm_provider: LLM for generating descriptions/questions
            embedding_provider: Provider for generating embeddings
            confidence_threshold: Minimum confidence for retention
        """
        self._llm = llm_provider
        self._embeddings = embedding_provider
        self._confidence_threshold = confidence_threshold

    def enrich_entities(
        self,
        entities: list[ExtractedEntity],
        discovery_metadata: dict[str, Any] | None = None,
    ) -> list[EnrichedEntity]:
        """Enrich entities with semantic metadata.

        Args:
            entities: Extracted entities to enrich
            discovery_metadata: Mapping of entity_id to discovery info
                (e.g., {"e1": {"questions": ["q1", "q2"], "confidence": 0.85}})

        Returns:
            List of enriched entities
        """
        logger.info("enriching_entities", count=len(entities))

        enriched = []
        for entity in entities:
            try:
                # Generate description
                description = self._generate_entity_description(entity)

                # Generate competency questions
                questions = self._generate_competency_questions(
                    entity.label, entity.entity_type
                )

                # Generate semantic embedding
                embedding = self._generate_embedding(
                    f"{entity.label} ({entity.entity_type}): {description}"
                )

                # Get discovery metadata
                metadata = discovery_metadata.get(entity.id, {}) if discovery_metadata else {}

                enriched_entity = EnrichedEntity(
                    entity=entity,
                    description=description,
                    semantic_embedding=embedding,
                    competency_questions=questions,
                    discovery_question_ids=metadata.get("questions", []),
                    evidence_count=metadata.get("evidence_count", len(entity.evidence)),
                    discovery_confidence=metadata.get(
                        "confidence", entity.confidence
                    ),
                )

                enriched.append(enriched_entity)
                logger.debug(
                    "entity_enriched",
                    entity_id=entity.id,
                    with_description=bool(description),
                    with_embedding=embedding is not None,
                    questions_count=len(questions),
                )

            except Exception as e:
                logger.warning(
                    "entity_enrichment_failed",
                    entity_id=entity.id,
                    error=str(e),
                )
                # Add entity even without enrichment
                enriched.append(
                    EnrichedEntity(entity=entity, description="")
                )

        logger.info("entities_enriched", count=len(enriched))
        return enriched

    def enrich_relations(
        self,
        relations: list[ExtractedRelation],
        entities: dict[str, ExtractedEntity] | None = None,
    ) -> list[EnrichedRelation]:
        """Enrich relations with semantic metadata.

        Args:
            relations: Extracted relations to enrich
            entities: Mapping of entity_id to entity (for context)

        Returns:
            List of enriched relations
        """
        logger.info("enriching_relations", count=len(relations))

        enriched = []
        for relation in relations:
            try:
                # Get source and target entity labels for context
                source_label = ""
                target_label = ""

                if entities:
                    source_label = entities.get(
                        relation.source_entity_id,
                        ExtractedEntity(id="?", label="", entity_type="", description=""),
                    ).label
                    target_label = entities.get(
                        relation.target_entity_id,
                        ExtractedEntity(id="?", label="", entity_type="", description=""),
                    ).label

                # Generate description
                description = self._generate_relation_description(
                    source_label, target_label, relation.predicate
                )

                # Generate semantic embedding
                embedding = self._generate_embedding(
                    f"{source_label} --{relation.predicate}--> {target_label}: {description}"
                )

                enriched_relation = EnrichedRelation(
                    relation=relation,
                    description=description,
                    semantic_embedding=embedding,
                )

                enriched.append(enriched_relation)
                logger.debug(
                    "relation_enriched",
                    relation_id=relation.id,
                    with_description=bool(description),
                    with_embedding=embedding is not None,
                )

            except Exception as e:
                logger.warning(
                    "relation_enrichment_failed",
                    relation_id=relation.id,
                    error=str(e),
                )
                # Add relation even without enrichment
                enriched.append(EnrichedRelation(relation=relation))

        logger.info("relations_enriched", count=len(enriched))
        return enriched

    def _generate_entity_description(self, entity: ExtractedEntity) -> str:
        """Generate semantic description for entity.

        Args:
            entity: Entity to describe

        Returns:
            Generated description
        """
        # For now, return a placeholder
        # In full implementation, would use LLM to generate from context
        return (
            f"{entity.label} is an example of {entity.entity_type} "
            f"(confidence: {entity.confidence:.2f})"
        )

    def _generate_competency_questions(
        self, label: str, entity_type: str
    ) -> list[str]:
        """Generate competency questions for entity.

        Args:
            label: Entity label
            entity_type: Entity type/class

        Returns:
            List of competency questions
        """
        # For now, return template questions
        # In full implementation, would generate specific questions via LLM
        return [
            f"What is {label}?",
            f"How does {label} relate to other {entity_type} entities?",
            f"What are the key properties of {label}?",
        ]

    def _generate_embedding(self, text: str) -> NDArray[np.float32] | None:
        """Generate semantic embedding for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None if embedding fails
        """
        try:
            # Use embedding provider if available
            if self._embeddings:
                embedding = self._embeddings.embed_text(text)
                if isinstance(embedding, list):
                    return np.array(embedding, dtype=np.float32)
                return embedding
            return None
        except Exception as e:
            logger.warning("embedding_generation_failed", error=str(e))
            return None

    def _generate_relation_description(
        self, source_label: str, target_label: str, predicate: str
    ) -> str:
        """Generate description for relation.

        Args:
            source_label: Source entity label
            target_label: Target entity label
            predicate: Relation predicate

        Returns:
            Generated description
        """
        return (
            f"Relation '{predicate}' connecting {source_label} to {target_label}"
        )
