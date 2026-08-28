"""Central registry of all skills and tools available to agents.

This module is the single place that enumerates the skill/tool surface of
the system. Orchestration code should look up capabilities here instead of
hardcoding module-specific pipeline steps.
"""

from __future__ import annotations

from kgbuilder.skills import (
    EnrichmentSkill,
    FollowUpGapAnalysisSkill,
    LawContextSkill,
    LawLinkingSkill,
    OntologyGapAnalysisSkill,
    RetrievalEvaluationSkill,
    RetrievalSkill,
)
from kgbuilder.skills.base import AgentSkill
from kgbuilder.tools import (
    CoverageSnapshotTool,
    EnrichmentTool,
    EvaluationTool,
    LawContextTool,
    LawLinkingTool,
    OntologyQueryTool,
    RetrievalTool,
)
from kgbuilder.tools.base import AgentTool

ALL_SKILLS: list[AgentSkill] = [
    OntologyGapAnalysisSkill,
    FollowUpGapAnalysisSkill,
    EnrichmentSkill,
    RetrievalSkill,
    RetrievalEvaluationSkill,
    LawLinkingSkill,
    LawContextSkill,
]

ALL_TOOLS: list[AgentTool] = [
    OntologyQueryTool,
    CoverageSnapshotTool,
    EnrichmentTool,
    RetrievalTool,
    EvaluationTool,
    LawLinkingTool,
    LawContextTool,
]

SKILL_REGISTRY: dict[str, AgentSkill] = {skill.name: skill for skill in ALL_SKILLS}
TOOL_REGISTRY: dict[str, AgentTool] = {tool.name: tool for tool in ALL_TOOLS}


def get_skill(name: str) -> AgentSkill:
    """Look up a registered skill by name."""
    if name not in SKILL_REGISTRY:
        available = ", ".join(sorted(SKILL_REGISTRY))
        raise ValueError(f"Unknown skill '{name}'. Available skills: {available}")
    return SKILL_REGISTRY[name]


def get_tool(name: str) -> AgentTool:
    """Look up a registered tool by name."""
    if name not in TOOL_REGISTRY:
        available = ", ".join(sorted(TOOL_REGISTRY))
        raise ValueError(f"Unknown tool '{name}'. Available tools: {available}")
    return TOOL_REGISTRY[name]
