"""Agent-swarm configuration: per-module model assignment and concurrency limits.

Lets an operator assign a different (e.g. smaller/cheaper) LLM to each
ontology module's extraction subagent, and bound how many subagents run
concurrently against a shared inference backend (Ollama or an
OpenAI-compatible server such as vLLM).

This config is deliberately backend-agnostic: it only says *which model
name* to use per module and *how many* subagents may run at once. Building
the actual retriever/extractor instances per model is left to a factory
callable supplied by the caller, so this module has no hard dependency on
any specific LLM client.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from kgbuilder.agents.orchestrator_agent import ModuleBinding, OrchestratorAgent


@dataclass
class SwarmModelConfig:
    """Model/concurrency configuration for a module-orchestrated agent swarm.

    Attributes:
        backend: Inference backend identifier ("ollama" or "vllm"). Informational —
            the caller's retriever/extractor factories decide how to honor it.
        base_url: Base URL of the inference server.
        default_model: Model used for modules with no entry in `module_models`.
        module_models: Per-module model overrides (module name -> model name).
        max_concurrent_agents: Max module subagents run concurrently
            (`OrchestratorAgent(max_workers=...)`).
        request_timeout_s: Per-request timeout passed through to LLM clients.
    """

    backend: str = "ollama"
    base_url: str = "http://localhost:11434"
    default_model: str = "qwen3:8b"
    module_models: dict[str, str] = field(default_factory=dict)
    max_concurrent_agents: int = 3
    request_timeout_s: int = 120

    def model_for_module(self, module_name: str) -> str:
        """Resolve the model name assigned to a module (falls back to `default_model`)."""
        return self.module_models.get(module_name, self.default_model)

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dict."""
        return {
            "backend": self.backend,
            "base_url": self.base_url,
            "default_model": self.default_model,
            "module_models": dict(self.module_models),
            "max_concurrent_agents": self.max_concurrent_agents,
            "request_timeout_s": self.request_timeout_s,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> SwarmModelConfig:
        """Build from a plain dict (e.g. parsed JSON)."""
        return SwarmModelConfig(
            backend=data.get("backend", "ollama"),
            base_url=data.get("base_url", "http://localhost:11434"),
            default_model=data.get("default_model", "qwen3:8b"),
            module_models=dict(data.get("module_models", {})),
            max_concurrent_agents=int(data.get("max_concurrent_agents", 3)),
            request_timeout_s=int(data.get("request_timeout_s", 120)),
        )

    @staticmethod
    def from_json(path: str | Path) -> SwarmModelConfig:
        """Load from a JSON config file."""
        return SwarmModelConfig.from_dict(json.loads(Path(path).read_text()))


def build_module_bindings_with_swarm_config(
    module_map: dict[str, list[Any]],
    questions: list[Any],
    retriever_factory: Callable[[str], Any],
    extractor_factory: Callable[[str], Any],
    swarm_config: SwarmModelConfig,
    top_k: int = 10,
) -> list[ModuleBinding]:
    """Build one `ModuleBinding` per module, using `swarm_config` to pick each module's model.

    One extractor/retriever instance is constructed per distinct model name
    (via the supplied factories) and shared across all modules assigned that
    model, so modules sharing a model don't spin up redundant clients.

    Args:
        module_map: Ontology module name -> class definitions (see
            `OntologyService.get_module_class_map`).
        questions: Research questions to assign to modules by `entity_class`.
        retriever_factory: Callable(model_name) -> retriever instance.
        extractor_factory: Callable(model_name) -> EntityExtractor instance.
        swarm_config: Per-module model assignment and concurrency limits.
        top_k: Documents to retrieve per research question.

    Returns:
        One `ModuleBinding` per module with a non-empty question assignment.
    """
    resources_by_model: dict[str, tuple[Any, Any]] = {}

    def _resources_for(model_name: str) -> tuple[Any, Any]:
        if model_name not in resources_by_model:
            resources_by_model[model_name] = (retriever_factory(model_name), extractor_factory(model_name))
        return resources_by_model[model_name]

    base_bindings = OrchestratorAgent.build_module_bindings(
        module_map=module_map,
        questions=questions,
        retriever=None,
        extractor=None,
        top_k=top_k,
    )

    swarm_bindings: list[ModuleBinding] = []
    for binding in base_bindings:
        model_name = swarm_config.model_for_module(binding.module_name)
        retriever, extractor = _resources_for(model_name)
        swarm_bindings.append(
            ModuleBinding(
                module_name=binding.module_name,
                ontology_classes=binding.ontology_classes,
                retriever=retriever,
                extractor=extractor,
                questions=binding.questions,
                top_k=top_k,
            )
        )
    return swarm_bindings
