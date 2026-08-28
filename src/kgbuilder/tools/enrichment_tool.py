"""Semantic enrichment tool wrapping SemanticEnrichmentPipeline."""

from __future__ import annotations

from typing import Any

from kgbuilder.tools.base import AgentTool


def _enrichment_handler(pipeline: Any, entities: list[Any], relations: list[Any] | None = None) -> Any:
    """Run the semantic enrichment pipeline over entities/relations."""
    return pipeline.enrich(entities=entities, relations=relations)


EnrichmentTool = AgentTool(
    name="semantic_enrichment",
    description=(
        "Run the 5-phase semantic enrichment pipeline (descriptions, embeddings, "
        "competency questions, type constraints, aliases) over entities and relations."
    ),
    parameters={
        "type": "object",
        "properties": {
            "entities": {"type": "array"},
            "relations": {"type": "array"},
        },
        "required": ["entities"],
    },
    handler=_enrichment_handler,
)
