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

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import BaseModel, Field

from kgbuilder.core.models import ExtractedEntity, ExtractedRelation, Evidence, generate_entity_id
from kgbuilder.extraction.aligner import TextAligner, AlignmentStatus


class LLMProvider(Protocol):
    """Protocol for LLM backends (matches existing KGB LLMProvider)."""

    def generate_structured(self, prompt: str, schema: type[BaseModel], **kwargs: Any) -> Any: ...

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
    verify_evidence: bool = True        # Whether to verify evidence spans match text


# ---------------------------------------------------------------------------
# Pydantic schemas for structured output
# ---------------------------------------------------------------------------

class LegalEntityItem(BaseModel):
    """Schema for individual legal entity extraction."""

    label: str = Field(description="Entity label/name from text")
    entity_type: str = Field(description="Ontology class type")
    description: str = Field(description="Brief description of the entity")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")
    evidence_span: str = Field(description="Exact text span that supports this entity")


class LegalEntityExtractionOutput(BaseModel):
    """Schema for legal entity extraction JSON output."""

    entities: list[LegalEntityItem] = Field(description="List of extracted legal entities")


class LegalRelationItem(BaseModel):
    """Schema for individual legal relation extraction."""

    source: str = Field(description="Source entity label")
    target: str = Field(description="Target entity label")
    predicate: str = Field(description="Relation type from ontology")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")
    evidence_span: str = Field(description="Text span supporting this relation")


class LegalRelationExtractionOutput(BaseModel):
    """Schema for legal relation extraction JSON output."""

    relations: list[LegalRelationItem] = Field(description="List of extracted legal relations")


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

    def __post_init__(self) -> None:
        """Initialize internal components."""
        self._aligner = TextAligner()

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
        entities = self.extract_entities(text, paragraph_id)
        relations = self.extract_relations(text, entities, paragraph_id)
        return entities, relations

    def extract_entities(
        self,
        text: str,
        paragraph_id: str = "",
    ) -> list[ExtractedEntity]:
        """Extract entities only (first pass)."""
        if not text or not text.strip():
            return []

        prompt = self._build_entity_prompt(text, paragraph_id)

        try:
            output: LegalEntityExtractionOutput = self.llm.generate_structured(
                prompt,
                LegalEntityExtractionOutput,
            )

            if not output.entities:
                return []

            return self._parse_entity_response(output, paragraph_id, source_text=text)

        except Exception as e:
            raise RuntimeError(f"Entity extraction failed: {e}") from e

    def extract_relations(
        self,
        text: str,
        entities: list[ExtractedEntity],
        paragraph_id: str = "",
    ) -> list[ExtractedRelation]:
        """Extract relations given pre-extracted entities (second pass)."""
        if not text or not entities:
            return []

        prompt = self._build_relation_prompt(text, entities, paragraph_id)

        try:
            output: LegalRelationExtractionOutput = self.llm.generate_structured(
                prompt,
                LegalRelationExtractionOutput,
            )

            if not output.relations:
                return []

            return self._parse_relation_response(output, paragraph_id)

        except Exception as e:
            raise RuntimeError(f"Relation extraction failed: {e}") from e

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _build_entity_prompt(self, text: str, paragraph_id: str) -> str:
        """Build entity extraction prompt from ontology + text."""
        class_defs = self._format_class_definitions()

        prompt = ENTITY_EXTRACTION_SYSTEM_PROMPT.format(
            class_definitions=class_defs
        )

        if paragraph_id:
            prompt += f"\n\nParagraph: {paragraph_id}"

        prompt += f"\n\nText:\n{text}\n\n"

        return prompt

    def _build_relation_prompt(
        self, text: str, entities: list[ExtractedEntity], paragraph_id: str
    ) -> str:
        """Build relation extraction prompt from ontology + entities + text."""
        relation_defs = self._format_relation_definitions()

        # Format entities as JSON for the prompt
        entities_data = [
            {
                "label": e.label,
                "type": e.entity_type,
                "description": getattr(e, 'description', '')
            }
            for e in entities
        ]
        entities_json = json.dumps(entities_data, ensure_ascii=False, indent=2)

        prompt = RELATION_EXTRACTION_SYSTEM_PROMPT.format(
            relation_definitions=relation_defs,
            entities_json=entities_json
        )

        if paragraph_id:
            prompt += f"\n\nParagraph: {paragraph_id}"

        prompt += f"\n\nText:\n{text}\n\n"

        return prompt

    def _format_class_definitions(self) -> str:
        """Format ontology classes for prompt injection."""
        classes = self.ontology.get_class_definitions()
        if not classes:
            return "Keine Ontologie-Klassen verfügbar."

        formatted = []
        for cls in classes[:10]:  # Limit to first 10 classes
            label = cls.get('label', cls.get('name', 'Unknown'))
            desc = cls.get('description', 'Keine Beschreibung verfügbar.')
            formatted.append(f"- {label}: {desc}")

        return "\n".join(formatted)

    def _format_relation_definitions(self) -> str:
        """Format ontology relations for prompt injection."""
        relations = self.ontology.get_relation_definitions()
        if not relations:
            return "Keine Ontologie-Relationen verfügbar."

        formatted = []
        for rel in relations[:10]:  # Limit to first 10 relations
            label = rel.get('label', rel.get('name', 'Unknown'))
            desc = rel.get('description', 'Keine Beschreibung verfügbar.')
            formatted.append(f"- {label}: {desc}")

        return "\n".join(formatted)

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_entity_response(
        self, output: LegalEntityExtractionOutput, paragraph_id: str, source_text: str | None = None
    ) -> list[ExtractedEntity]:
        """Parse entity response from LLM."""
        entities = []
        for item in output.entities:
            # Verify evidence span if source text provided
            alignment = None
            confidence = item.confidence
            
            if source_text and self.config.verify_evidence:
                alignment = self._aligner.align(item.evidence_span, source_text)
                
                # Boost/Penalize confidence based on alignment
                if alignment.status == AlignmentStatus.EXACT:
                    confidence = min(1.0, confidence + 0.1)
                elif alignment.status == AlignmentStatus.FUZZY:
                    # Keep as is, maybe slight boost
                    pass
                elif alignment.status == AlignmentStatus.PARTIAL:
                    confidence = confidence * 0.8
                else: # MISSING
                    confidence = confidence * 0.5

            entity_id = generate_entity_id(item.label, item.entity_type)
            
            evidence_metadata = {
                "paragraph_id": paragraph_id,
                "description": item.description
            }
            if alignment:
                 evidence_metadata["alignment"] = alignment.status.value
                 evidence_metadata["matched_span"] = alignment.matched_text

            entity = ExtractedEntity(
                id=entity_id,
                label=item.label,
                entity_type=item.entity_type,
                description=item.description,
                confidence=confidence,
                evidence=[
                    Evidence(
                        source_type="text",
                        source_id=paragraph_id or "unknown",
                        text_span=item.evidence_span,
                        confidence=confidence
                    )
                ],
                properties=evidence_metadata  # Store validation metadata in properties
            )
            entities.append(entity)

        # Filter by confidence threshold
        filtered = [
            e for e in entities
            if e.confidence >= self.config.confidence_threshold
        ]

        # Validate against ontology
        return self._validate_against_ontology(filtered)

    def _parse_relation_response(
        self, output: LegalRelationExtractionOutput, paragraph_id: str
    ) -> list[ExtractedRelation]:
        """Parse relation response from LLM."""
        relations = []
        for item in output.relations:
            relation = ExtractedRelation(
                id=str(uuid.uuid4()),
                source_id="",  # Will be resolved later
                source_label=item.source,
                relation_type=item.predicate,
                target_id="",  # Will be resolved later
                target_label=item.target,
                confidence=item.confidence,
                evidence=[
                    Evidence(
                        source_text=item.evidence_span,
                        extraction_method="legal_llm",
                        confidence=item.confidence,
                        metadata={"paragraph_id": paragraph_id}
                    )
                ]
            )
            relations.append(relation)

        # Filter by confidence threshold
        filtered = [
            r for r in relations
            if r.confidence >= self.config.confidence_threshold
        ]

        return filtered

    def _validate_against_ontology(
        self, entities: list[ExtractedEntity]
    ) -> list[ExtractedEntity]:
        """Filter entities whose types don't exist in the ontology."""
        valid_classes = {cls.get('label', cls.get('name', '')) for cls in self.ontology.get_class_definitions()}

        if not valid_classes:
            return entities  # No validation possible

        validated = []
        for entity in entities:
            if entity.entity_type in valid_classes:
                validated.append(entity)

        return validated
