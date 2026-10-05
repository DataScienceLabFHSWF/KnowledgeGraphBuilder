"""Core tool abstractions for agentic workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class AgentTool:
    """A callable building block available to an agent at runtime."""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    handler: Callable[..., Any] | None = None

    def execute(self, **kwargs: Any) -> Any:
        """Execute the tool with the provided arguments."""
        if self.handler is None:
            raise ValueError(f"Tool '{self.name}' has no handler")
        return self.handler(**kwargs)
