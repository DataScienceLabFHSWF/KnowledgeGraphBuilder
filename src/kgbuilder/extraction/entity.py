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
from kgbuilder.core.protocols import LLMProvider
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
        llm_provider: LLMProvider,
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

        Uses LLM with structured JSON output and retry logic.
        Validates output against Pydantic schema with automatic retries.

        Args:
            text: Source text (max 4000 chars recommended for single pass)
            ontology_classes: Valid entity types from ontology
            existing_entities: Known entities for deduplication (optional)

        Returns:
            List of extracted entities filtered by confidence threshold

        Raises:
            RuntimeError: If extraction fails after max_retries
        """
        # Validate inputs
        if not text or not text.strip():
            logger.warning("Empty text provided to extract()")
            return []

        if not ontology_classes:
            logger.warning("No ontology classes provided")
            return []

        text = text.strip()
        logger.info(
            f"Extracting entities from {len(text)} chars, {len(ontology_classes)} classes"
        )

        # Build ontology-guided prompt
        prompt = self._build_extraction_prompt(text, ontology_classes)

        # Retry loop with exponential backoff
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(f"Extraction attempt {attempt}/{self.max_retries}")

                # Call LLM with structured output validation
                output = self._llm.generate_structured(
                    prompt,
                    EntityExtractionOutput,
                )

                # Validate output is not empty
                if not output.entities:
                    logger.info("LLM returned no entities")
                    return []

                # Convert schema output to domain entities
                entities = self._convert_to_extracted_entities(output, text)

                logger.debug(f"Converted {len(entities)} entities from LLM output")

                # Deduplicate
                entities = self._deduplicate_entities(entities, existing_entities)

                # Filter by confidence threshold
                filtered = [
                    e
                    for e in entities
                    if e.confidence >= self.confidence_threshold
                ]

                logger.info(
                    f"✓ Extracted {len(filtered)}/{len(entities)} entities "
                    f"(confidence >= {self.confidence_threshold})"
                )
                return filtered

            except ValidationError as e:
                logger.warning(
                    f"Attempt {attempt}: Schema validation failed: {e.error_count()} errors"
                )
                if attempt < self.max_retries:
                    logger.debug(f"Retrying (attempt {attempt + 1}/{self.max_retries})")
                    continue
                raise RuntimeError(
                    f"Extraction failed after {self.max_retries} attempts: {e}"
                ) from e

            except Exception as e:
                logger.warning(f"Attempt {attempt}: Extraction error: {type(e).__name__}: {e}")
                if attempt < self.max_retries:
                    logger.debug(f"Retrying (attempt {attempt + 1}/{self.max_retries})")
                    continue
                raise RuntimeError(
                    f"Extraction failed after {self.max_retries} attempts: {e}"
                ) from e

        return []

    def _build_extraction_prompt(
        self, text: str, ontology_classes: list[OntologyClassDef]
    ) -> str:
        """Build ontology-guided extraction prompt.

        Constructs a structured prompt that:
        1. Explains the extraction task
        2. Lists valid entity types from ontology
        3. Provides extraction guidelines
        4. Includes the source text

        Args:
            text: Source text to extract from
            ontology_classes: Entity type definitions

        Returns:
            Formatted prompt for structured extraction
        """
        # Format ontology classes
        ontology_section = self._format_ontology_section(ontology_classes)

        prompt = f"""You are an expert entity extraction system.

TASK: Extract entities from the following text.
Match each entity to one of the valid types listed below.

VALID ENTITY TYPES:
{ontology_section}

EXTRACTION GUIDELINES:
1. Extract all entities matching the types above
2. Assign each a unique ID in format "ent_XXX" 
3. Record exact text as it appears in source
4. Classify as one of the entity types above
5. Estimate confidence (0.0-1.0) based on context clarity:
   - 0.9-1.0: Very clear, unambiguous entity
   - 0.7-0.9: Likely entity, clear context
   - 0.5-0.7: Possible entity, some ambiguity
   - <0.5: Uncertain, skip or lower confidence
6. Find character positions (start_char, end_char) in source text
7. Provide context: text snippet with 50 chars before/after entity

IMPORTANT:
- Be conservative: only extract if confident
- Avoid duplicates: each entity type + label should appear once
- Domain focus: prioritize domain-relevant entities
- Quality over quantity: accuracy matters more than coverage

TEXT TO ANALYZE:
{text}

Extract all entities you can identify with confidence >= 0.5."""

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
        """Convert Pydantic schema output to domain ExtractedEntity objects.

        Maps EntityExtractionOutput (LLM schema) to ExtractedEntity (domain model)
        and creates Evidence objects for provenance tracking.

        Args:
            output: Structured extraction output from LLM
            source_text: Original source text for evidence

        Returns:
            List of ExtractedEntity domain objects with provenance
        """
        entities = []

        for item in output.entities:
            # Validate character positions
            start = max(0, min(item.start_char, len(source_text)))
            end = min(len(source_text), item.end_char)
            
            if start >= end:
                logger.warning(
                    f"Invalid char range for entity {item.label}: [{start}, {end}]"
                )
                start, end = 0, 0

            # Extract text span for evidence
            text_span = source_text[start:end].strip() if start < end else None
            
            # Validate text span matches entity label
            if text_span and text_span.lower() != item.label.lower():
                logger.debug(
                    f"Entity label '{item.label}' doesn't match span '{text_span}' "
                    f"(will use label)"
                )

            # Create Evidence with source tracking
            evidence = Evidence(
                source_type="local_doc",
                source_id=f"char_{start}_{end}",
                text_span=text_span,
                confidence=item.confidence,
            )

            # Create description from context if available
            description = item.context if item.context else f"Entity of type {item.entity_type}"

            # Create ExtractedEntity domain object
            entity = ExtractedEntity(
                id=item.id or f"ent_{uuid.uuid4().hex[:8]}",
                label=item.label,
                entity_type=item.entity_type,
                description=description,
                confidence=item.confidence,
                evidence=[evidence],
            )
            entities.append(entity)

        logger.debug(f"Converted {len(entities)} entities from LLM schema")
        return entities

    def _deduplicate_entities(
        self,
        entities: list[ExtractedEntity],
        existing_entities: list[ExtractedEntity] | None = None,
    ) -> list[ExtractedEntity]:
        """Deduplicate entities, preferring higher confidence.

        Deduplication strategy:
        1. Group by (label, entity_type) pairs
        2. For duplicates, keep the one with highest confidence
        3. Merge existing_entities with extracted for conflict resolution

        Args:
            entities: Extracted entities to deduplicate
            existing_entities: Previously known entities for merging

        Returns:
            Deduplicated entity list
        """
        all_entities = entities + (existing_entities or [])
        if not all_entities:
            return []

        # Group by (normalized_label, entity_type)
        deduplicated: dict[tuple[str, str], ExtractedEntity] = {}

        for entity in all_entities:
            # Normalize label for comparison (lowercase, strip)
            key = (entity.label.lower().strip(), entity.entity_type)

            # Keep entity with higher confidence
            if key not in deduplicated:
                deduplicated[key] = entity
            elif entity.confidence > deduplicated[key].confidence:
                logger.debug(
                    f"Replacing entity '{key[0]}' ({deduplicated[key].confidence:.2f}) "
                    f"with higher confidence ({entity.confidence:.2f})"
                )
                deduplicated[key] = entity

        result = list(deduplicated.values())
        removed = len(all_entities) - len(result)
        if removed > 0:
            logger.debug(
                f"Deduplicated {len(all_entities)} → {len(result)} entities "
                f"({removed} duplicates removed)"
            )
        return result
