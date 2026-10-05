"""Law linking / cross-domain skills."""

from __future__ import annotations

from typing import Any

from kgbuilder.skills.base import AgentSkill
from kgbuilder.tools.law_linking_tool import LawContextTool, LawLinkingTool


def _law_linking_skill_handler(linker: Any, **kwargs: Any) -> Any:
    """Create cross-domain links between KG entities and law nodes."""
    return LawLinkingTool.handler(linker, **kwargs)


def _law_context_skill_handler(provider: Any, text: str) -> str:
    """Fetch relevant law context for a document chunk."""
    return LawContextTool.handler(provider, text=text)


LawLinkingSkill = AgentSkill(
    name="law_linking",
    description="Link decommissioning KG entities to relevant German law graph nodes.",
    handler=_law_linking_skill_handler,
)

LawContextSkill = AgentSkill(
    name="law_context_lookup",
    description="Retrieve relevant law paragraph context to augment extraction of a text chunk.",
    handler=_law_context_skill_handler,
)
