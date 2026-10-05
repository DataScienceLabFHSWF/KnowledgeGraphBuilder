"""Core skill abstractions for agentic workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class AgentSkill:
    """A reusable capability exposed by an agent.

    Skills represent higher-level intent, usually mapping to a bounded job such
    as ontology gap analysis or follow-up question generation.
    """

    name: str
    description: str
    handler: Callable[..., Any]

    def execute(self, **kwargs: Any) -> Any:
        """Execute the skill using the supplied keyword arguments."""
        return self.handler(**kwargs)
