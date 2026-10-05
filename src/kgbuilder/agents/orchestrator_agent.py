"""Orchestrator agent: dynamically dispatches one subagent per ontology module.

Given a module map (module name -> ontology class definitions) and per-module
resource bindings (retriever/extractor, which may differ per module — e.g. a
smaller/cheaper model for a simpler module), the orchestrator builds one
`ModuleExtractionAgent` per module, runs each over its assigned research
questions, and joins the resulting entity lists into a single deduplicated
knowledge graph slice.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from kgbuilder.agents.base_agent import BaseAgent
from kgbuilder.agents.module_extraction_agent import ModuleExtractionAgent
from kgbuilder.core.models import ExtractedEntity
from kgbuilder.skills.join_skill import JoinModuleResultsSkill


@dataclass
class ModuleBinding:
    """Resources and questions assigned to a single ontology module."""

    module_name: str
    ontology_classes: list[Any]
    retriever: Any
    extractor: Any
    questions: list[Any]
    top_k: int = 10


class OrchestratorAgent(BaseAgent):
    """Builds and runs one `ModuleExtractionAgent` per ontology module, then joins results."""

    def __init__(self, max_workers: int = 3) -> None:
        super().__init__(name="orchestrator_agent", skills=[JoinModuleResultsSkill])
        self._max_workers = max_workers

    @staticmethod
    def build_module_bindings(
        module_map: dict[str, list[Any]],
        questions: list[Any],
        retriever: Any,
        extractor: Any,
        top_k: int = 10,
    ) -> list[ModuleBinding]:
        """Construct one `ModuleBinding` per module from an ontology module map.

        Each question is assigned to the module(s) matching its `entity_class`.
        If a class is not present in the module map, the question is kept with the
        first available module as a safe fallback so the pipeline still works for
        partial or noisy ontology metadata.
        """
        if not module_map:
            return []

        class_to_modules: dict[str, list[str]] = {}
        for module_name, classes in module_map.items():
            for class_name in classes:
                class_to_modules.setdefault(str(class_name).lower(), []).append(module_name)

        questions_by_module: dict[str, list[Any]] = {module_name: [] for module_name in module_map}
        fallback_module = next(iter(module_map))

        for question in questions:
            entity_class = getattr(question, "entity_class", None)
            module_names: list[str] = []
            if entity_class:
                module_names = class_to_modules.get(str(entity_class).lower(), [])
            if not module_names:
                module_names = [fallback_module]
            for module_name in module_names:
                questions_by_module.setdefault(module_name, []).append(question)

        bindings: list[ModuleBinding] = []
        for module_name, module_classes in module_map.items():
            module_questions = questions_by_module.get(module_name, [])
            if not module_questions:
                continue
            bindings.append(
                ModuleBinding(
                    module_name=module_name,
                    ontology_classes=list(module_classes),
                    retriever=retriever,
                    extractor=extractor,
                    questions=module_questions,
                    top_k=top_k,
                )
            )
        return bindings

    def run(self, prompt: str, **kwargs: Any) -> Any:
        """Compatibility hook; prefer `run_modules()` for the real workflow."""
        raise NotImplementedError("OrchestratorAgent.run_modules() is the entry point")

    def build_module_agents(self, bindings: list[ModuleBinding]) -> dict[str, ModuleExtractionAgent]:
        """Instantiate one extraction subagent per module binding."""
        return {
            binding.module_name: ModuleExtractionAgent(
                module_name=binding.module_name,
                ontology_classes=binding.ontology_classes,
                retriever=binding.retriever,
                extractor=binding.extractor,
                top_k=binding.top_k,
            )
            for binding in bindings
        }

    def run_modules(self, bindings: list[ModuleBinding], parallel: bool = True) -> list[ExtractedEntity]:
        """Run one subagent per module and join their results.

        Args:
            bindings: One `ModuleBinding` per ontology module to extract.
            parallel: Run module subagents concurrently (default) or sequentially.

        Returns:
            Deduplicated entities merged across all modules.
        """
        module_agents = self.build_module_agents(bindings)

        def _run_one(binding: ModuleBinding) -> tuple[str, list[ExtractedEntity]]:
            agent = module_agents[binding.module_name]
            return binding.module_name, agent.run_questions(binding.questions)

        results_by_module: dict[str, list[ExtractedEntity]] = {}
        if parallel and len(bindings) > 1:
            with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
                for module_name, entities in executor.map(_run_one, bindings):
                    results_by_module[module_name] = entities
        else:
            for binding in bindings:
                module_name, entities = _run_one(binding)
                results_by_module[module_name] = entities

        return self.run_skill("join_module_results", results_by_module=results_by_module)
