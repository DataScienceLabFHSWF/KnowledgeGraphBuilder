import pytest
import rdflib
import sys
from pathlib import Path
from types import SimpleNamespace

from kgbuilder.validation.shacl_generator import SHACLShapeGenerator


class EmptyOntology:
    def get_all_classes(self):
        return []
    def get_class_properties(self, cls):
        return []
    def get_special_properties(self):
        return {}


class SimpleOntology:
    def get_all_classes(self):
        return ["A"]

    def get_class_properties(self, cls):
        # one datatype property with xsd:string range and one object property
        return [
            ("prop1", "DatatypeProperty", "xsd:string", {}),
            ("rel", "ObjectProperty", "B", {"qualified_value_shape": "B", "qualified_max_count": 2}),
        ]

    def get_special_properties(self):
        return {"functional": ["prop1"]}


def test_generate_empty_ontology():
    gen = SHACLShapeGenerator(EmptyOntology())
    g = gen.generate()
    assert isinstance(g, rdflib.Graph)
    # there may only be namespace bindings; no NodeShape triples should be added
    SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")
    assert not any(o == SH.NodeShape for _, _, o in g.triples((None, rdflib.RDF.type, None)))


def test_generate_basic_shapes():
    gen = SHACLShapeGenerator(SimpleOntology(), namespace="http://example.org/shapes/", ontology_namespace="http://example.org/ont#")
    g = gen.generate()
    # there should be a NodeShape for class A
    SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")
    ONT = rdflib.Namespace("http://example.org/ont#")
    shape_uri = rdflib.URIRef("http://example.org/shapes/AShape")
    assert (shape_uri, rdflib.RDF.type, SH.NodeShape) in g
    assert (shape_uri, SH.targetClass, ONT.A) in g
    # property shape for prop1 should have datatype xsd:string and maxCount 1
    # locate blank node property
    props = list(g.objects(shape_uri, SH.property))
    assert props, "no property shapes emitted"
    # property with path ending prop1
    found = False
    for b in props:
        path = g.value(b, SH.path)
        if str(path).endswith("prop1"):
            found = True
            assert (b, SH.datatype, rdflib.XSD.string) in g
            assert (b, SH.maxCount, rdflib.Literal(1)) in g
    assert found
    # check qualified max count for rel
    found_rel = False
    for b in props:
        path = g.value(b, SH.path)
        if str(path).endswith("rel"):
            found_rel = True
            assert (b, SH.qualifiedMaxCount, rdflib.Literal(2)) in g
    assert found_rel


def test_generate_for_class():
    gen = SHACLShapeGenerator(SimpleOntology())
    frag = gen.generate_for_class("A")
    # should only include triples related to class A
    SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")
    ONT = rdflib.Namespace("https://purl.org/ai4s/ontology/planning#")
    assert len(list(frag.subjects(SH.targetClass, ONT.A))) == 1
    # there should be at least one property shape attached
    shape = list(frag.subjects(SH.targetClass, ONT.A))[0]
    assert list(frag.objects(shape, SH.property))


def test_serialize_and_save(tmp_path: Path) -> None:
    gen = SHACLShapeGenerator(SimpleOntology())
    g = gen.generate()
    txt = gen.serialize(g, format="turtle")
    assert isinstance(txt, str)
    file = tmp_path / "shapes.ttl"
    out = gen.save(g, file)
    assert out == file
    assert file.read_text().startswith("@prefix")


def test_generate_raises_without_rdflib(monkeypatch):
    orig = sys.modules.get("rdflib")
    monkeypatch.setitem(sys.modules, "rdflib", None)
    gen = SHACLShapeGenerator(SimpleOntology())
    with pytest.raises(RuntimeError):
        gen.generate()
    monkeypatch.setitem(sys.modules, "rdflib", orig)


def test_generate_for_class_raises_without_rdflib(monkeypatch):
    orig = sys.modules.get("rdflib")
    monkeypatch.setitem(sys.modules, "rdflib", None)
    gen = SHACLShapeGenerator(SimpleOntology())
    with pytest.raises(RuntimeError):
        gen.generate_for_class("A")
    monkeypatch.setitem(sys.modules, "rdflib", orig)


def test_add_special_constraints_annotations() -> None:
    # build a tiny graph with property shapes for names
    import rdflib
    from rdflib import Namespace, URIRef, BNode
    from rdflib.namespace import SH, RDFS

    g = rdflib.Graph()
    for pname in ("prop1", "prop2", "prop3", "propX"):
        b = BNode()
        g.add((rdflib.BNode(), SH.property, b))
        g.add((b, SH.path, URIRef(f"http://example/{pname}")))

    class FullOntology(SimpleOntology):
        def get_special_properties(self):
            return {
                "functional": ["prop1"],
                "symmetric": ["prop2"],
                "transitive": ["prop3"],
                "inverse": [("prop1", "propX")],
            }

    gen = SHACLShapeGenerator(FullOntology(), ontology_namespace="http://example/")
    gen._add_special_constraints(g)
    # functional prop1 should yield a maxCount literal
    assert any((None, SH.maxCount, None) for _ in g.triples((None, None, None)))
    # the SPARQL queries for symmetric/transitive should be added
    assert any("FILTER NOT EXISTS" in str(o) for s, p, o in g.triples((None, SH.select, None)))
    # comments for inverse declarations should exist
    assert any((None, RDFS.comment, None) for _ in g.triples((None, None, None)))


def test_generate_handles_empty_lists() -> None:
    class EmptyOnt(SimpleOntology):
        def get_all_classes(self):
            return []

    gen = SHACLShapeGenerator(EmptyOnt())
    g = gen.generate()
    # graph may contain only the top-level comment triple but no NodeShapes
    from rdflib.namespace import SH
    assert not any(o == SH.NodeShape for _, _, o in g.triples((None, rdflib.RDF.type, None)))
