"""Relation extraction tool wrapping RelationExtractor implementations."""

from __future__ import annotations

from typing import Any

from kgbuilder.tools.base import AgentTool


def _relation_extraction_handler(
    relation_extractor: Any,
    text: str,
    entities: list[Any],
    ontology_relations: list[Any],
) -> Any:
    """Extract relations between entities from text guided by ontology relation definitions."""
    return relation_extractor.extract(text=text, entities=entities, ontology_relations=ontology_relations)


RelationExtractionTool = AgentTool(
    name="relation_extraction",
    description="Extract relations between known entities in a text chunk guided by ontology relation definitions.",
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "entities": {"type": "array"},
            "ontology_relations": {"type": "array"},
        },
        "required": ["text", "entities", "ontology_relations"],
    },
    handler=_relation_extraction_handler,
)
