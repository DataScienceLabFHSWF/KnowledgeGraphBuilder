"""LangChain-based extraction chains for entity and relation extraction.

Implements unified LCEL (LangChain Expression Language) chains for:
- Entity extraction with ontology guidance
- Relation extraction with constraint validation
- Confidence scoring and deduplication
- Provenance tracking
"""

from __future__ import annotations

import logging
import os

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_ollama import ChatOllama

from kgbuilder.core import get_base_url
from kgbuilder.core.models import ExtractedEntity
from kgbuilder.extraction.entity import OntologyClassDef
from kgbuilder.extraction.relation import OntologyRelationDef
from kgbuilder.extraction.schemas import EntityExtractionOutput, RelationExtractionOutput

logger = logging.getLogger(__name__)


class ExtractionChains:
    """Factory for creating extraction chains using LangChain LCEL.
    
    Provides standardized chains for entity and relation extraction
    with full ontology integration and confidence scoring.
    """

    @staticmethod
    def _fix_json_arithmetic(text: str) -> str:
        """Convert simple arithmetic expressions in JSON values to numeric results.

        Some LLMs output things like ``"end_char": 266 + 18`` which is invalid
        JSON.  This helper finds occurrences of unquoted arithmetic and evaluates
        them safely, leaving the rest of the text untouched.
        """
        import re

        pattern = r'("[^"]+"\s*:\s*)(\d+(?:\s*[+\-*/]\s*\d+)+)(\s*[,}\n])'

        def replace_expr(match):
            prefix = match.group(1)
            expr = match.group(2)
            suffix = match.group(3)
            try:
                expr_clean = expr.replace(" ", "")
                if all(c in "0123456789+-*/" for c in expr_clean):
                    result = int(eval(expr_clean))
                    return f"{prefix}{result}{suffix}"
            except Exception:
                return match.group(0)
            return match.group(0)

        return re.sub(pattern, replace_expr, text)

    @staticmethod
    def _safe_parse(parser, x):
        """Wrapper around output parser that fixes arithmetic expressions first.

        Returns an empty output on failure instead of raising.
        """
        try:
            json_text = ExtractionChains._fix_json_arithmetic(x.content)
            return parser.parse(json_text)
        except Exception as e:
            logger.warning(f"JSON parsing failed, returning empty: {str(e)[:100]}")
            return EntityExtractionOutput(entities=[])

    @staticmethod
    def create_entity_extraction_chain(
        model: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.5,
    ) -> Runnable:
        """Create entity extraction chain using LCEL.
        
        Chain flow:
        1. Format ontology classes for prompt
        2. Send to LLM with structured output schema

        3. Parse and validate output
        4. Return ExtractedEntity objects
        
        Args:
            model: Ollama model name (default: OLLAMA_MODEL env var or qwen3:8b)
            base_url: Ollama API base URL
            temperature: LLM temperature (lower = more deterministic)
            
        Returns:
            LCEL Runnable chain for entity extraction
        """
        model = model or os.environ.get("OLLAMA_LLM_MODEL", os.environ.get("OLLAMA_MODEL", "qwen3:8b"))
        base_url = get_base_url(base_url)

        # Initialize LLM with structured output (attach Langsmith callbacks if enabled)
        from kgbuilder.telemetry.langsmith import get_langsmith_callbacks

        callbacks = get_langsmith_callbacks()
        llm = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=temperature,
            callbacks=callbacks if callbacks is not None else None,
        )

        # Create output parser
        parser = PydanticOutputParser(pydantic_object=EntityExtractionOutput)

        # Create prompt template with clearer format
        prompt = ChatPromptTemplate.from_template(
            """You are an entity extraction system. Extract named entities from the given text.

Entity types to identify:
{ontology_section}

TEXT:
{text}

Extract all entities. For each entity, provide:
- id: unique identifier like "ent_001"
- label: the exact text of the entity
- entity_type: one of the types listed above
- confidence: how confident (0.0 to 1.0)
- start_char: character position where entity starts (MUST BE AN INTEGER NUMBER, not an expression)
- end_char: character position where entity ends (MUST BE AN INTEGER NUMBER, not an expression. Example: if start is 266 and label is 18 chars, write 284 not 266+18)
- context: surrounding text for context

IMPORTANT: All character positions must be actual numbers, computed values.
DO NOT output arithmetic like "266 + 18" - compute it to "284"

Return ONLY valid JSON matching this format:
{{"entities": [
  {{"id": "ent_001", "label": "Example Entity", "entity_type": "Facility", "confidence": 0.95, "start_char": 0, "end_char": 15, "context": "Example Entity is..."}}
]}}

{format_instructions}
"""
        ).partial(format_instructions=parser.get_format_instructions())

        # Build chain with error handling
        chain = prompt | llm | (lambda x: ExtractionChains._safe_parse(parser, x))

        logger.info(f"[OK] Created entity extraction chain ({model})")
        return chain

    @staticmethod
    def create_relation_extraction_chain(
        model: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.5,
    ) -> Runnable:
        """Create relation extraction chain using LCEL.
        
        Chain flow:
        1. Format entities and ontology relations
        2. Send to LLM with relation extraction prompt
        3. Parse and validate output
        4. Return ExtractedRelation objects with constraint checking
        
        Args:
            model: Ollama model name (default: OLLAMA_MODEL env var or qwen3:8b)
            base_url: Ollama API base URL
            temperature: LLM temperature
            
        Returns:
            LCEL Runnable chain for relation extraction
        """
        model = model or os.environ.get("OLLAMA_LLM_MODEL", os.environ.get("OLLAMA_MODEL", "qwen3:8b"))
        base_url = get_base_url(base_url)

        # Initialize LLM (attach Langsmith callbacks if enabled)
        from kgbuilder.telemetry.langsmith import get_langsmith_callbacks

        callbacks = get_langsmith_callbacks()
        llm = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=temperature,
            callbacks=callbacks if callbacks is not None else None,
        )

        # Create output parser
        parser = PydanticOutputParser(pydantic_object=RelationExtractionOutput)

        # Create prompt template
        prompt = ChatPromptTemplate.from_template(
            """Extract relationships between the following entities from the text.

ENTITIES MENTIONED:
{entities_list}

VALID RELATIONSHIPS:
{relations_section}

TEXT TO ANALYZE:
{text}

For each relationship found:
1. Assign a unique ID (rel_XXX format)
2. Identify source and target entity IDs from the list above
3. Determine the relationship type from valid relationships
4. Estimate confidence (0.0-1.0)
5. Note the character positions of the relationship evidence
6. Ensure domain and range constraints are satisfied

Extract all valid relationships. Only include relationships between entities in the provided list.
Respect domain/range constraints from the relationship definitions.

{format_instructions}

JSON Response:"""
        ).partial(format_instructions=parser.get_format_instructions())

        # Build chain
        chain = prompt | llm | parser

        logger.info(f"[OK] Created relation extraction chain ({model})")
        return chain

    @staticmethod
    def format_ontology_section(ontology_classes: list[OntologyClassDef]) -> str:
        """Format ontology classes for prompt inclusion.
        
        Args:
            ontology_classes: Entity type definitions
            
        Returns:
            Formatted ontology section for prompt
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

    @staticmethod
    def format_entities_list(entities: list[ExtractedEntity]) -> str:
        """Format extracted entities for relation extraction prompt.
        
        Args:
            entities: Extracted entities
            
        Returns:
            Formatted entity list for prompt
        """
        lines = []
        for ent in entities:
            lines.append(
                f"- {ent.id}: {ent.label} (type: {ent.entity_type}, "
                f"confidence: {ent.confidence:.2f})"
            )
        return "\n".join(lines)

    @staticmethod
    def format_relations_section(
        ontology_relations: list[OntologyRelationDef],
    ) -> str:
        """Format ontology relations for prompt inclusion.
        
        Args:
            ontology_relations: Relation/property definitions
            
        Returns:
            Formatted relations section for prompt
        """
        lines = []
        for rel in ontology_relations:
            header = f"- **{rel.label}** ({rel.uri})"
            lines.append(header)

            if rel.description:
                lines.append(f"  Description: {rel.description}")

            if rel.domain:
                domain_str = ", ".join(rel.domain)
                lines.append(f"  Domain: {domain_str}")

            if rel.range:
                range_str = ", ".join(rel.range)
                lines.append(f"  Range: {range_str}")

            if rel.is_functional:
                lines.append("  Functional: Yes (at most one value)")
            if rel.is_symmetric:
                lines.append("  Symmetric: Yes")
            if rel.is_transitive:
                lines.append("  Transitive: Yes")

        return "\n".join(lines)


def build_extraction_pipeline() -> tuple[Runnable, Runnable]:
    """Build complete extraction pipeline using LCEL.
    
    Returns:
        Tuple of (entity_extraction_chain, relation_extraction_chain)
    """
    entity_chain = ExtractionChains.create_entity_extraction_chain()
    relation_chain = ExtractionChains.create_relation_extraction_chain()

    logger.info("[OK] Built complete extraction pipeline")
    return entity_chain, relation_chain
