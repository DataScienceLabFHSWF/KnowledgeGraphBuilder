"""Smart entity extractor with ontology-aware semantic filtering for token optimization.

Implements approach #2 from LFM exploration: reduces token counts by filtering
irrelevant ontology classes before extraction, using embedding-based semantic
relevance scoring.

Key features:
- Semantic filtering of ontology classes by relevance to source text
- Configurable max_classes parameter to control token budget
- Token usage tracking (before/after filtering) for optimization metrics
- Fallback to unfiltered extraction if embedding provider unavailable
- Compatible with any LLM model (Gemma4, LFM2.5, etc.)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import structlog

from kgbuilder.core.models import ExtractedEntity
from kgbuilder.core.protocols import LLMProvider
from kgbuilder.extraction.entity import (
    LLMEntityExtractor,
    OntologyClassDef,
)

logger = structlog.get_logger(__name__)


@dataclass
class FilteringMetrics:
    """Metrics for ontology filtering operation."""

    total_classes: int
    filtered_classes: int
    reduction_percent: float
    embedding_time_ms: float
    filtering_time_ms: float
    estimated_token_savings: int


class SmartEntityExtractor(LLMEntityExtractor):
    """Entity extractor with ontology-aware semantic filtering.

    Reduces extraction token counts by filtering irrelevant ontology classes
    based on embedding-based semantic relevance to the source text.

    This is particularly valuable for large ontologies (100+ classes) where
    many classes are irrelevant to a given document chunk.

    Usage:
        extractor = SmartEntityExtractor(
            llm_provider=ollama_provider,
            embedding_provider=ollama_provider,  # Same provider works
            max_classes=10,  # Keep top 10 most relevant classes
            confidence_threshold=0.5
        )

        entities = extractor.extract(
            text=source_text,
            ontology_classes=all_100_classes
        )
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        embedding_provider: Any | None = None,
        max_classes: int = 15,
        confidence_threshold: float = 0.5,
        max_retries: int = 3,
        token_budget_target: int | None = None,
    ) -> None:
        """Initialize smart entity extractor.

        Args:
            llm_provider: LLM provider for extraction (Gemma4, LFM2.5, etc.)
            embedding_provider: Provider with embed_text() method (optional).
                If None, falls back to unfiltered extraction.
                Can be same provider if it supports both LLM + embedding.
            max_classes: Maximum ontology classes to include in extraction
                prompt. Semantic filtering selects top-K by relevance.
                Default 15 is tuned for ~2-3K token prompt budgets.
            confidence_threshold: Minimum confidence for entities (0.0-1.0)
            max_retries: Max retries on extraction failure
            token_budget_target: Target prompt token count (for future budget
                optimization). Currently unused; reserved for adaptive filtering.
        """
        super().__init__(
            llm_provider=llm_provider,
            confidence_threshold=confidence_threshold,
            max_retries=max_retries,
        )
        self.embedding_provider = embedding_provider
        self.max_classes = max_classes
        self.token_budget_target = token_budget_target
        self.last_filtering_metrics: FilteringMetrics | None = None

        logger.info(
            "initialized_smart_entity_extractor",
            llm_model=llm_provider.model_name,
            embedding_available=embedding_provider is not None,
            max_classes=max_classes,
            token_budget_target=token_budget_target,
        )

    def extract(
        self,
        text: str,
        ontology_classes: list[OntologyClassDef] | None = None,
        existing_entities: list[ExtractedEntity] | None = None,
        apply_filtering: bool = True,
    ) -> list[ExtractedEntity]:
        """Extract entities with optional semantic filtering of ontology.

        Args:
            text: Source text to extract from
            ontology_classes: Valid entity types from ontology
            existing_entities: Known entities for deduplication
            apply_filtering: If True, filter classes by relevance. Set False
                to bypass filtering (useful for debugging/comparison).

        Returns:
            List of extracted entities
        """
        if not ontology_classes:
            logger.warning("No ontology classes provided")
            return []

        # Apply semantic filtering if enabled and embedding provider available
        if apply_filtering and self.embedding_provider is not None:
            filtered_classes = self._filter_relevant_classes(text, ontology_classes)
            logger.info(
                "ontology_classes_filtered",
                original_count=len(ontology_classes),
                filtered_count=len(filtered_classes),
                max_classes=self.max_classes,
                reduction_percent=self.last_filtering_metrics.reduction_percent
                if self.last_filtering_metrics
                else 0.0,
            )
        else:
            filtered_classes = ontology_classes

        # Extract using parent class with filtered ontology
        return super().extract(
            text=text,
            ontology_classes=filtered_classes,
            existing_entities=existing_entities,
        )

    def _filter_relevant_classes(
        self,
        text: str,
        ontology_classes: list[OntologyClassDef],
    ) -> list[OntologyClassDef]:
        """Filter ontology classes by semantic relevance to text.

        Uses embedding-based cosine similarity to rank classes.
        Returns top-K most relevant classes.

        Args:
            text: Source text to filter classes for
            ontology_classes: Candidate classes to filter

        Returns:
            Top-K classes ranked by relevance (top_classes ≤ max_classes)
        """
        if len(ontology_classes) <= self.max_classes:
            # Already below threshold, no filtering needed
            self.last_filtering_metrics = FilteringMetrics(
                total_classes=len(ontology_classes),
                filtered_classes=len(ontology_classes),
                reduction_percent=0.0,
                embedding_time_ms=0.0,
                filtering_time_ms=0.0,
                estimated_token_savings=0,
            )
            return ontology_classes

        if self.embedding_provider is None:
            # No embedding provider, return first max_classes
            logger.warning("No embedding provider, returning first max_classes")
            return ontology_classes[: self.max_classes]

        start_time = time.time()
        embedding_start = time.time()

        try:
            # Embed the source text
            text_embedding = self.embedding_provider.embed_text(text)
            if text_embedding is None:
                logger.warning("embed_text returned None, skipping filtering")
                return ontology_classes[: self.max_classes]

            # Embed each class (label + description)
            scores = []
            for cls in ontology_classes:
                class_text = self._class_to_text(cls)
                try:
                    cls_embedding = self.embedding_provider.embed_text(class_text)
                    if cls_embedding is None:
                        scores.append((0.0, cls))
                        continue

                    # Compute cosine similarity
                    similarity = self._cosine_similarity(text_embedding, cls_embedding)
                    scores.append((similarity, cls))
                except Exception as e:
                    logger.warning(
                        "embedding_error_for_class",
                        class_label=cls.label,
                        error=str(e),
                    )
                    scores.append((0.0, cls))

            embedding_time = time.time() - embedding_start

            # Sort by similarity, take top-K
            scores.sort(reverse=True, key=lambda x: x[0])
            filtered = [cls for _, cls in scores[: self.max_classes]]

            filtering_time = time.time() - start_time

            # Estimate token savings: assume ~1.5 tokens per class description
            tokens_saved = (len(ontology_classes) - len(filtered)) * 15
            reduction_percent = 100.0 * (
                len(ontology_classes) - len(filtered)
            ) / len(ontology_classes)

            self.last_filtering_metrics = FilteringMetrics(
                total_classes=len(ontology_classes),
                filtered_classes=len(filtered),
                reduction_percent=reduction_percent,
                embedding_time_ms=embedding_time * 1000,
                filtering_time_ms=filtering_time * 1000,
                estimated_token_savings=tokens_saved,
            )

            logger.info(
                "ontology_filtered",
                total=len(ontology_classes),
                filtered=len(filtered),
                reduction_pct=f"{reduction_percent:.1f}%",
                tokens_saved=tokens_saved,
                time_ms=f"{filtering_time * 1000:.1f}",
            )

            return filtered

        except Exception as e:
            logger.error(
                "filtering_failed",
                error=str(e),
                fallback="returning_first_max_classes",
            )
            # Fallback: return first max_classes
            return ontology_classes[: self.max_classes]

    @staticmethod
    def _class_to_text(cls: OntologyClassDef) -> str:
        """Convert ontology class to text for embedding.

        Args:
            cls: Ontology class definition

        Returns:
            String representation (label + description)
        """
        parts = [cls.label]
        if cls.description:
            parts.append(cls.description)
        if cls.examples:
            parts.append(f"Examples: {', '.join(cls.examples)}")
        return ". ".join(parts)

    @staticmethod
    def _cosine_similarity(vec_a: Any, vec_b: Any) -> float:
        """Compute cosine similarity between two vectors.

        Args:
            vec_a: First vector (numpy array or list)
            vec_b: Second vector (numpy array or list)

        Returns:
            Cosine similarity [-1, 1]. Returns 0 on error.
        """
        try:
            a = np.asarray(vec_a, dtype=np.float32)
            b = np.asarray(vec_b, dtype=np.float32)

            # Handle zero vectors
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            if norm_a == 0 or norm_b == 0:
                return 0.0

            return float(np.dot(a, b) / (norm_a * norm_b))
        except Exception as e:
            logger.debug(f"cosine_similarity_error: {e}")
            return 0.0

    def get_filtering_metrics(self) -> FilteringMetrics | None:
        """Get metrics from the last extraction's filtering step.

        Returns:
            FilteringMetrics if filtering was applied, else None
        """
        return self.last_filtering_metrics
