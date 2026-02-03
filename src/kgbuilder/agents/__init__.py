"""Agent framework for orchestration.

Implementation of Issues #4.2-#4.4: Agent Framework

TODO (Tool Framework - Issue #4.2):
- [ ] Define Tool protocol (name, description, parameters, execute)
- [ ] Implement VectorSearchTool for document search
- [ ] Implement OntologyQueryTool for ontology exploration
- [ ] Implement KGQueryTool for graph queries
- [ ] Implement ValidationTool for SHACL/CQ validation
- [ ] Add JSON schema parameter validation
- [ ] Add tool registry and auto-discovery
- [ ] Add unit tests for each tool

TODO (Base Agent - Issue #4.3):
- [ ] Define Agent base class
- [ ] Implement ReAct-style reasoning loop
  - Thought generation
  - Action selection
  - Tool execution
  - Observation integration
- [ ] Add multi-turn conversation support
- [ ] Add execution trace logging
- [ ] Add error recovery with retries
- [ ] Add unit tests

TODO (Agent Orchestration - Issue #4.4):
- [ ] Define Pipeline abstraction (DAG-based)
- [ ] Implement sequential pipeline execution
- [ ] Implement parallel agent execution (optional)
- [ ] Add checkpointing for long-running pipelines
- [ ] Add resource management (token budgets, timeouts)
- [ ] Add message passing between agents
- [ ] Add integration tests

TODO (Specific agents):
- [ ] QuestionGeneratorAgent (generates CQs from ontology)
- [ ] DeepResearchAgent (performs iterative research)
- [ ] KGBuilderAgent (orchestrates KG construction)
- [ ] ValidationAgent (runs validation pipeline)

See Planning/ISSUES_BACKLOG.md Issues #4.2-#4.4 for acceptance criteria.
"""

from kgbuilder.agents.discovery_loop import (
    DiscoveryResult,
    IterativeDiscoveryLoop,
    IterationResult,
)
from kgbuilder.agents.question_generator import (
    OntologyService,
    QuestionGenerationAgent,
    ResearchQuestion,
)

__all__ = [
    "QuestionGenerationAgent",
    "OntologyService",
    "ResearchQuestion",
    "IterativeDiscoveryLoop",
    "DiscoveryResult",
    "IterationResult",
]
