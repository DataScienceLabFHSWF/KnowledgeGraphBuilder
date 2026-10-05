"""Agent framework for orchestration.

Implementation of Issues #4.2-#4.4: Agent Framework

See Planning/ISSUES_BACKLOG.md Issues #4.2-#4.4 for acceptance criteria.
"""

from kgbuilder.agents.discovery_loop import (
    DiscoveryResult,
    IterationResult,
    IterativeDiscoveryLoop,
)
from kgbuilder.agents.module_extraction_agent import ModuleExtractionAgent
from kgbuilder.agents.orchestrator_agent import ModuleBinding, OrchestratorAgent
from kgbuilder.agents.question_generator import (
    CQType,
    OntologyService,
    QuestionGenerationAgent,
    ResearchQuestion,
)
from kgbuilder.agents.swarm_config import SwarmModelConfig, build_module_bindings_with_swarm_config
from kgbuilder.agents.validation_agent import ValidationAgent

__all__ = [
    "QuestionGenerationAgent",
    "OntologyService",
    "ResearchQuestion",
    "CQType",
    "ModuleExtractionAgent",
    "ModuleBinding",
    "OrchestratorAgent",
    "ValidationAgent",
    "SwarmModelConfig",
    "build_module_bindings_with_swarm_config",
    "IterativeDiscoveryLoop",
    "DiscoveryResult",
    "IterationResult",
]
