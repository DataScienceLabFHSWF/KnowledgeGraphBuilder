"""Cross-domain linking between knowledge graph subgraphs.

Provides rule-based and keyword-driven linking between domain entities
and law/regulation graph nodes.
"""

from __future__ import annotations

from kgbuilder.linking.law_linker import KGLawLinker

__all__ = ["KGLawLinker"]
