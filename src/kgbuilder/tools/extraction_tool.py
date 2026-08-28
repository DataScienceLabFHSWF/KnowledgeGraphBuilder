"""Entity extraction tool wrapping EntityExtractor implementations."""

from __future__ import annotations

from typing import Any

from kgbuilder.tools.base import AgentTool


def _extraction_handler(
    extractor: Any,
    text: str,
    ontology_classes: list[Any],
    existing_entities: list[Any] | None = None,
) -> Any:
    """Extract entities from text guided by a module's ontology classes."""
    return extractor.extract(text=text, ontology_classes=ontology_classes, existing_entities=existing_entities)


ExtractionTool = AgentTool(
    name="entity_extraction",
    description="Extract entities from a text chunk guided by a set of ontology class definitions.",
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "ontology_classes": {"type": "array"},
            "existing_entities": {"type": "array"},
        },
        "required": ["text", "ontology_classes"],
    },
    handler=_extraction_handler,
)
