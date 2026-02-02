"""Knowledge graph assembly and construction.

Implementation of Issue #6.1: KG Assembly Engine

TODO:
- [ ] Define KGAssembler protocol for pluggable strategies
- [ ] Implement basic graph assembly from extracted entities/relations
  - Create nodes from entities
  - Create edges from relations
  - Set entity properties
  - Store provenance (evidence links)
- [ ] Implement entity deduplication/merging
  - Exact match (same URI)
  - Fuzzy match (similar labels)
  - Coreference resolution hints from extraction
- [ ] Implement relation deduplication
- [ ] Implement graph statistics tracking
  - Node/edge counts
  - Property distributions
  - Confidence metrics
- [ ] Add transaction support for atomic updates
- [ ] Add rollback capability
- [ ] Add unit and integration tests

See Planning/ISSUES_BACKLOG.md Issue #6.1 for acceptance criteria.
"""

from .core import GraphStatistics, KGAssembler, SimpleKGAssembler

__all__ = [
    "KGAssembler",
    "SimpleKGAssembler",
    "GraphStatistics",
]
