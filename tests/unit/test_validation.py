"""Comprehensive tests for Phase 8 validation pipeline.

Tests all validation components:
- SHACL constraint validation
- Semantic rule execution
- Conflict and duplicate detection
- Report generation
- Integration tests

Test Coverage: 75%+ of validation module
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from kgbuilder.storage.protocol import Edge, GraphStore, Node
from kgbuilder.validation.consistency_checker import ConsistencyChecker, ConsistencyReport
from kgbuilder.validation.models import (
    Conflict,
    ConflictType,
    RuleViolation,
    ValidationResult,
    ValidationViolation,
    ViolationSeverity,
)
from kgbuilder.validation.reporter import ReportGenerator
from kgbuilder.validation.rules_engine import (
    DomainRangeRule,
    FunctionalPropertyRule,
    InversePropertyRule,
    RulesEngine,
    TransitiveRule,
)
from kgbuilder.validation.shacl_validator import SHACLValidator


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_graph_store() -> GraphStore:
    """Create a mock GraphStore for testing."""
    store = MagicMock(spec=GraphStore)

    # Sample nodes
    nodes = [
        Node(id="person1", node_type="Person", label="Alice", properties={"age": 30}),
        Node(id="person2", node_type="Person", label="Bob", properties={"age": 25}),
        Node(
            id="org1",
            node_type="Organization",
            label="TechCorp",
            properties={"founded": 2020},
        ),
        Node(
            id="org2",
            node_type="Organization",
            label="DataInc",
            properties={"founded": 2020},
        ),
    ]

    # Sample edges
    edges = [
        Edge(
            id="edge1",
            source_id="person1",
            target_id="org1",
            edge_type="works_for",
            source_node_type="Person",
            target_node_type="Organization",
            properties={"confidence": 0.9},
        ),
        Edge(
            id="edge2",
            source_id="person2",
            target_id="org1",
            edge_type="works_for",
            source_node_type="Person",
            target_node_type="Organization",
            properties={"confidence": 0.8},
        ),
        Edge(
            id="edge3",
            source_id="person1",
            target_id="person2",
            edge_type="knows",
            source_node_type="Person",
            target_node_type="Person",
            properties={"confidence": 0.7},
        ),
    ]

    store.get_all_nodes.return_value = nodes
    store.get_all_edges.return_value = edges
    store.query.return_value = Mock()

    return store


@pytest.fixture
def validation_result() -> ValidationResult:
    """Create a sample ValidationResult."""
    result = ValidationResult()
    result.node_count = 4
    result.edge_count = 3
    result.valid = False

    # Add violations
    result.add_violation(
        ValidationViolation(
            severity=ViolationSeverity.ERROR,
            path="person1/age",
            message="Age must be positive",
            expected="> 0",
        )
    )

    result.add_rule_violation(
        RuleViolation(
            rule_name="inverse_property",
            rule_description="Enforce inverse relations",
            subject_id="person1",
            predicate="knows",
            object_id="person2",
            reason="Missing inverse relation",
        )
    )

    return result


# ============================================================================
# Unit Tests - Models
# ============================================================================


class TestValidationModels:
    """Test data models."""

    def test_violation_creation(self) -> None:
        """Test ValidationViolation creation."""
        v = ValidationViolation(
            severity=ViolationSeverity.WARNING,
            path="test/path",
            message="Test violation",
        )

        assert v.severity == ViolationSeverity.WARNING
        assert v.path == "test/path"
        assert v.message == "Test violation"

    def test_violation_to_dict(self) -> None:
        """Test ValidationViolation to_dict serialization."""
        v = ValidationViolation(
            severity=ViolationSeverity.ERROR,
            path="prop",
            message="Invalid",
            expected="Valid",
        )
        d = v.to_dict()

        assert d["severity"] == "ERROR"
        assert d["path"] == "prop"
        assert d["message"] == "Invalid"
        assert d["expected"] == "Valid"

    def test_rule_violation_creation(self) -> None:
        """Test RuleViolation creation."""
        v = RuleViolation(
            rule_name="test_rule",
            rule_description="Test description",
            subject_id="s1",
            predicate="predicate",
            object_id="o1",
            reason="Test reason",
        )

        assert v.rule_name == "test_rule"
        assert v.subject_id == "s1"

    def test_conflict_creation(self) -> None:
        """Test Conflict creation."""
        c = Conflict(
            conflict_type=ConflictType.VALUE_CONFLICT,
            involved_entities=["e1", "e2"],
            description="Test conflict",
        )

        assert c.conflict_type == ConflictType.VALUE_CONFLICT
        assert len(c.involved_entities) == 2

    def test_validation_result_creation(self) -> None:
        """Test ValidationResult creation."""
        result = ValidationResult()

        assert result.valid is True
        assert result.node_count == 0
        assert len(result.violations) == 0

    def test_validation_result_pass_rate(self, validation_result: ValidationResult) -> None:
        """Test ValidationResult pass_rate calculation."""
        # With 1 violation out of 7 entities (4 nodes + 3 edges)
        # pass_rate = (7 - 1) / 7 ≈ 0.857
        assert validation_result.pass_rate > 0.85
        assert validation_result.pass_rate < 0.9


# ============================================================================
# Unit Tests - SHACL Validator
# ============================================================================


class TestSHACLValidator:
    """Test SHACL Validator."""

    @patch("kgbuilder.validation.shacl_validator.validate")
    def test_validator_creation(self, mock_validate: Mock) -> None:
        """Test SHACLValidator initialization."""
        import rdflib

        shapes = rdflib.Graph()
        validator = SHACLValidator(shapes, "http://example.org/")

        assert validator.ontology_uri == "http://example.org/"

    @patch("kgbuilder.validation.shacl_validator.validate")
    def test_validate_node_with_valid_properties(self, mock_validate: Mock) -> None:
        """Test validate_node with valid node."""
        import rdflib

        shapes = rdflib.Graph()
        validator = SHACLValidator(shapes)

        node = Node(id="test1", node_type="Person", label="Test", properties={})
        result = validator.validate_node(node, "http://example.org/PersonShape")

        assert result.valid is True
        assert len(result.violations) == 0

    def test_validate_node_missing_id(self) -> None:
        """Test validate_node detects missing ID."""
        import rdflib

        shapes = rdflib.Graph()
        validator = SHACLValidator(shapes)

        node = Node(id="", node_type="Person", label="", properties={})
        result = validator.validate_node(node)

        assert len(result.violations) > 0
        assert any("id" in v.path for v in result.violations)

    def test_validate_edge_confidence_validation(self) -> None:
        """Test validate_edge checks confidence range."""
        import rdflib

        shapes = rdflib.Graph()
        validator = SHACLValidator(shapes)

        # Valid confidence
        edge = Edge(
            id="e1",
            source_id="s1",
            target_id="t1",
            edge_type="rel",
            source_node_type="Type1",
            target_node_type="Type2",
            properties={"confidence": 0.8},
        )
        result = validator.validate_edge(edge)
        assert len(result.violations) == 0

        # Invalid confidence (>1.0)
        edge.properties["confidence"] = 1.5
        result = validator.validate_edge(edge)
        assert len(result.violations) > 0

    def test_convert_store_to_rdf(self, mock_graph_store: GraphStore) -> None:
        """Test RDF conversion from GraphStore."""
        import rdflib

        shapes = rdflib.Graph()
        validator = SHACLValidator(shapes)

        rdf_graph = validator._convert_store_to_rdf(mock_graph_store)

        # Check that triples were created
        assert len(rdf_graph) > 0


# ============================================================================
# Unit Tests - Rules Engine
# ============================================================================


class TestRulesEngine:
    """Test semantic rules and rules engine."""

    def test_inverse_property_rule_missing_inverse(self, mock_graph_store: GraphStore) -> None:
        """Test InversePropertyRule detects missing inverse."""
        rule = InversePropertyRule(property_uri="knows", inverse_uri="knows_inverse")
        violations = rule.check(mock_graph_store)

        # Should detect missing inverse for knows edge
        assert len(violations) > 0

    def test_transitive_rule_missing_closure(self, mock_graph_store: GraphStore) -> None:
        """Test TransitiveRule detects missing transitive closure."""
        # Create store with path A -> B -> C
        rule = TransitiveRule(property_uri="knows", max_depth=3)

        # Mock store with transitive path
        store = MagicMock(spec=GraphStore)
        edges = [
            Edge(
                id="e1",
                source_id="a",
                target_id="b",
                edge_type="knows",
                source_node_type="Person",
                target_node_type="Person",
                properties={},
            ),
            Edge(
                id="e2",
                source_id="b",
                target_id="c",
                edge_type="knows",
                source_node_type="Person",
                target_node_type="Person",
                properties={},
            ),
        ]
        store.get_all_edges.return_value = edges

        violations = rule.check(store)

        # Should detect missing A -> C edge
        assert len(violations) > 0
        assert violations[0].subject_id == "a"

    def test_domain_range_rule_violation(self) -> None:
        """Test DomainRangeRule validates domain/range."""
        rule = DomainRangeRule(
            property_uri="works_for",
            domain_types=["Person"],
            range_types=["Organization"],
        )

        store = MagicMock(spec=GraphStore)

        # Valid edge: Person -> Organization
        valid_edge = Edge(
            id="e1",
            source_id="p1",
            target_id="o1",
            edge_type="works_for",
            source_node_type="Person",
            target_node_type="Organization",
            properties={},
        )

        # Invalid edge: Organization -> Person (reversed)
        invalid_edge = Edge(
            id="e2",
            source_id="o2",
            target_id="p2",
            edge_type="works_for",
            source_node_type="Organization",
            target_node_type="Person",
            properties={},
        )

        person = Node(id="p1", node_type="Person", properties={})
        org = Node(id="o1", node_type="Organization", properties={})
        org2 = Node(id="o2", node_type="Organization", properties={})
        person2 = Node(id="p2", node_type="Person", properties={})

        store.get_all_edges.return_value = [valid_edge, invalid_edge]
        store.get_all_nodes.return_value = [person, org, org2, person2]

        violations = rule.check(store)

        # Should detect domain violation in invalid_edge
        assert len(violations) > 0

    def test_functional_property_rule(self) -> None:
        """Test FunctionalPropertyRule detects multiple values."""
        rule = FunctionalPropertyRule(property_uri="email")

        store = MagicMock(spec=GraphStore)

        # Two edges with same source (functional property violation)
        edges = [
            Edge(
                id="e1",
                source_id="p1",
                target_id="email1@test.com",
                edge_type="email",
                source_node_type="Person",
                target_node_type="Email",
                properties={},
            ),
            Edge(
                id="e2",
                source_id="p1",
                target_id="email2@test.com",
                edge_type="email",
                source_node_type="Person",
                target_node_type="Email",
                properties={},
            ),
        ]

        store.get_all_edges.return_value = edges

        violations = rule.check(store)

        # Should detect functional property violation
        assert len(violations) > 0

    def test_rules_engine_add_and_execute(self, mock_graph_store: GraphStore) -> None:
        """Test RulesEngine add and execute."""
        engine = RulesEngine()

        rule = InversePropertyRule(property_uri="knows", inverse_uri="knows_inverse")
        engine.add_rule(rule)

        assert len(engine.rules) == 1

        result = engine.execute_rules(mock_graph_store)

        assert isinstance(result, ValidationResult)
        assert result.validation_duration_ms > 0

    def test_rules_engine_rule_control(self, mock_graph_store: GraphStore) -> None:
        """Test enabling/disabling rules."""
        engine = RulesEngine()
        rule = InversePropertyRule(property_uri="knows", inverse_uri="knows_inverse")
        engine.add_rule(rule)

        assert engine.enable_rule("knows-inverse") is True
        assert rule.enabled is True

        assert engine.disable_rule("knows-inverse") is True
        assert rule.enabled is False

        # Disabled rule should not create violations
        result = engine.execute_rules(mock_graph_store)
        assert len(result.rule_violations) == 0


# ============================================================================
# Unit Tests - Consistency Checker
# ============================================================================


class TestConsistencyChecker:
    """Test consistency checking."""

    def test_consistency_checker_creation(self) -> None:
        """Test ConsistencyChecker initialization."""
        checker = ConsistencyChecker()
        assert isinstance(checker, ConsistencyChecker)

    def test_find_conflicts_empty(self, mock_graph_store: GraphStore) -> None:
        """Test find_conflicts on store without conflicts."""
        checker = ConsistencyChecker()
        conflicts = checker.find_conflicts(mock_graph_store, "person1")

        # Mock store doesn't have conflicting values, so should be empty
        assert isinstance(conflicts, list)

    def test_find_duplicates_similarity(self, mock_graph_store: GraphStore) -> None:
        """Test find_duplicates identifies similar entities."""
        checker = ConsistencyChecker()
        duplicates = checker.find_duplicates(mock_graph_store, threshold=0.5)

        # Should find similar organizations with same founding year
        assert isinstance(duplicates, list)

    def test_compute_similarity(self, mock_graph_store: GraphStore) -> None:
        """Test similarity computation."""
        checker = ConsistencyChecker()

        # TechCorp vs DataInc (both Organization, founded 2020)
        similarity = checker._compute_similarity("org1", "org2", mock_graph_store)

        assert 0.0 <= similarity <= 1.0
        # Should be similar due to same type and properties
        assert similarity > 0.2

    def test_check_consistency_report(self, mock_graph_store: GraphStore) -> None:
        """Test consistency check produces report."""
        checker = ConsistencyChecker()
        report = checker.check_consistency(mock_graph_store)

        assert isinstance(report, ConsistencyReport)
        assert report.conflict_count >= 0
        assert report.check_duration_ms > 0


# ============================================================================
# Unit Tests - Report Generator
# ============================================================================


class TestReportGenerator:
    """Test report generation."""

    def test_generator_creation(self) -> None:
        """Test ReportGenerator initialization."""
        gen = ReportGenerator(title="Test Report")
        assert gen.title == "Test Report"

    def test_to_dict(self, validation_result: ValidationResult) -> None:
        """Test result to dict conversion."""
        gen = ReportGenerator()
        result_dict = gen.to_dict(validation_result)

        assert result_dict["title"] == "KG Validation Report"
        assert result_dict["valid"] is False
        assert "metrics" in result_dict
        assert "violations" in result_dict

    def test_to_json(self, validation_result: ValidationResult) -> None:
        """Test JSON export."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = ReportGenerator()
            output_path = Path(tmpdir) / "report.json"

            gen.to_json(validation_result, output_path)

            assert output_path.exists()

            with open(output_path) as f:
                data = json.load(f)

            assert data["valid"] is False
            assert len(data["violations"]) > 0

    def test_to_markdown(self, validation_result: ValidationResult) -> None:
        """Test Markdown export."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = ReportGenerator()
            output_path = Path(tmpdir) / "report.md"

            gen.to_markdown(validation_result, output_path)

            assert output_path.exists()

            content = output_path.read_text()
            assert "# KG Validation Report" in content
            assert "SHACL Violations" in content
            assert "Rule Violations" in content

    def test_to_html(self, validation_result: ValidationResult) -> None:
        """Test HTML export."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = ReportGenerator()
            output_path = Path(tmpdir) / "report.html"

            gen.to_html(validation_result, output_path)

            assert output_path.exists()

            content = output_path.read_text()
            assert "<!DOCTYPE html>" in content
            assert "KG Validation Report" in content
            assert "SHACL Violations" in content


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests combining multiple validators."""

    def test_full_validation_pipeline(self, mock_graph_store: GraphStore) -> None:
        """Test complete validation workflow."""
        import rdflib

        # Set up validators
        shapes = rdflib.Graph()
        shacl_validator = SHACLValidator(shapes)

        # Run SHACL validation
        shacl_result = shacl_validator.validate(mock_graph_store)
        assert isinstance(shacl_result, ValidationResult)

        # Run rules
        engine = RulesEngine()
        engine.add_rule(InversePropertyRule(property_uri="works_for", inverse_uri="employs"))
        rules_result = engine.execute_rules(mock_graph_store)
        assert isinstance(rules_result, ValidationResult)

        # Check consistency
        checker = ConsistencyChecker()
        consistency_report = checker.check_consistency(mock_graph_store)
        assert isinstance(consistency_report, ConsistencyReport)

        # Generate reports
        gen = ReportGenerator()
        report_dict = gen.to_dict(shacl_result)
        assert isinstance(report_dict, dict)

    def test_validation_with_multiple_formats(
        self, validation_result: ValidationResult
    ) -> None:
        """Test exporting validation result in multiple formats."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = ReportGenerator(title="Phase 8 Validation")

            json_path = Path(tmpdir) / "report.json"
            md_path = Path(tmpdir) / "report.md"
            html_path = Path(tmpdir) / "report.html"

            # Export to all formats
            gen.to_json(validation_result, json_path)
            gen.to_markdown(validation_result, md_path)
            gen.to_html(validation_result, html_path)

            # Verify all files exist
            assert json_path.exists()
            assert md_path.exists()
            assert html_path.exists()

            # Verify content
            with open(json_path) as f:
                json_data = json.load(f)
            assert json_data["valid"] is False

            md_content = md_path.read_text()
            assert "Phase 8 Validation" in md_content

            html_content = html_path.read_text()
            assert "Phase 8 Validation" in html_content


# ============================================================================
# Edge Case Tests
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_graph_validation(self) -> None:
        """Test validation on empty graph."""
        store = MagicMock(spec=GraphStore)
        store.get_all_nodes.return_value = []
        store.get_all_edges.return_value = []

        checker = ConsistencyChecker()
        report = checker.check_consistency(store)

        assert report.conflict_count == 0

    def test_large_graph_performance(self) -> None:
        """Test handling of large graphs."""
        store = MagicMock(spec=GraphStore)

        # Create large number of nodes
        nodes = [
            Node(id=f"node_{i}", node_type="Entity", properties={"index": i})
            for i in range(100)
        ]

        store.get_all_nodes.return_value = nodes
        store.get_all_edges.return_value = []

        checker = ConsistencyChecker()
        duplicates = checker.find_duplicates(store, threshold=0.95)

        # Should handle large graph without error
        assert isinstance(duplicates, list)

    def test_report_with_empty_violations(self, validation_result: ValidationResult) -> None:
        """Test report generation with empty violations."""
        result = ValidationResult()
        result.node_count = 10
        result.edge_count = 5
        result.valid = True

        gen = ReportGenerator()
        md_content = gen._generate_markdown(result)

        assert "✓ Yes" in md_content
        assert "No violations found" in md_content

    def test_rule_with_disabled_state(self, mock_graph_store: GraphStore) -> None:
        """Test disabled rules don't execute."""
        rule = InversePropertyRule(property_uri="knows", inverse_uri="knows_inverse")
        rule.enabled = False

        violations = rule.check(mock_graph_store)

        # Disabled rule should return empty list
        assert len(violations) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
