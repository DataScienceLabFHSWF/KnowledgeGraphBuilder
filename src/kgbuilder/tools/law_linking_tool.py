"""Law linking tools wrapping KGLawLinker and LawContextProvider."""

from __future__ import annotations

from typing import Any

from kgbuilder.tools.base import AgentTool


def _law_linking_handler(linker: Any, **kwargs: Any) -> Any:
    """Create cross-domain links between KG entities and law graph nodes."""
    return linker.create_links(**kwargs)


def _law_context_handler(provider: Any, text: str) -> str:
    """Return relevant law paragraph context for a text chunk."""
    return provider.get_context(text)


LawLinkingTool = AgentTool(
    name="law_linking",
    description="Create cross-domain LINKED_* relationships between KG entities and law graph nodes.",
    parameters={
        "type": "object",
        "properties": {},
        "additionalProperties": True,
    },
    handler=_law_linking_handler,
)

LawContextTool = AgentTool(
    name="law_context_lookup",
    description="Retrieve relevant German law paragraph context for a document chunk via semantic search.",
    parameters={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    },
    handler=_law_context_handler,
)
