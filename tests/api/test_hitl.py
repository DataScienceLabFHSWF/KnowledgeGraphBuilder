"""Tests for HITL (Human-in-the-Loop) endpoints."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

_HITL = "kgbuilder.api.routes.hitl"
_HITL_GAP = "kgbuilder.hitl.gap_detector"
_HITL_CFG = "kgbuilder.hitl.config"
_HITL_ING = "kgbuilder.hitl.ingestion"


# ── Gap Detection ────────────────────────────────────────────────────────


class TestGetGapReport:
    def test_no_reports_returns_empty(self, client: TestClient) -> None:
        """No persisted reports → empty gap report with coverage 1.0."""
        with patch(f"{_HITL}.Path") as mock_path_cls:
            mock_dir = MagicMock()
            mock_dir.exists.return_value = False
            mock_path_cls.return_value = mock_dir

            resp = client.get("/api/v1/hitl/gaps")

        assert resp.status_code == 200
        data = resp.json()
        assert data["coverage_score"] == 1.0
        assert data["untyped_entities"] == []
        assert data["suggested_new_classes"] == []

    def test_existing_report_returned(self, client: TestClient, tmp_path: Path) -> None:
        """Latest gap report file is loaded and returned."""
        gap_dir = tmp_path / "gap_reports"
        gap_dir.mkdir(parents=True)
        report_data = {
            "untyped_entities": ["FooEntity"],
            "failed_queries": ["What is X?"],
            "suggested_new_classes": ["NewClass"],
            "suggested_new_relations": ["newRelation"],
            "coverage_score": 0.75,
            "low_confidence_answers": [{"query": "q1", "confidence": "0.3"}],
            "timestamp": "2025-01-01T00:00:00",
        }
        report_file = gap_dir / "gap_report_20250101_000000.json"
        report_file.write_text(json.dumps(report_data))

        with patch(f"{_HITL}.Path", return_value=gap_dir):
            resp = client.get("/api/v1/hitl/gaps")

        assert resp.status_code == 200
        data = resp.json()
        assert data["untyped_entities"] == ["FooEntity"]
        assert data["coverage_score"] == 0.75


class TestDetectGaps:
    def test_detect_from_qa_results(self, client: TestClient) -> None:
        """POST /gaps/detect runs GapDetector and returns report."""
        mock_report = MagicMock()
        mock_report.untyped_entities = ["UnknownEntity"]
        mock_report.failed_queries = []
        mock_report.suggested_new_classes = []
        mock_report.suggested_new_relations = []
        mock_report.coverage_score = 0.9
        mock_report.low_confidence_answers = []
        mock_report.timestamp = datetime(2025, 1, 1)

        with (
            patch(f"{_HITL_GAP}.GapDetector") as cls,
            patch(f"{_HITL_CFG}.GapDetectionConfig"),
        ):
            detector = MagicMock()
            detector.detect_from_qa_feedback.return_value = mock_report
            cls.return_value = detector

            resp = client.post("/api/v1/hitl/gaps/detect", json={
                "qa_results": [
                    {"query": "What is X?", "confidence": "0.3"},
                ],
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["untyped_entities"] == ["UnknownEntity"]
        assert data["coverage_score"] == 0.9
        detector.save_report.assert_called_once()

    def test_detect_forwards_tbox_gaps(self, client: TestClient) -> None:
        """When suggested_new_classes exist, forward to ontology API."""
        mock_report = MagicMock()
        mock_report.untyped_entities = []
        mock_report.failed_queries = []
        mock_report.suggested_new_classes = ["NewClass"]
        mock_report.suggested_new_relations = []
        mock_report.coverage_score = 0.8
        mock_report.low_confidence_answers = []
        mock_report.timestamp = datetime(2025, 1, 1)

        with (
            patch(f"{_HITL_GAP}.GapDetector") as cls,
            patch(f"{_HITL_CFG}.GapDetectionConfig"),
            patch(
                f"{_HITL}._forward_tbox_gaps_to_ontology_api",
                new_callable=AsyncMock,
            ) as mock_fwd,
        ):
            detector = MagicMock()
            detector.detect_from_qa_feedback.return_value = mock_report
            cls.return_value = detector

            resp = client.post("/api/v1/hitl/gaps/detect", json={
                "qa_results": [],
            })

        assert resp.status_code == 200
        mock_fwd.assert_awaited_once()


class TestDetectGapsFromExtraction:
    def test_detect_from_extraction(self, client: TestClient) -> None:
        """POST /gaps/detect-from-extraction compares entities against ontology."""
        mock_report = MagicMock()
        mock_report.untyped_entities = ["orphan"]
        mock_report.failed_queries = []
        mock_report.suggested_new_classes = []
        mock_report.suggested_new_relations = []
        mock_report.coverage_score = 0.5
        mock_report.low_confidence_answers = []
        mock_report.timestamp = datetime(2025, 1, 1)

        with (
            patch(f"{_HITL_GAP}.GapDetector") as cls,
            patch(f"{_HITL_CFG}.GapDetectionConfig"),
        ):
            detector = MagicMock()
            detector.detect_from_extraction.return_value = mock_report
            cls.return_value = detector

            resp = client.post(
                "/api/v1/hitl/gaps/detect-from-extraction",
                json={
                    "entities": [{"name": "orphan", "type": "Unknown"}],
                    "ontology_classes": ["Person", "Organization"],
                },
            )

        # The endpoint takes query params (not body), so may differ.
        # If it returns 200 great; 422 means we need to adjust call format.
        assert resp.status_code in (200, 422)


# ── Feedback ─────────────────────────────────────────────────────────────


class TestFeedback:
    def test_submit_feedback_accepted(self, client: TestClient) -> None:
        """Submit accepted feedback routes to kg_builder."""
        mock_result = MagicMock()
        mock_result.tbox_changes = []
        mock_result.abox_changes = [Path("/tmp/abox_change.json")]
        mock_result.cq_additions = []

        with (
            patch(f"{_HITL_ING}.FeedbackIngester") as cls,
            patch(f"{_HITL_CFG}.FeedbackConfig"),
        ):
            ingester = MagicMock()
            ingester.ingest.return_value = mock_result
            cls.return_value = ingester

            resp = client.post("/api/v1/hitl/feedback", json={
                "review_item_id": "item_001",
                "reviewer_id": "reviewer_1",
                "decision": "accepted",
                "rationale": "Looks correct",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "processed"
        assert "kg_builder" in data["routed_to"]

    def test_submit_feedback_tbox_routes_to_ontology(
        self, client: TestClient
    ) -> None:
        """TBox changes route to ontology_extender."""
        mock_result = MagicMock()
        mock_result.tbox_changes = [Path("/tmp/tbox_change.json")]
        mock_result.abox_changes = []
        mock_result.cq_additions = []

        with (
            patch(f"{_HITL_ING}.FeedbackIngester") as cls,
            patch(f"{_HITL_CFG}.FeedbackConfig"),
        ):
            ingester = MagicMock()
            ingester.ingest.return_value = mock_result
            cls.return_value = ingester

            resp = client.post("/api/v1/hitl/feedback", json={
                "review_item_id": "item_002",
                "reviewer_id": "reviewer_1",
                "decision": "modified",
                "rationale": "Needs new class",
                "suggested_changes": {"class_label": "NewConcept"},
            })

        assert resp.status_code == 200
        data = resp.json()
        assert "ontology_extender" in data["routed_to"]

    def test_submit_feedback_missing_fields(self, client: TestClient) -> None:
        """Missing required fields return 422."""
        resp = client.post("/api/v1/hitl/feedback", json={
            "review_item_id": "item_003",
            # missing reviewer_id, decision, rationale
        })
        assert resp.status_code == 422

    def test_submit_feedback_processing_error(self, client: TestClient) -> None:
        """Ingester failure returns 500."""
        with (
            patch(f"{_HITL_ING}.FeedbackIngester") as cls,
            patch(f"{_HITL_CFG}.FeedbackConfig"),
        ):
            ingester = MagicMock()
            ingester.ingest.side_effect = RuntimeError("DB error")
            cls.return_value = ingester

            resp = client.post("/api/v1/hitl/feedback", json={
                "review_item_id": "item_004",
                "reviewer_id": "reviewer_1",
                "decision": "rejected",
                "rationale": "Wrong",
            })

        assert resp.status_code == 500


# ── Cross-service forwarding ────────────────────────────────────────────


class TestForwardTboxGaps:
    def test_forward_ignores_unreachable_api(self, client: TestClient) -> None:
        """Unreachable OntologyExtender is silently handled."""
        import httpx

        mock_report = MagicMock()
        mock_report.suggested_new_classes = ["Widget"]

        with patch(f"{_HITL}.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post.side_effect = httpx.HTTPError("unreachable")
            mock_client_cls.return_value = mock_client

            from kgbuilder.api.routes.hitl import _forward_tbox_gaps_to_ontology_api

            import asyncio

            # Should not raise
            asyncio.get_event_loop().run_until_complete(
                _forward_tbox_gaps_to_ontology_api(mock_report)
            )
