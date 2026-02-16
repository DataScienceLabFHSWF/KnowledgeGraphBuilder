"""Knowledge graph assembly and construction.

Implementation of Issue #6.1: KG Assembly Engine

Provides:
- SimpleKGAssembler: Document-to-KG pipeline orchestration (Neo4j-specific)
- KGAssembler (Protocol-based): Backend-agnostic assembler for any GraphStore
- GraphStatistics: KG metrics and statistics
- AssemblyResult: Result of KG assembly operation
- LangChain LCEL-based orchestration
"""

# New protocol-based assembler (Phase 6)
from kgbuilder.assembly.assembler import (
    KGAssembler as ProtocolKGAssembler,
)
from kgbuilder.assembly.assembler import (
    KGAssemblyResult,
    assemble_to_dict,
    assemble_to_json,
)
from kgbuilder.assembly.core import (
    AssemblyResult,
    GraphStatistics,
    KGAssembler,
    SimpleKGAssembler,
)

# Multi-store orchestrator (Phase 7)
from kgbuilder.assembly.kg_builder import (
    KGBuilder,
    KGBuilderConfig,
    KGBuildResult,
)

__all__ = [
    # Legacy exports
    "SimpleKGAssembler",
    "KGAssembler",
    "GraphStatistics",
    "AssemblyResult",
    # New protocol-based exports (Phase 6)
    "ProtocolKGAssembler",
    "KGAssemblyResult",
    "assemble_to_json",
    "assemble_to_dict",
    # Multi-store orchestrator (Phase 7)
    "KGBuilder",
    "KGBuilderConfig",
    "KGBuildResult",
]

