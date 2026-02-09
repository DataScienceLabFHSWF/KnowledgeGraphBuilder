"""LLM-based entity and relation extraction for German legal text.

Uses ontology-guided prompts with structured output to extract semantic
entities and relations that rule-based methods cannot capture. Complements
LegalRuleBasedExtractor in an ensemble configuration.

The extractor:
1. Loads ontology class definitions (from LKIF-Core / custom law ontology)
2. Builds extraction prompts with class descriptions + few-shot examples
3. Calls the LLM with structured output (JSON schema)
4. Parses and validates the response against ontology constraints

Usage::

    extractor = LegalLLMExtractor(llm=llm_provider, ontology=ontology_service)
    entities, relations = extractor.extract(text, paragraph_id="AtG_§ 7")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from kgbuilder.core.models import ExtractedEntity, ExtractedRelation


class LLMProvider(Protocol):
    """Protocol for LLM backends (matches existing KGB LLMProvider)."""

    def generate(self, prompt: str, **kwargs: Any) -> str: ...

    @property
    def model_name(self) -> str: ...


class OntologyService(Protocol):
    """Protocol for ontology access (matches existing KGB OntologyService)."""

    def get_class_definitions(self) -> list[dict[str, Any]]: ...
    def get_relation_definitions(self) -> list[dict[str, Any]]: ...


@dataclass
class LegalExtractionConfig:
    """Configuration for legal LLM extraction."""

    temperature: float = 0.1            # Low temp for precision
    max_tokens: int = 4096
    language: str = "de"                # Prompt language
    few_shot_examples: int = 3          # Examples per class
    confidence_threshold: float = 0.5   # Min confidence to keep
    batch_size: int = 5                 # Norms per LLM call (if batching)


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

ENTITY_EXTRACTION_SYSTEM_PROMPT = """\
Du bist ein Experte für deutsches Recht. Extrahiere strukturierte Entitäten
aus dem folgenden Gesetzestext. Verwende ausschließlich die Klassen aus der
bereitgestellten Ontologie.

Ontologie-Klassen:
{class_definitions}

Antworte ausschließlich im JSON-Format:
{{
  "entities": [
    {{
      "label": "...",
      "entity_type": "...",
      "description": "...",
      "confidence": 0.0-1.0,
      "evidence_span": "..."
    }}
  ]
}}
"""

RELATION_EXTRACTION_SYSTEM_PROMPT = """\
Du bist ein Experte für deutsches Recht. Gegeben sind Entitäten und
Gesetzestext. Extrahiere Relationen zwischen den Entitäten.

Erlaubte Relationen:
{relation_definitions}

Bereits extrahierte Entitäten:
{entities_json}

Antworte ausschließlich im JSON-Format:
{{
  "relations": [
    {{
      "source": "...",
      "target": "...",
      "predicate": "...",
      "confidence": 0.0-1.0,
      "evidence_span": "..."
    }}
  ]
}}
"""


@dataclass
class LegalLLMExtractor:
    """Ontology-guided LLM extractor for German legal text.

    Uses the custom law ontology (aligned to LKIF-Core / ELI) to generate
    extraction prompts and validate LLM outputs.
    """

    llm: LLMProvider
    ontology: OntologyService
    config: LegalExtractionConfig = field(default_factory=LegalExtractionConfig)

    def extract(
        self,
        text: str,
        paragraph_id: str = "",
        law_abbr: str = "",
    ) -> tuple[list[ExtractedEntity], list[ExtractedRelation]]:
        """Extract entities and relations from legal text using LLM.

        Two-pass extraction:
        1. Entity extraction with ontology class definitions
        2. Relation extraction with extracted entities as context

        Args:
            text: Plain text of a law paragraph.
            paragraph_id: Identifier (e.g. "§ 7").
            law_abbr: Source law abbreviation (e.g. "AtG").

        Returns:
            Tuple of (entities, relations).
        """
        raise NotImplementedError  # TODO: Step 5 implementation

    def extract_entities(
        self,
        text: str,
        paragraph_id: str = "",
    ) -> list[ExtractedEntity]:
        """Extract entities only (first pass)."""
        raise NotImplementedError  # TODO: Step 5 implementation

    def extract_relations(
        self,
        text: str,
        entities: list[ExtractedEntity],
        paragraph_id: str = "",
    ) -> list[ExtractedRelation]:
        """Extract relations given pre-extracted entities (second pass)."""
        raise NotImplementedError  # TODO: Step 5 implementation

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _build_entity_prompt(self, text: str, paragraph_id: str) -> str:
        """Build entity extraction prompt from ontology + text."""
        raise NotImplementedError

    def _build_relation_prompt(
        self, text: str, entities: list[ExtractedEntity], paragraph_id: str
    ) -> str:
        """Build relation extraction prompt from ontology + entities + text."""
        raise NotImplementedError

    def _format_class_definitions(self) -> str:
        """Format ontology classes for prompt injection."""
        raise NotImplementedError

    def _format_relation_definitions(self) -> str:
        """Format ontology relations for prompt injection."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_entity_response(
        self, response: str, paragraph_id: str
    ) -> list[ExtractedEntity]:
        """Parse JSON entity response from LLM."""
        raise NotImplementedError

    def _parse_relation_response(
        self, response: str, paragraph_id: str
    ) -> list[ExtractedRelation]:
        """Parse JSON relation response from LLM."""
        raise NotImplementedError

    def _validate_against_ontology(
        self, entities: list[ExtractedEntity]
    ) -> list[ExtractedEntity]:
        """Filter entities whose types don't exist in the ontology."""
        raise NotImplementedError
