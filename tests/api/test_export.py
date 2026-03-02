"""Tests for KG export endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

_DEP = "kgbuilder.api.dependencies"
_STORE_EXPORT = "kgbuilder.storage.export"


class TestExportToFile:
    def test_export_json(self, client: TestClient, mock_neo4j) -> None:
        """POST /export with JSON format returns path and counts."""
        with patch(f"{_STORE_EXPORT}.KGExporter") as cls, patch(f"{_STORE_EXPORT}.ExportConfig"):
            exporter = MagicMock()
            cls.return_value = exporter

            resp = client.post("/api/v1/export", json={
                "format": "json",
                "include_metadata": True,
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == "json"
        assert "output_path" in data
        assert data["node_count"] == 42  # from mock_neo4j._MockStats
        assert data["edge_count"] == 100

    def test_export_custom_path(self, client: TestClient, mock_neo4j) -> None:
        """Custom output_path is forwarded to exporter."""
        with patch(f"{_STORE_EXPORT}.KGExporter") as cls, patch(f"{_STORE_EXPORT}.ExportConfig"):
            exporter = MagicMock()
            cls.return_value = exporter

            resp = client.post("/api/v1/export", json={
                "format": "turtle",
                "output_path": "/tmp/my_kg.ttl",
            })

        assert resp.status_code == 200
        assert resp.json()["output_path"] == "/tmp/my_kg.ttl"

    def test_export_invalid_format(self, client: TestClient) -> None:
        """Invalid format returns 422 validation error."""
        resp = client.post("/api/v1/export", json={"format": "invalid_fmt"})
        assert resp.status_code == 422

    def test_export_failure(self, client: TestClient) -> None:
        """Exporter exception returns 500."""
        with patch(f"{_DEP}.get_neo4j_store", side_effect=RuntimeError("Neo4j down")):
            resp = client.post("/api/v1/export", json={"format": "json"})
        assert resp.status_code == 500


class TestExportDownload:
    def test_download_json(self, client: TestClient, mock_neo4j) -> None:
        """GET /export/json returns attachment with correct content type."""
        with patch(f"{_STORE_EXPORT}.KGExporter") as cls, patch(f"{_STORE_EXPORT}.ExportConfig"):
            exporter = MagicMock()
            exporter.to_json.return_value = '{"nodes": []}'
            cls.return_value = exporter

            resp = client.get("/api/v1/export/json")

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/json"
        assert "attachment" in resp.headers.get("content-disposition", "")

    def test_download_turtle(self, client: TestClient, mock_neo4j) -> None:
        """GET /export/turtle returns text/turtle."""
        with patch(f"{_STORE_EXPORT}.KGExporter") as cls, patch(f"{_STORE_EXPORT}.ExportConfig"):
            exporter = MagicMock()
            exporter.to_turtle.return_value = "@prefix ex: <http://example.org/> ."
            cls.return_value = exporter

            resp = client.get("/api/v1/export/turtle")

        assert resp.status_code == 200
        assert "text/turtle" in resp.headers["content-type"]

    def test_download_jsonld(self, client: TestClient, mock_neo4j) -> None:
        """GET /export/jsonld returns ld+json."""
        with patch(f"{_STORE_EXPORT}.KGExporter") as cls, patch(f"{_STORE_EXPORT}.ExportConfig"):
            exporter = MagicMock()
            exporter.to_jsonld.return_value = '{"@context": {}}'
            cls.return_value = exporter

            resp = client.get("/api/v1/export/jsonld")

        assert resp.status_code == 200
        assert "application/ld+json" in resp.headers["content-type"]

    def test_download_invalid_format(self, client: TestClient) -> None:
        """Invalid format in path returns 422."""
        resp = client.get("/api/v1/export/rdf_xml")
        assert resp.status_code == 422

    def test_download_failure(self, client: TestClient) -> None:
        """Exporter error returns 500."""
        with patch(f"{_DEP}.get_neo4j_store", side_effect=RuntimeError("fail")):
            resp = client.get("/api/v1/export/json")
        assert resp.status_code == 500
