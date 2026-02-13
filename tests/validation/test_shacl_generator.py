"""Tests for SHACL shape generation from OWL ontology."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kgbuilder.validation.shacl_generator import SHACLShapeGenerator


@pytest.fixture
def mock_ontology_service() -> MagicMock:
    """Create mock ontology service with typical responses."""
    svc = MagicMock()
    svc.get_all_classes.return_value = [
        "Activity", "Facility", "Organization", "Document",
    ]
    svc.get_class_properties.return_value = [
        ("hasOperator", "ObjectProperty", "Organization"),
        ("hasName", "DatatypeProperty", "xsd:string"),
    ]
    svc.get_special_properties.return_value = {
        "transitive": ["partOf"],
        "symmetric": ["relatedTo"],
        "functional": ["hasOperator"],
        "inverse": [("requires", "requiredBy")],
    }
    svc.get_class_hierarchy.return_value = [
        ("NuclearFacility", "Facility"),
    ]
    return svc


class TestSHACLShapeGenerator:
    """Test suite for SHACLShapeGenerator."""

    def test_init_stores_ontology_service(
        self, mock_ontology_service: MagicMock
    ) -> None:
        gen = SHACLShapeGenerator(mock_ontology_service)
        assert gen._ontology is mock_ontology_service

    def test_init_accepts_custom_namespace(
        self, mock_ontology_service: MagicMock
    ) -> None:
        gen = SHACLShapeGenerator(
            mock_ontology_service,
            namespace="http://example.org/shapes/",
        )
        assert gen._namespace == "http://example.org/shapes/"

    @pytest.mark.skip(reason="generate() not yet implemented")
    def test_generate_returns_rdflib_graph(
        self, mock_ontology_service: MagicMock
    ) -> None:
        gen = SHACLShapeGenerator(mock_ontology_service)
        graph = gen.generate()
        # Should return an rdflib.Graph
        assert graph is not None

    @pytest.mark.skip(reason="generate() not yet implemented")
    def test_generate_creates_node_shapes_for_classes(
        self, mock_ontology_service: MagicMock
    ) -> None:
        gen = SHACLShapeGenerator(mock_ontology_service)
        graph = gen.generate()
        # Should have one NodeShape per ontology class
        # Query graph for sh:NodeShape triples
        assert len(list(graph.subjects())) > 0

    @pytest.mark.skip(reason="generate() not yet implemented")
    def test_generate_adds_functional_property_maxcount(
        self, mock_ontology_service: MagicMock
    ) -> None:
        gen = SHACLShapeGenerator(mock_ontology_service)
        graph = gen.generate()
        # Functional properties should get sh:maxCount 1
        # (verify via SPARQL or triple check)
        pass

    @pytest.mark.skip(reason="serialize() not yet implemented")
    def test_serialize_turtle_format(
        self, mock_ontology_service: MagicMock
    ) -> None:
        gen = SHACLShapeGenerator(mock_ontology_service)
        graph = gen.generate()
        ttl = gen.serialize(graph, format="turtle")
        assert "sh:NodeShape" in ttl

    @pytest.mark.skip(reason="save() not yet implemented")
    def test_save_writes_file(
        self, mock_ontology_service: MagicMock, tmp_path: object
    ) -> None:
        gen = SHACLShapeGenerator(mock_ontology_service)
        graph = gen.generate()
        out = gen.save(graph, tmp_path / "shapes.ttl")  # type: ignore[operator]
        assert out.exists()
