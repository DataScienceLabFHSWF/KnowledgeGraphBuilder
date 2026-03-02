"""Tests for the build pipeline endpoints."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


_BUILD = "kgbuilder.api.routes.build"


class TestStartBuild:
    def test_start_returns_job_id(self, client: TestClient) -> None:
        """POST /build starts a job and returns immediately."""
        # Patch the thread so we don't actually run the pipeline
        with patch(f"{_BUILD}.Thread") as mock_thread:
            mock_thread.return_value.start = MagicMock()
            resp = client.post("/api/v1/build", json={})

        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "pending"
        assert data["message"] == "Build pipeline started"

    def test_start_with_custom_params(self, client: TestClient) -> None:
        with patch(f"{_BUILD}.Thread") as mock_thread:
            mock_thread.return_value.start = MagicMock()
            resp = client.post(
                "/api/v1/build",
                json={
                    "questions_per_class": 5,
                    "max_iterations": 3,
                    "confidence_threshold": 0.8,
                    "run_validation": False,
                    "model": "llama3.1:70b",
                },
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"

    def test_start_rejects_invalid_params(self, client: TestClient) -> None:
        resp = client.post("/api/v1/build", json={"questions_per_class": 0})
        assert resp.status_code == 422

        resp = client.post("/api/v1/build", json={"confidence_threshold": 2.0})
        assert resp.status_code == 422


class TestGetBuildStatus:
    def test_get_status_existing_job(self, client: TestClient) -> None:
        """Start a job, then check its status."""
        with patch(f"{_BUILD}.Thread") as mock_thread:
            mock_thread.return_value.start = MagicMock()
            start_resp = client.post("/api/v1/build", json={})

        job_id = start_resp.json()["job_id"]
        resp = client.get(f"/api/v1/build/{job_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == job_id
        assert data["status"] in ("pending", "running", "completed", "failed")

    def test_get_status_unknown_job(self, client: TestClient) -> None:
        resp = client.get("/api/v1/build/nonexistent")
        assert resp.status_code == 404


class TestListBuildJobs:
    def test_list_returns_all_jobs(self, client: TestClient) -> None:
        with patch(f"{_BUILD}.Thread") as mock_thread:
            mock_thread.return_value.start = MagicMock()
            client.post("/api/v1/build", json={})
            client.post("/api/v1/build", json={})

        resp = client.get("/api/v1/build")
        assert resp.status_code == 200
        jobs = resp.json()
        assert isinstance(jobs, list)
        # At least the 2 we just created (may have more from other tests)
        assert len(jobs) >= 2
