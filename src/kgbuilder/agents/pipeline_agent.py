"""Declarative pipeline agent.

Replaces ad-hoc hardcoded call sequences with a small ordered plan of skill
invocations. Each plan step names a registered skill and the keyword
arguments to pass; bound resources (retriever, pipeline, linker, ...) are
supplied by the caller via `bindings` and merged into each step's kwargs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from kgbuilder.agents.base_agent import BaseAgent
from kgbuilder.agents.registry import ALL_SKILLS, ALL_TOOLS, get_skill


@dataclass
class PipelineStep:
    """One step of a declarative pipeline plan."""

    skill: str
    kwargs: dict[str, Any] = field(default_factory=dict)
    bind: dict[str, str] = field(default_factory=dict)  # kwarg name -> binding key


class PipelineAgent(BaseAgent):
    """Runs a declared plan of skills instead of a fixed hardcoded pipeline.

    Example:
        agent = PipelineAgent(bindings={"retriever": my_retriever})
        agent.run_plan([
            PipelineStep(skill="document_retrieval", kwargs={"query": "..."}, bind={"retriever": "retriever"}),
        ])
    """

    def __init__(self, bindings: dict[str, Any] | None = None) -> None:
        super().__init__(name="pipeline_agent", skills=ALL_SKILLS, tools=ALL_TOOLS)
        self._bindings = bindings or {}

    def run(self, prompt: str, **kwargs: Any) -> Any:
        """Run a single skill by name; `prompt` is treated as the skill name."""
        return self.run_skill(prompt, **kwargs)

    def run_plan(self, steps: list[PipelineStep]) -> list[Any]:
        """Execute an ordered plan of skill invocations and return their results."""
        results: list[Any] = []
        for step in steps:
            skill = get_skill(step.skill)
            resolved_kwargs = dict(step.kwargs)
            for kwarg_name, binding_key in step.bind.items():
                if binding_key not in self._bindings:
                    raise ValueError(f"Missing binding '{binding_key}' required by step '{step.skill}'")
                resolved_kwargs[kwarg_name] = self._bindings[binding_key]
            results.append(skill.execute(**resolved_kwargs))
        return results
