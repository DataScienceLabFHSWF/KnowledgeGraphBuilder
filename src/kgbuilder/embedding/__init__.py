"""Embedding and LLM providers.

Implementation of Issues #3.1, #3.2: Provider Interfaces

Provides:
- OllamaProvider: Local LLM inference via Ollama (QWEN3, qwen3-next, etc.)
- Structured and unstructured generation with Pydantic validation

See Planning/ISSUES_BACKLOG.md Issue #3.1 for acceptance criteria.
"""

from __future__ import annotations

from kgbuilder.embedding.ollama import OllamaProvider

__all__ = [
    "OllamaProvider",
]
