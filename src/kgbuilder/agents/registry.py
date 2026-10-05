"""Central registry of all skills and tools available to agents.

This module is the single place that enumerates the skill/tool surface of
the system. Orchestration code should look up capabilities here instead of
hardcoding module-specific pipeline steps.
"""

from __future__ import annotations

from kgbuilder.skills import (
    EnrichmentSkill,
    FollowUpGapAnalysisSkill,
    KGValidationSkill,
    LawContextSkill,
    LawLinkingSkill,
    OntologyGapAnalysisSkill,
    QuestionValidationSkill,
    RetrievalEvaluationSkill,
    RetrievalSkill,
    SparqlQuestionValidationSkill,
)
from kgbuilder.skills.base import AgentSkill
from kgbuilder.skills.build_pipeline_skills import (
    BuildValidationSkill,
    FindingsSynthesisSkill,
    KGAssemblySkill,
    ModuleExtractionBatchSkill,
    RelationExtractionBatchSkill,
)
from kgbuilder.skills.join_skill import JoinModuleResultsSkill
from kgbuilder.skills.module_extraction_skill import ModuleExtractionSkill
from kgbuilder.tools import (
    ConsistencyCheckTool,
    CoverageSnapshotTool,
    CQSparqlTool,
    EnrichmentTool,
    EvaluationTool,
    LawContextTool,
    LawLinkingTool,
    OntologyConsistencyReasoningTool,
    OntologyPitfallScanTool,
    OntologyQueryTool,
    RelationExtractionTool,
    RetrievalTool,
    RulesEngineTool,
    SHACLValidationTool,
    StaticValidationTool,
    ValidationTool,
)
from kgbuilder.tools.base import AgentTool
from kgbuilder.tools.extraction_tool import ExtractionTool

ALL_SKILLS: list[AgentSkill] = [
    OntologyGapAnalysisSkill,
    FollowUpGapAnalysisSkill,
    EnrichmentSkill,
    RetrievalSkill,
    RetrievalEvaluationSkill,
    LawLinkingSkill,
    LawContextSkill,
    ModuleExtractionSkill,
    JoinModuleResultsSkill,
    ModuleExtractionBatchSkill,
    RelationExtractionBatchSkill,
    FindingsSynthesisSkill,
    KGAssemblySkill,
    BuildValidationSkill,
    KGValidationSkill,
    QuestionValidationSkill,
    SparqlQuestionValidationSkill,
]

ALL_TOOLS: list[AgentTool] = [
    OntologyQueryTool,
    CoverageSnapshotTool,
    EnrichmentTool,
    RetrievalTool,
    EvaluationTool,
    LawLinkingTool,
    LawContextTool,
    ExtractionTool,
    ValidationTool,
    RelationExtractionTool,
    StaticValidationTool,
    SHACLValidationTool,
    RulesEngineTool,
    ConsistencyCheckTool,
    OntologyConsistencyReasoningTool,
    OntologyPitfallScanTool,
    CQSparqlTool,
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
