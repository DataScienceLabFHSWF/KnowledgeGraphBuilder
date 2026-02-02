"""Entity extraction using LLM with ontology guidance.

Implementation of Issue #5.1-#5.2: Entity Extraction

Key features:
- Ontology-guided prompting with class descriptions
- Structured JSON extraction with Pydantic validation
- Entity deduplication within document
- Confidence score calibration
- Error recovery with retries
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from pydantic import ValidationError

from kgbuilder.core.models import ExtractedEntity, Evidence
from kgbuilder.extraction.schemas import EntityExtractionOutput, EntityItem

logger = logging.getLogger(__name__)


@runtime_checkable
class EntityExtractor(Protocol):
    """Protocol for entity extraction implementations."""

    def extract(
        self,
        text: str,
        ontology_classes: list[OntologyClassDef],
        existing_entities: list[ExtractedEntity] | None = None,
    ) -> list[ExtractedEntity]:
        """Extract entities from text guided by ontology.

        Args:
            text: Source text to extract from
            ontology_classes: Target entity types from ontology
            existing_entities: Known entities for coreference/deduplication

        Returns:
            List of extracted entities with confidence and evidence
        """
        ...


@dataclass
class OntologyClassDef:
    """Ontology class definition for extraction guidance."""

    uri: str
    label: str
    description: str | None = None
    examples: list[str] = field(default_factory=list)
    parent_uri: str | None = None


class LLMEntityExtractor:
    """LLM-based entity extractor with ontology guidance.

    Uses structured JSON extraction with Pydantic validation.
    Integrates with QWEN3/qwen3-next via Ollama for local inference.
    """

    def __init__(
        self,
        llm_provider: Any,  # LLMProvider
        confidence_threshold: float = 0.5,
        max_retries: int = 3,
    ) -> None:
        """Initialize entity extractor.

        Args:
            llm_provider: LLM provider instance (Ollama, OpenAI, etc.)
            confidence_threshold: Minimum confidence for entities (0.0-1.0)
            max_retries: Max retries on extraction failure
        """
        self._llm = llm_provider
        self.confidence_threshold = confidence_threshold
        self.max_retries = max_retries
        logger.info(
            f"✓ Initialized LLMEntityExtractor with {llm_provider.model_name} "
            f"(threshold={confidence_threshold})"
        )

    def extract(
        self,
        text: str,
        ontology_classes: list[OntologyClassDef],
        existing_entities: list[ExtractedEntity] | None = None,
    ) -> list[ExtractedEntity]:
        """Extract entities from text with ontology guidance.

        Args:
            text: Source text (max 4000 chars recommended for single pass)
            ontology_classes: Valid entity types from ontology
            existing_entities: Known entities for deduplication (optional)

        Returns:
            List of extracted entities filtered by confidence threshold

        Raises:
            RuntimeError: If extraction fails after max_retries
        """
        if not text or not text.strip():
            logger.warning("Empty text provided to extract()")
            return []

        if not ontology_classes:
            logger.warning("No ontology classes provided")
            return []

        logger.info(
            f"Extracting entities from {len(text)} chars, {len(ontology_classes)} classes"
        )

        # Build and execute extraction
        prompt = self._build_extraction_prompt(text, ontology_classes)

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(f"Extraction attempt {attempt}/{self.max_retries}")

                # Call LLM with structured output
                output = self._llm.generate_structured(
                    prompt,
                    EntityExtractionOutput,
                )

                # Convert schema output to domain entities
                entities = self._convert_to_extracted_entities(output, text)

                # Deduplicate
                entities = self._deduplicate_entities(entities, existing_entities)

                # Filter by confidence
                entities = [
                    e
                    for e in entities
                    if e.confidence >= self.confidence_threshold
                ]

                logger.info(
                    f"✓ Extracted {len(entities)} entities "
                    f"(confidence >= {self.confidence_threshold})"
                )
                return entities

            except ValidationError as e:
                logger.warning(f"Attempt {attempt}: Schema validation failed: {e}")
                if attempt == self.max_retries:
                    raise RuntimeError(
                        f"Extraction failed after {self.max_retries} attempts: {e}"
                    ) from e
            except Exception as e:
                logger.warning(f"Attempt {attempt}: Extraction error: {e}")
                if attempt == self.max_retries:
                    raise RuntimeError(
                        f"Extraction failed after {self.max_retries} attempts: {e}"
                    ) from e

        return []

    def _build_extraction_prompt(
        self, text: str, ontology_classes: list[OntologyClassDef]
    ) -> str:
        """Build ontology-guided extraction prompt.

        Args:
            text: Source text to extract from
            ontology_classes: Entity type definitions

        Returns:
            Formatted prompt for structured extraction
        """
        # Format ontology classes
        ontology_section = self._format_ontology_section(ontology_classes)

        prompt = f"""Extract entities from the following text. Identify all mentions of:
{ontology_section}

TEXT TO ANALYZE:
{text}

For each entity found:
1. Assign a unique ID (ent_XXX format)
2. Record the exact text as it appears in the source
3. Classify as one of the entity types above
4. Estimate confidence (0.0-1.0) based on context clarity
5. Note character positions in the original text
6. Provide context (50 chars before/after)

Extract all entities you can identify. Prioritize entities with clear context and high confidence.
Focus on domain-relevant entities (organizations, facilities, operations, requirements, documents)."""

        logger.debug(f"Generated prompt ({len(prompt)} chars)")
        return prompt

    def _format_ontology_section(
        self, ontology_classes: list[OntologyClassDef]
    ) -> str:
        """Format ontology classes for prompt inclusion.

        Args:
            ontology_classes: Entity type definitions

        Returns:
            Formatted ontology section
        """
        lines = []
        for cls in ontology_classes:
            header = f"- **{cls.label}** ({cls.uri})"
            lines.append(header)

            if cls.description:
                lines.append(f"  Description: {cls.description}")

            if cls.examples:
                examples_str = ", ".join(f'"{ex}"' for ex in cls.examples[:3])
                lines.append(f"  Examples: {examples_str}")

        return "\n".join(lines)

    def _convert_to_extracted_entities(
        self,
        output: EntityExtractionOutput,
        source_text: str,
    ) -> list[ExtractedEntity]:
        """Convert schema output to domain ExtractedEntity objects.

        Args:
            output: Structured extraction output
            source_text: Original source text for evidence

        Returns:
            List of ExtractedEntity domain objects
        """
        entities = []

        for item in output.entities:
            # Create Evidence
            text_span = source_text[
                max(0, item.start_char) : min(len(source_text), item.end_char)
            ]
            evidence = Evidence(
                source_type="local_doc",
                source_id="chunk_id",
                text_span=text_span if text_span.strip() else None,
                confidence=item.confidence,
            )

            # Create ExtractedEntity
            entity = ExtractedEntity(
                id=item.id or f"ent_{uuid.uuid4().hex[:8]}",
                label=item.label,
                entity_type=item.entity_type,
                confidence=item.confidence,
                evidence=[evidence],
            )
            entities.append(entity)

        return entities

    def _deduplicate_entities(
        self,
        entities: list[ExtractedEntity],
        existing_entities: list[ExtractedEntity] | None = None,
    ) -> list[ExtractedEntity]:
        """Deduplicate entities, preferring higher confidence.

        Simple deduplication based on label and type.
        For same entity: keeps highest confidence version.

        Args:
            entities: Extracted entities
            existing_entities: Previously known entities (merged with extracted)

        Returns:
            Deduplicated entity list
        """
        all_entities = entities + (existing_entities or [])
        deduplicated: dict[tuple[str, str], ExtractedEntity] = {}

        for entity in all_entities:
            key = (entity.label.lower(), entity.entity_type)
            if key not in deduplicated or entity.confidence > deduplicated[key].confidence:
                deduplicated[key] = entity

        result = list(deduplicated.values())
        logger.debug(
            f"Deduplicated {len(all_entities)} → {len(result)} entities"
        )
        return result
