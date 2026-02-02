"""Knowledge graph assembly and construction.

Implementation of Issue #6.1: KG Assembly Engine

Provides:
- SimpleKGAssembler: Document-to-KG pipeline orchestration
- GraphStatistics: KG metrics and statistics
- AssemblyResult: Result of KG assembly operation
- LangChain LCEL-based orchestration
"""

from kgbuilder.assembly.core import (
    AssemblyResult,
    GraphStatistics,
    KGAssembler,
    SimpleKGAssembler,
)

__all__ = [
    "SimpleKGAssembler",
    "KGAssembler",
    "GraphStatistics",
    "AssemblyResult",
]

