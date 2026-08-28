"""Semantic enrichment skill."""

from __future__ import annotations

from typing import Any

from kgbuilder.skills.base import AgentSkill
from kgbuilder.tools.enrichment_tool import EnrichmentTool


def _enrichment_skill_handler(pipeline: Any, entities: list[Any], relations: list[Any] | None = None) -> Any:
    """Run semantic enrichment as a skill (delegates to the enrichment tool)."""
    return EnrichmentTool.handler(pipeline, entities=entities, relations=relations)


EnrichmentSkill = AgentSkill(
    name="semantic_enrichment",
    description="Enrich extracted entities/relations with descriptions, embeddings, CQs, type scores, and aliases.",
    handler=_enrichment_skill_handler,
)
