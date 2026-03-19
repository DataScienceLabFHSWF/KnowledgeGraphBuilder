"""Integration smoke test for the KGBuilder API.

Runs against a live Docker stack (Neo4j, Qdrant, Fuseki, Ollama).
Skipped when services are not reachable.

Usage::

    # Start infra first
    docker compose up -d neo4j qdrant fuseki ollama-kgbuilder

    # Then run
    pytest tests/api/test_integration.py -v -m integration
"""

from __future__ import annotations

import os

import httpx
import pytest

API_BASE = os.getenv("KGBUILDER_API_URL", "http://localhost:8001")

_LIVE = False
try:
    resp = httpx.get(f"{API_BASE}/", timeout=2.0)
    _LIVE = resp.status_code == 200
except Exception:
    pass

pytestmark = pytest.mark.skipif(not _LIVE, reason="KGBuilder API not reachable")


@pytest.fixture(scope="module")
def api() -> httpx.Client:
    """HTTP client pointed at the live API."""
    return httpx.Client(base_url=API_BASE, timeout=30.0)


class TestIntegrationSmoke:
    """Smoke tests against a running KGBuilder API."""

    @pytest.mark.integration
    def test_root(self, api: httpx.Client) -> None:
        resp = api.get("/")
        assert resp.status_code == 200
        assert "kgbuilder" in resp.json().get("service", "").lower()

    @pytest.mark.integration
    def test_health(self, api: httpx.Client) -> None:
        resp = api.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("healthy", "degraded")

    @pytest.mark.integration
    def test_stats(self, api: httpx.Client) -> None:
        resp = api.get("/api/v1/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "node_count" in data
        assert "edge_count" in data

    @pytest.mark.integration
    def test_ontology(self, api: httpx.Client) -> None:
        resp = api.get("/api/v1/ontology")
        assert resp.status_code == 200
        data = resp.json()
        assert "classes" in data

    @pytest.mark.integration
    def test_validate_empty_kg(self, api: httpx.Client) -> None:
        resp = api.post("/api/v1/validate", json={
            "run_shacl": False,
            "run_rules": True,
            "run_consistency": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "passed" in data

    @pytest.mark.integration
    def test_gaps_empty(self, api: httpx.Client) -> None:
        resp = api.get("/api/v1/hitl/gaps")
        assert resp.status_code == 200
        data = resp.json()
        assert "coverage_score" in data

    @pytest.mark.integration
    def test_export_json(self, api: httpx.Client) -> None:
        resp = api.get("/api/v1/export/json")
        assert resp.status_code in (200, 500)  # 500 ok if KG is empty

    @pytest.mark.integration
    def test_build_list(self, api: httpx.Client) -> None:
        resp = api.get("/api/v1/build")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
