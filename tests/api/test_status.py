"""Tests for status / health / ontology endpoints."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

_DEP = "kgbuilder.api.dependencies"
_ROUTES = "kgbuilder.api.routes.status"


class TestRoot:
    def test_root_returns_message(self, client: TestClient) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "KGBuilder API" in resp.json()["message"]


class TestHealth:
    def test_health_all_ok(self, client: TestClient, mock_neo4j) -> None:
        """When all backends respond, status is 'ok'."""
        mock_resp = httpx.Response(200)
        with (
            patch("httpx.get", return_value=mock_resp),
        ):
            resp = client.get("/api/v1/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "kgbuilder"
        assert data["neo4j"] == "ok"

    def test_health_neo4j_down(self, client: TestClient) -> None:
        """When Neo4j is unreachable, status is 'degraded'."""
        with (
            patch(f"{_DEP}.get_neo4j_store", side_effect=ConnectionError("refused")),
            patch("httpx.get", side_effect=httpx.ConnectError("refused")),
        ):
            resp = client.get("/api/v1/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert "error" in data["neo4j"]


class TestStats:
    def test_stats_returns_counts(self, client: TestClient, mock_neo4j) -> None:
        resp = client.get("/api/v1/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["node_count"] == 42
        assert data["edge_count"] == 100
        assert "Entity" in data["nodes_by_type"]

    def test_stats_fallback_on_error(self, client: TestClient) -> None:
        """When Neo4j is down, returns zeroed stats (no 500)."""
        with patch(f"{_DEP}.get_neo4j_store", side_effect=ConnectionError):
            resp = client.get("/api/v1/stats")
        assert resp.status_code == 200
        assert resp.json()["node_count"] == 0


class TestOntologyInfo:
    def test_ontology_returns_classes(self, client: TestClient, mock_ontology) -> None:
        resp = client.get("/api/v1/ontology")
        assert resp.status_code == 200
        data = resp.json()
        assert data["class_count"] == 3
        assert "Person" in data["classes"]
        assert data["relation_count"] == 2
        assert len(data["hierarchy"]) == 2

    def test_ontology_fallback_on_error(self, client: TestClient) -> None:
        with patch(f"{_DEP}.get_ontology_service", side_effect=ConnectionError):
            resp = client.get("/api/v1/ontology")
        assert resp.status_code == 200
        assert resp.json()["class_count"] == 0
