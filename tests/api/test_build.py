"""Tests for the build pipeline endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from kgbuilder.agents.pipeline_agent import PipelineStep
from kgbuilder.api.routes import build as build_route
from kgbuilder.api.schemas import BuildRequest, BuildStatus

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


def test_build_worker_runs_markdown_pipeline_agent() -> None:
    class OntologyService:
        def get_all_classes(self) -> list[str]:
            return ["Person", "Organization"]

        def get_module_class_map(self) -> dict[str, list[str]]:
            return {"Core": ["Person", "Organization"]}

        def get_class_description(self, class_name: str) -> str:
            return f"{class_name} description"

        def get_all_relations(self) -> list[str]:
            return ["works-for"]

    class FakePipelineAgent:
        def __init__(self, bindings: dict[str, object]) -> None:
            self.bindings = bindings

        def run_plan(self, steps, **kwargs) -> list[object]:
            assert [step.id for step in steps] == ["questions"]
            assert kwargs["iterations"] == 4
            assert kwargs["stop_if_empty"] == "questions"
            return []

    build_route._jobs["agentic-test"] = {
        "status": BuildStatus.PENDING,
        "progress": 0.0,
        "current_phase": "initializing",
        "entities_count": 0,
        "relations_count": 0,
        "current_iteration": 0,
        "started_at": "now",
        "error": None,
    }
    request = BuildRequest(max_iterations=4, run_validation=False)
    with (
        patch("kgbuilder.api.dependencies.get_ontology_service", return_value=OntologyService()),
        patch("kgbuilder.api.dependencies.get_llm_provider", return_value=object()),
        patch("kgbuilder.api.dependencies.get_qdrant_store", return_value=object()),
        patch("kgbuilder.api.dependencies.get_neo4j_store", return_value=object()),
        patch("kgbuilder.retrieval.FusionRAGRetriever", return_value=object()),
        patch("kgbuilder.extraction.entity.LLMEntityExtractor", return_value=object()),
        patch("kgbuilder.extraction.relation.LLMRelationExtractor", return_value=object()),
        patch("kgbuilder.assembly.kg_builder.KGBuilder", return_value=object()),
        patch(
            "kgbuilder.agents.question_generator.QuestionGenerationAgent",
            return_value=object(),
        ),
        patch(
            "kgbuilder.agents.markdown_pipeline.load_pipeline",
            return_value=[PipelineStep(skill="ontology_gap_analysis", id="questions")],
        ),
        patch("kgbuilder.agents.pipeline_agent.PipelineAgent", FakePipelineAgent),
    ):
        build_route._run_build_pipeline("agentic-test", request)

    assert build_route._jobs["agentic-test"]["status"] == BuildStatus.COMPLETED
    assert build_route._jobs["agentic-test"]["current_phase"] == "completed"
