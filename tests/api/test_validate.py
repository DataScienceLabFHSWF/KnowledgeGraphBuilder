"""Tests for KG validation endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from kgbuilder.validation.consistency_checker import ConsistencyReport
from kgbuilder.validation.models import (
    Conflict,
    RuleViolation,
    ValidationResult,
    ValidationViolation,
    ViolationSeverity,
)

_DEP = "kgbuilder.api.dependencies"
_RULES = "kgbuilder.validation.rules_engine"
_CONSIST = "kgbuilder.validation.consistency_checker"
_SHACL = "kgbuilder.validation.shacl_validator"


class TestValidateKG:
    def test_validate_no_checks_enabled(self, client: TestClient, mock_neo4j) -> None:
        """All check flags off → passed=True, zero violations."""
        resp = client.post("/api/v1/validate", json={
            "run_shacl": False,
            "run_rules": False,
            "run_consistency": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["passed"] is True
        assert data["violations_count"] == 0
        assert data["total_checks"] == 0

    def test_validate_rules_no_violations(self, client: TestClient, mock_neo4j) -> None:
        """Rules engine returns clean result → passed=True."""
        with patch(f"{_RULES}.RulesEngine") as cls:
            engine = MagicMock()
            engine.execute_rules.return_value = ValidationResult(
                valid=True, rule_violations=[]
            )
            cls.return_value = engine

            resp = client.post("/api/v1/validate", json={
                "run_shacl": False,
                "run_rules": True,
                "run_consistency": False,
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["passed"] is True
        assert data["violations_count"] == 0

    def test_validate_rules_with_violations(self, client: TestClient, mock_neo4j) -> None:
        """Rule violations appear in response."""
        rv = RuleViolation(
            rule_name="inverse_check",
            rule_description="Every hasPart must have isPartOf",
            subject_id="entity_1",
            predicate="hasPart",
            object_id="entity_2",
            reason="Missing inverse relation",
        )
        with patch(f"{_RULES}.RulesEngine") as cls:
            engine = MagicMock()
            engine.execute_rules.return_value = ValidationResult(
                valid=False, rule_violations=[rv]
            )
            cls.return_value = engine

            resp = client.post("/api/v1/validate", json={
                "run_shacl": False,
                "run_rules": True,
                "run_consistency": False,
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["passed"] is False
        assert data["violations_count"] == 1
        v = data["violations"][0]
        assert v["type"] == "rule"
        assert v["path"] == "hasPart"
        assert v["focus_node"] == "entity_1"

    def test_validate_consistency_with_conflicts(
        self, client: TestClient, mock_neo4j
    ) -> None:
        """Consistency conflicts are surfaced."""
        report = ConsistencyReport(
            conflicts=[
                Conflict(entity_id="e1", description="Type mismatch"),
            ],
            conflict_count=1,
        )
        with patch(f"{_CONSIST}.ConsistencyChecker") as cls:
            checker = MagicMock()
            checker.check_consistency.return_value = report
            cls.return_value = checker

            resp = client.post("/api/v1/validate", json={
                "run_shacl": False,
                "run_rules": False,
                "run_consistency": True,
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["passed"] is False
        assert data["conflicts_count"] == 1

    def test_validate_shacl_with_shapes(self, client: TestClient, mock_neo4j) -> None:
        """SHACL validation runs when shapes_path provided."""
        shacl_result = ValidationResult(
            violations=[
                ValidationViolation(
                    severity=ViolationSeverity.ERROR,
                    path="name",
                    message="Missing required property",
                    focus_node="node_1",
                )
            ],
            node_count=10,
            edge_count=5,
        )
        with (
            patch("rdflib.Graph") as mock_graph_cls,
            patch(f"{_SHACL}.SHACLValidator") as cls,
        ):
            mock_graph_cls.return_value = MagicMock()
            validator = MagicMock()
            validator.validate.return_value = shacl_result
            cls.return_value = validator

            resp = client.post("/api/v1/validate", json={
                "run_shacl": True,
                "run_rules": False,
                "run_consistency": False,
                "shapes_path": "/tmp/shapes.ttl",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["violations_count"] == 1
        assert data["violations"][0]["type"] == "shacl"

    def test_validate_shacl_no_shapes_path(self, client: TestClient, mock_neo4j) -> None:
        """SHACL is skipped gracefully when no shapes_path."""
        resp = client.post("/api/v1/validate", json={
            "run_shacl": True,
            "run_rules": False,
            "run_consistency": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["passed"] is True

    def test_validate_neo4j_failure(self, client: TestClient) -> None:
        """Neo4j connection error returns 500."""
        with patch(f"{_DEP}.get_neo4j_store", side_effect=ConnectionError("refused")):
            resp = client.post("/api/v1/validate", json={})
        assert resp.status_code == 500

    def test_validate_default_request(self, client: TestClient, mock_neo4j) -> None:
        """Default request body enables all checks."""
        resp = client.post("/api/v1/validate", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "passed" in data
        assert "violations" in data
        assert "violations_count" in data
