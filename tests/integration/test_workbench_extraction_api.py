"""Live contract test for KG Workbench's external extraction adapter."""

from __future__ import annotations

import base64
import os
import time
from uuid import uuid4

import pytest
import requests

pytestmark = pytest.mark.integration


def test_workbench_external_extraction_contract() -> None:
    """Submit, poll, and fetch results through a running KGBuilder API."""
    base_url = os.getenv("KGBUILDER_EXTRACTION_BASE_URL")
    api_key = os.getenv("KGBUILDER_API_KEY")
    if not base_url or not api_key:
        pytest.skip("Set KGBUILDER_EXTRACTION_BASE_URL and KGBUILDER_API_KEY for live testing")

    run_id = f"run_{uuid4().hex}"
    document_text = "Ada Lovelace works for Acme GmbH."
    request_body = {
        "runId": run_id,
        "documentId": f"document_{uuid4().hex}",
        "ontologyId": f"ontology_{uuid4().hex}",
        "file": {
            "name": "workbench-integration.txt",
            "contentType": "text/plain",
            "base64": base64.b64encode(document_text.encode()).decode(),
        },
        "ontology": {
            "name": "Workbench integration ontology",
            "defaultLanguage": "en",
            "languages": [{"code": "en", "label": "English"}],
            "usecase": "Extract people, organizations, and employment relations.",
            "version": "1.0.0",
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
            "relationAttributes": [],
            "competencyQuestions": [
                {
                    "id": "cq-1",
                    "question": "Which organization does a person work for?",
                    "subjectClassId": "person",
                    "predicateRelationId": "works-for",
                    "objectClassId": "organization",
                    "modules": [{"id": "core", "name": "Core"}],
                }
            ],
            "notes": [],
            "examples": [
                {
                    "id": "example-person",
                    "targetType": "class",
                    "targetId": "person",
                    "value": "Ada Lovelace",
                },
                {
                    "id": "example-organization",
                    "targetType": "class",
                    "targetId": "organization",
                    "value": "Acme GmbH",
                },
                {
                    "id": "example-works-for",
                    "targetType": "relation",
                    "targetId": "works-for",
                    "value": "Ada Lovelace works for Acme GmbH.",
                    "subjectLabel": "Ada Lovelace",
                    "predicateLabel": "works for",
                    "objectLabel": "Acme GmbH",
                },
            ],
            "localizedTexts": [],
            "visual": {"moduleLayouts": [], "classPositions": []},
        },
    }
    headers = {"Authorization": f"Bearer {api_key}"}

    started = requests.post(
        f"{base_url.rstrip('/')}/api/extract",
        json=request_body,
        headers=headers,
        timeout=30,
    )
    assert started.status_code == 200, started.text
    assert started.json() == {"runId": run_id}

    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        status_response = requests.get(
            f"{base_url.rstrip('/')}/api/extract/{run_id}/status",
            headers=headers,
            timeout=10,
        )
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status["runId"] == run_id
        assert status["status"] in {"running", "completed", "failed"}
        assert 0 <= status["progress"] <= 100
        if status["status"] == "failed":
            pytest.fail(f"KGBuilder extraction failed at progress {status['progress']}")
        if status["status"] == "completed":
            break
        time.sleep(3)
    else:
        pytest.fail("KGBuilder extraction did not complete within 240 seconds")

    result_response = requests.get(
        f"{base_url.rstrip('/')}/api/extract/{run_id}/results",
        headers=headers,
        timeout=30,
    )
    assert result_response.status_code == 200, result_response.text
    result = result_response.json()
    assert set(result) == {"sections", "entities", "facts"}
    assert result["sections"]
    assert result["sections"][0]["paragraphs"][0]["content"] == document_text
    assert result["entities"], "The integration fixture should yield at least one entity"

    entity_ids: set[str] = set()
    for entity in result["entities"]:
        assert set(entity) == {"temp_id", "text", "className", "attributes"}
        assert entity["temp_id"] and entity["text"] and entity["className"]
        entity_ids.add(entity["temp_id"])
        for attribute in entity["attributes"]:
            assert set(attribute) == {"attribute_name", "value"}
            assert isinstance(attribute["value"], str)

    for fact in result["facts"]:
        assert set(fact) == {
            "subject_temp_id",
            "relation_text",
            "object_temp_id",
            "subjectClassName",
            "objectClassName",
            "relationName",
            "confidence",
            "isCrossChapter",
            "evidence",
        }
        assert fact["subject_temp_id"] in entity_ids
        assert fact["object_temp_id"] in entity_ids
        evidence = fact["evidence"]
        assert set(evidence) == {
            "quote",
            "sectionTitle",
            "paragraphId",
            "pageFrom",
            "pageTo",
        }
        assert isinstance(evidence["sectionTitle"], str)
        assert evidence["paragraphId"] is None or isinstance(evidence["paragraphId"], str)
        assert evidence["pageFrom"] is None or isinstance(evidence["pageFrom"], int)
        assert evidence["pageTo"] is None or isinstance(evidence["pageTo"], int)
