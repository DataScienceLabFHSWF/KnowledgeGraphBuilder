"""Declarative pipeline agent.

Replaces ad-hoc hardcoded call sequences with a small ordered plan of skill
invocations. Each plan step names a registered skill and the keyword
arguments to pass; bound resources (retriever, pipeline, linker, ...) are
supplied by the caller via `bindings` and merged into each step's kwargs.
"""

from __future__ import annotations

from collections.abc import Callable
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
    id: str | None = None
    inputs: dict[str, str] = field(default_factory=dict)  # kwarg name -> prior step output


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

    def run_plan(
        self,
        steps: list[PipelineStep],
        on_step: Callable[[PipelineStep, str, Any | None, int], None] | None = None,
        iterations: int = 1,
        stop_if_empty: str | None = None,
    ) -> list[Any]:
        """Execute an ordered plan with result flow and optional empty-result stopping."""
        if iterations < 1:
            raise ValueError("iterations must be at least 1")
        results: list[Any] = []
        stop = False
        for iteration in range(1, iterations + 1):
            results_by_id: dict[str, Any] = {}
            for index, step in enumerate(steps):
                step_id = step.id or str(index)
                skill = get_skill(step.skill)
                resolved_kwargs = dict(step.kwargs)
                for kwarg_name, binding_key in step.bind.items():
                    if binding_key not in self._bindings:
                        raise ValueError(
                            f"Missing binding '{binding_key}' required by step '{step.skill}'"
                        )
                    resolved_kwargs[kwarg_name] = self._bindings[binding_key]
                for kwarg_name, reference in step.inputs.items():
                    source_id, _, attribute = reference.partition(".")
                    if source_id not in results_by_id:
                        raise ValueError(
                            f"Step '{step_id}' references unavailable result '{source_id}'"
                        )
                    value = results_by_id[source_id]
                    if attribute:
                        for part in attribute.split("."):
                            value = value[part] if isinstance(value, dict) else getattr(value, part)
                    resolved_kwargs[kwarg_name] = value
                if on_step:
                    on_step(step, "running", None, iteration)
                try:
                    result = skill.execute(**resolved_kwargs)
                except Exception as exc:
                    if on_step:
                        on_step(step, "failed", exc, iteration)
                    raise
                results.append(result)
                results_by_id[step_id] = result
                if on_step:
                    on_step(step, "completed", result, iteration)
                if step_id == stop_if_empty and not result:
                    stop = True
                    break
            if stop:
                break
        return results
