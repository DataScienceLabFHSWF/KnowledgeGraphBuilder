"""Shared fixtures for KGBuilder API tests.

Provides a FastAPI TestClient with all backend dependencies mocked out,
so tests run without Neo4j, Qdrant, Fuseki, or Ollama.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ── Mock objects ─────────────────────────────────────────────────────────


@dataclass
class _MockStats:
    node_count: int = 42
    edge_count: int = 100
    nodes_by_type: dict[str, int] = field(default_factory=lambda: {"Entity": 30, "Law": 12})
    edges_by_type: dict[str, int] = field(default_factory=lambda: {"RELATES_TO": 80, "REFERENCES": 20})
    avg_confidence: float = 0.78


class _MockNeo4jStore:
    """Lightweight mock for Neo4jGraphStore."""

    def query(self, cypher: str, **kwargs):  # noqa: ANN001
        return [{"count": 1}]

    def get_statistics(self) -> _MockStats:
        return _MockStats()


class _MockQdrantStore:
    """Lightweight mock for QdrantStore."""

    def search(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return []


class _MockOntologyService:
    """Lightweight mock for FusekiOntologyService."""

    def get_all_classes(self) -> list[str]:
        return ["Person", "Organization", "Law"]

    def get_all_relations(self) -> list[str]:
        return ["RELATES_TO", "REFERENCES"]

    def get_class_hierarchy(self) -> list[tuple[str, str]]:
        return [("Person", "Agent"), ("Organization", "Agent")]


class _MockLLMProvider:
    """Lightweight mock for OllamaProvider."""

    model = "test-model"

    def generate(self, prompt: str) -> str:
        return '{"entities": []}'


# ── Patch targets ────────────────────────────────────────────────────────

_DEP_MODULE = "kgbuilder.api.dependencies"


@pytest.fixture()
def mock_neo4j():
    """Patch get_neo4j_store to return a mock."""
    store = _MockNeo4jStore()
    with patch(f"{_DEP_MODULE}.get_neo4j_store", return_value=store):
        yield store


@pytest.fixture()
def mock_qdrant():
    store = _MockQdrantStore()
    with patch(f"{_DEP_MODULE}.get_qdrant_store", return_value=store):
        yield store


@pytest.fixture()
def mock_ontology():
    svc = _MockOntologyService()
    with patch(f"{_DEP_MODULE}.get_ontology_service", return_value=svc):
        yield svc


@pytest.fixture()
def mock_llm():
    llm = _MockLLMProvider()
    with patch(f"{_DEP_MODULE}.get_llm_provider", return_value=llm):
        yield llm


@pytest.fixture()
def mock_all_deps(mock_neo4j, mock_qdrant, mock_ontology, mock_llm):
    """Convenience fixture that mocks all backend dependencies at once."""
    return {
        "neo4j": mock_neo4j,
        "qdrant": mock_qdrant,
        "ontology": mock_ontology,
        "llm": mock_llm,
    }


@pytest.fixture()
def client() -> TestClient:
    """Create a TestClient for the FastAPI app.

    Dependencies that need external services are imported lazily by
    routes, so the app object itself can be imported without mocks.
    """
    from kgbuilder.api.server import app

    return TestClient(app)
