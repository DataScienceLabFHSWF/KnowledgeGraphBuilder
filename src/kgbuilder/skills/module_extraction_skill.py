"""Module-scoped extraction skill: retrieve then extract for one question."""

from __future__ import annotations

from typing import Any

from kgbuilder.skills.base import AgentSkill
from kgbuilder.tools.extraction_tool import ExtractionTool
from kgbuilder.tools.retrieval_tool import RetrievalTool


def _module_extraction_handler(
    retriever: Any,
    extractor: Any,
    query: str,
    ontology_classes: list[Any],
    top_k: int = 10,
    existing_entities: list[Any] | None = None,
) -> list[Any]:
    """Retrieve documents for a question, then extract module-scoped entities from each."""
    retrieved = RetrievalTool.handler(retriever, query=query, top_k=top_k)
    entities: list[Any] = []
    for result in retrieved:
        content = getattr(result, "content", None) or (result.get("content") if isinstance(result, dict) else None)
        if not content:
            continue
        entities.extend(
            ExtractionTool.handler(
                extractor,
                text=content,
                ontology_classes=ontology_classes,
                existing_entities=existing_entities,
            )
        )
    return entities


ModuleExtractionSkill = AgentSkill(
    name="module_extraction",
    description=(
        "Retrieve documents relevant to a research question, then extract entities scoped "
        "to a single ontology module's class definitions."
    ),
    handler=_module_extraction_handler,
)
