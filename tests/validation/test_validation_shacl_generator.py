"""Tests for SHACL shape generation from OWL ontology."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import rdflib

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
        ("partOf", "ObjectProperty", "Facility"),
        ("relatedTo", "ObjectProperty", "Activity"),
        ("hasPrimaryContact", "ObjectProperty", "Organization", {"qualified_value_shape": "Person", "qualified_max_count": 1}),
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

    def test_generate_returns_rdflib_graph(
        self, mock_ontology_service: MagicMock
    ) -> None:
        gen = SHACLShapeGenerator(mock_ontology_service)
        graph = gen.generate()
        # Should return an rdflib.Graph
        import rdflib
        assert isinstance(graph, rdflib.Graph)

    def test_generate_creates_node_shapes_for_classes(
        self, mock_ontology_service: MagicMock
    ) -> None:
        gen = SHACLShapeGenerator(mock_ontology_service)
        graph = gen.generate()
        # Check at least one sh:NodeShape exists
        SH = rdflib.namespace.Namespace("http://www.w3.org/ns/shacl#")
        node_shapes = list(graph.subjects(rdflib.RDF.type, SH.NodeShape))
        assert len(node_shapes) >= len(mock_ontology_service.get_all_classes())

    # (see related test above)

    def test_generate_adds_functional_property_maxcount(
        self, mock_ontology_service: MagicMock
    ) -> None:
        gen = SHACLShapeGenerator(mock_ontology_service)
        graph = gen.generate()
        SH = rdflib.namespace.Namespace("http://www.w3.org/ns/shacl#")
        # health of functional property 'hasOperator' from fixture
        matches = []
        for s, p, o in graph.triples((None, SH.property, None)):
            for _, _, path in graph.triples((o, SH.path, None)):
                if str(path).endswith("hasOperator"):
                    for _, _, maxc in graph.triples((o, SH.maxCount, None)):
                        matches.append(int(str(maxc)))
        assert 1 in matches

    def test_generate_adds_sparql_constraints_for_special_props(
        self, mock_ontology_service: MagicMock
    ) -> None:
        gen = SHACLShapeGenerator(mock_ontology_service)
        graph = gen.generate()
        SH = rdflib.namespace.Namespace("http://www.w3.org/ns/shacl#")
        found_selects = []
        for s, p, o in graph.triples((None, SH.property, None)):
            for _, _, path in graph.triples((o, SH.path, None)):
                pname = str(path)
                # look for select literal on property-shape node
                for _, _, sel in graph.triples((o, SH.select, None)):
                    found_selects.append(str(sel))
        # The fixture declares 'partOf' as transitive and 'relatedTo' as symmetric
        assert any("partOf" in q for q in found_selects) or any("relatedTo" in q for q in found_selects)

    def test_serialize_turtle_format(
        self, mock_ontology_service: MagicMock
    ) -> None:
        gen = SHACLShapeGenerator(mock_ontology_service)
        graph = gen.generate()
        ttl = gen.serialize(graph, format="turtle")
        assert "sh:NodeShape" in ttl

    def test_save_writes_file(
        self, mock_ontology_service: MagicMock, tmp_path: object
    ) -> None:
        gen = SHACLShapeGenerator(mock_ontology_service)
        graph = gen.generate()
        out = gen.save(graph, tmp_path / "shapes.ttl")  # type: ignore[operator]
        assert out.exists()
        content = out.read_text()
        assert "sh:NodeShape" in content

    def test_generate_emits_qualified_value_shape(self, mock_ontology_service: MagicMock) -> None:
        gen = SHACLShapeGenerator(mock_ontology_service)
        graph = gen.generate()
        SH = rdflib.namespace.Namespace("http://www.w3.org/ns/shacl#")
        found_qualified = False
        for s, p, o in graph.triples((None, SH.property, None)):
            for _, _, path in graph.triples((o, SH.path, None)):
                if str(path).endswith("hasPrimaryContact"):
                    # check for qualifiedValueShape and qualifiedMaxCount
                    for _, _, qvs in graph.triples((o, SH.qualifiedValueShape, None)):
                        found_qualified = True
                    for _, _, qmax in graph.triples((o, SH.qualifiedMaxCount, None)):
                        assert int(str(qmax)) == 1
        assert found_qualified is True
