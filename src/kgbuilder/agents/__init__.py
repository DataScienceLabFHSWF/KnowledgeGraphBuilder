"""Agent framework for orchestration.

Implementation of Issues #4.2-#4.4: Agent Framework

See Planning/ISSUES_BACKLOG.md Issues #4.2-#4.4 for acceptance criteria.
"""

from kgbuilder.agents.discovery_loop import (
    DiscoveryResult,
    IterationResult,
    IterativeDiscoveryLoop,
)
from kgbuilder.agents.question_generator import (
    CQType,
    OntologyService,
    QuestionGenerationAgent,
    ResearchQuestion,
)

__all__ = [
    "QuestionGenerationAgent",
    "OntologyService",
    "ResearchQuestion",
    "CQType",
    "IterativeDiscoveryLoop",
    "DiscoveryResult",
    "IterationResult",
]
