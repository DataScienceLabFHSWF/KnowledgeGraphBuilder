"""Entity extraction using LLM with ontology guidance.

Implementation of Issue #5.1-#5.2: Entity Extraction

Key features:
- Ontology-guided prompting with class descriptions
- Multi-pass extraction for complex documents
- Entity deduplication within document
- Confidence score calibration
- Structured output validation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from kgbuilder.core.models import ExtractedEntity, Evidence


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

    TODO (Implementation):
    - [ ] Implement extract() with structured output
    - [ ] Add ontology-guided prompt generation
    - [ ] Add multi-pass extraction for complex documents
    - [ ] Add entity deduplication within document
    - [ ] Add confidence score calibration
    - [ ] Add coreference resolution hints
    - [ ] Add error recovery with retries
    - [ ] Add unit tests

    See Planning/ISSUES_BACKLOG.md Issue #5.2 for acceptance criteria.
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
            confidence_threshold: Minimum confidence for entities
            max_retries: Max retries on extraction failure
        """
        self._llm = llm_provider
        self.confidence_threshold = confidence_threshold
        self.max_retries = max_retries

    def extract(
        self,
        text: str,
        ontology_classes: list[OntologyClassDef],
        existing_entities: list[ExtractedEntity] | None = None,
    ) -> list[ExtractedEntity]:
        """Extract entities from text with ontology guidance.

        Args:
            text: Source text
            ontology_classes: Valid entity types
            existing_entities: Known entities for deduplication

        Returns:
            List of extracted entities
        """
        # TODO: Implement extraction pipeline
        # 1. Generate ontology-guided prompt
        # 2. Call LLM with structured output schema
        # 3. Parse JSON response
        # 4. Deduplicate and validate
        # 5. Filter by confidence threshold
        # 6. Return entities with evidence
        raise NotImplementedError("extract() not yet implemented")

    def _build_extraction_prompt(
        self, text: str, ontology_classes: list[OntologyClassDef]
    ) -> str:
        """Build structured extraction prompt with ontology guidance.

        Args:
            text: Source text
            ontology_classes: Entity types to extract

        Returns:
            Formatted prompt string
        """
        # TODO: Implement prompt generation
        # Include class descriptions, examples, constraints
        raise NotImplementedError("_build_extraction_prompt() not yet implemented")

    def _parse_extraction_output(self, output: str) -> list[ExtractedEntity]:
        """Parse and validate LLM structured output.

        Args:
            output: JSON output from LLM

        Returns:
            List of extracted entities
        """
        # TODO: Implement JSON parsing and validation
        raise NotImplementedError("_parse_extraction_output() not yet implemented")
