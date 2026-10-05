"""Tests for the asynchronous extraction API."""

from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from kgbuilder.api.routes import extract as extract_route
from kgbuilder.core.models import Evidence, ExtractedEntity, ExtractedRelation

_EXTRACT = "kgbuilder.api.routes.extract"
_RUN_ID = "run-test-001"


@pytest.fixture(autouse=True)
def clear_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(extract_route, "_runs", {})


def _request_body() -> dict:
    return {
        "runId": _RUN_ID,
        "documentId": "document-test",
        "ontologyId": "ontology-test",
        "file": {
            "name": "example.txt",
            "contentType": "text/plain",
            "base64": base64.b64encode(b"Ada works for Acme.").decode(),
        },
        "ontology": {
            "name": "Test ontology",
            "modules": [{"id": "core", "name": "Core"}],
            "classes": [
                {
                    "id": "person",
                    "name": "Person",
                    "moduleId": "core",
                    "module": "Core",
                    "attributes": [],
                },
                {
                    "id": "organization",
                    "name": "Organization",
                    "moduleId": "core",
                    "module": "Core",
                    "attributes": [
                        {
                            "id": "organization-name",
                            "name": "Name",
                            "dataType": "xsd:string",
                            "required": True,
                        }
                    ],
                },
            ],
            "relations": [
                {
                    "id": "works-for",
                    "name": "works for",
                    "domainClassId": "person",
                    "rangeClassId": "organization",
                }
            ],
            "examples": [
                {
                    "targetType": "relation",
                    "targetId": "works-for",
                    "value": "Ada works for Acme.",
                    "subjectLabel": "Ada",
                    "objectLabel": "Acme",
                }
            ],
            "competencyQuestions": [
                {
                    "id": "cq-1",
                    "question": "Which organization does a person work for?",
                    "subjectClassId": "person",
                    "modules": [{"id": "core", "name": "Core"}],
                }
            ],
        },
    }


class TestExtractionRoutes:
    def test_start_returns_the_supplied_run_id(self, client: TestClient) -> None:
        with patch(f"{_EXTRACT}.Thread") as mock_thread:
            mock_thread.return_value.start = MagicMock()
            response = client.post("/api/extract", json=_request_body())

        assert response.status_code == 200
        assert response.json() == {"runId": _RUN_ID}
        assert extract_route._runs[_RUN_ID]["status"].value == "running"

    def test_start_rejects_invalid_base64(self, client: TestClient) -> None:
        body = _request_body()
        body["file"]["base64"] = "not-base64!"

        response = client.post("/api/extract", json=body)

        assert response.status_code == 422
        assert _RUN_ID not in extract_route._runs

    def test_start_rejects_duplicate_run_ids(self, client: TestClient) -> None:
        extract_route._runs[_RUN_ID] = {
            "status": extract_route.ExtractionStatusValue.RUNNING,
            "progress": 0,
            "results": None,
            "error": None,
        }

        response = client.post("/api/extract", json=_request_body())

        assert response.status_code == 409

    def test_status_requires_configured_bearer_key(self, client: TestClient) -> None:
        extract_route._runs[_RUN_ID] = {
            "status": extract_route.ExtractionStatusValue.RUNNING,
            "progress": 42,
        }
        response = client.get(f"/api/extract/{_RUN_ID}/status")
        assert response.status_code == 503

    def test_status_returns_progress_with_valid_key(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("KGBUILDER_API_KEY", "integration-test-key")
        extract_route._runs[_RUN_ID] = {
            "status": extract_route.ExtractionStatusValue.RUNNING,
            "progress": 42,
        }

        response = client.get(
            f"/api/extract/{_RUN_ID}/status",
            headers={"Authorization": "Bearer integration-test-key"},
        )

        assert response.status_code == 200
        assert response.json() == {
            "runId": _RUN_ID,
            "status": "running",
            "progress": 42,
        }

    @pytest.mark.parametrize(
        "document_format",
        [
            ("example.txt", "text/plain"),
            ("example.pdf", "application/pdf"),
            (
                "example.docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
            (
                "example.pptx",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ),
            ("example.xml", "application/xml"),
        ],
    )
    def test_results_shape_after_agentic_extraction(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        document_format: tuple[str, str],
    ) -> None:
        from kgbuilder.api.schemas import ExtractionStatusValue

        monkeypatch.setenv("KGBUILDER_API_KEY", "integration-test-key")
        request = extract_route.ExtractionRequest.model_validate(_request_body())
        request.file.name, request.file.content_type = document_format
        binary_document = request.file.content_type != "text/plain"
        person = ExtractedEntity(
            id="entity-person",
            label="Ada",
            entity_type="Person",
            description="",
            confidence=0.95,
            evidence=[Evidence(source_type="local_doc", source_id="text")],
        )
        organization = ExtractedEntity(
            id="entity-org",
            label="Acme",
            entity_type="Organization",
            description="",
            properties={"legal_name": "Acme", "employee_count": 25},
            confidence=0.92,
            evidence=[Evidence(source_type="local_doc", source_id="text")],
        )
        fact = ExtractedRelation(
            id="fact-1",
            source_entity_id=person.id,
            target_entity_id=organization.id,
            predicate="works-for",
            confidence=0.91,
            evidence=[
                Evidence(
                    source_type="local_doc",
                    source_id="text",
                    text_span="Ada works for Acme.",
                )
            ],
        )

        class FakeOrchestrator:
            def __init__(self) -> None:
                pass

            def run_modules(self, module_bindings: list[object]) -> list[ExtractedEntity]:
                assert len(module_bindings) == 1
                return [person, organization]

        class FakeEntityExtractor:
            def __init__(self, llm_provider: object) -> None:
                pass

        class FakeRelationExtractor:
            def __init__(self, llm_provider: object) -> None:
                pass

            def extract(self, **kwargs: object) -> list[ExtractedRelation]:
                return [fact]

        extract_route._runs[_RUN_ID] = {
            "status": ExtractionStatusValue.RUNNING,
            "progress": 0,
            "results": None,
            "error": None,
        }
        with (
            patch("kgbuilder.api.dependencies.get_llm_provider", return_value=object()),
            patch(
                "kgbuilder.agents.orchestrator_agent.OrchestratorAgent",
                FakeOrchestrator,
            ),
            patch(
                "kgbuilder.extraction.entity.LLMEntityExtractor",
                FakeEntityExtractor,
            ),
            patch(
                "kgbuilder.extraction.relation.LLMRelationExtractor",
                FakeRelationExtractor,
            ),
            patch.object(extract_route, "_load_document_text", return_value="Ada works for Acme."),
        ):
            extract_route._run_extraction(
                _RUN_ID,
                request,
                base64.b64decode(request.file.base64),
            )

        response = client.get(
            f"/api/extract/{_RUN_ID}/results",
            headers={"Authorization": "Bearer integration-test-key"},
        )

        assert response.status_code == 200
        result = response.json()
        assert result["sections"][0]["paragraphs"][0]["id"] == "paragraph-1"
        assert result["entities"] == [
            {
                "temp_id": "entity-1",
                "text": "Ada",
                "className": "Person",
                "attributes": [],
            },
            {
                "temp_id": "entity-2",
                "text": "Acme",
                "className": "Organization",
                "attributes": [
                    {"attribute_name": "legal_name", "value": "Acme"},
                    {"attribute_name": "employee_count", "value": "25"},
                ],
            },
        ]
        assert result["facts"][0] == {
            "subject_temp_id": "entity-1",
            "relation_text": "works for",
            "object_temp_id": "entity-2",
            "subjectClassName": "Person",
            "objectClassName": "Organization",
            "relationName": "works-for",
            "confidence": 0.91,
            "isCrossChapter": False,
            "evidence": {
                "quote": "Ada works for Acme.",
                "sectionTitle": request.file.name,
                "paragraphId": "paragraph-1",
                **({} if binary_document else {"pageFrom": 1, "pageTo": 1}),
            },
        }
