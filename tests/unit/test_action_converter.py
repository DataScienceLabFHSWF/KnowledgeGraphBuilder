from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from kgbuilder.validation.action_converter import (
    ActionConverter,
    ShapeAction,
    PathAction,
    ActionSet,
)


@dataclass
class DummyEntity:
    entity_type: str


@dataclass
class DummyRelation:
    relation_type: str


# ---------------------------------------------------------------------------
# basic model serialization
# ---------------------------------------------------------------------------

def test_shape_action_to_dict() -> None:
    sa = ShapeAction(
        predicate="http://p",
        subject_shape="s",
        object_shape="o",
        is_add=False,
    )
    d = sa.to_dict()
    assert d["type"] == "ShapeAction"
    assert not d["isAdd"]
    assert d["predicate"] == "http://p"


def test_path_action_to_dict() -> None:
    pa = PathAction(predicate="p", path="<p>")
    d = pa.to_dict()
    assert d["type"] == "PathAction"
    assert d["path"] == "<p>"


def test_action_set_serialization() -> None:
    aset = ActionSet(
        shape_actions=[ShapeAction("p", "s", "o")],
        path_actions=[PathAction("q", "<q>")],
        metadata={"foo": "bar"},
    )
    lst = aset.to_json_list()
    assert len(lst) == 2
    assert aset.total_actions == 2


# ---------------------------------------------------------------------------
# converter helpers and behaviour
# ---------------------------------------------------------------------------

def test_entity_relation_type_helpers() -> None:
    conv = ActionConverter()

    @dataclass
    class HasType:
        type: str

    @dataclass
    class HasPred:
        predicate: str

    assert conv._get_entity_type(HasType(type="X")) == "X"
    assert conv._get_entity_type(DummyEntity(entity_type="Y")) == "Y"

    assert conv._get_relation_type(HasPred(predicate="foo")) == "foo"
    assert conv._get_relation_type(
        DummyRelation(relation_type="bar")
    ) == "bar"


def test_inline_shape_contains_namespace() -> None:
    conv = ActionConverter(shapes_namespace="http://sh/")
    s = conv._inline_shape("http://ont/Foo")
    assert "http://sh/" in s
    assert "http://ont/Foo" in s


def test_from_entities_basic() -> None:
    conv = ActionConverter(ontology_namespace="http://ont/")
    e = DummyEntity(entity_type="Person")
    aset = conv.from_entities([e])
    # should produce a single path action for rdf:type
    assert aset.metadata["generated_from"] == "entities"
    assert aset.path_actions
    assert aset.path_actions[0].predicate == conv._RDF_TYPE


def test_from_relations_basic() -> None:
    conv = ActionConverter(ontology_namespace="http://ont/")
    r = DummyRelation(relation_type="knows")
    aset = conv.from_relations([r])
    assert aset.metadata["generated_from"] == "relations"
    assert aset.path_actions[0].predicate.endswith("knows")


def test_update_operation_merges_sets() -> None:
    conv = ActionConverter(ontology_namespace="http://ont/")
    e = DummyEntity(entity_type="E")
    aset = conv.from_entities([e], operation="update")
    assert aset.metadata["operation"] == "update"
    # both add and remove actions should be present
    assert len(aset.path_actions) == 2


def test_inverse_expansion() -> None:
    class MockOntology:
        def get_special_properties(self) -> dict[str, Any]:
            return {"inverse": [("a", "b")]}  # a<->b

    conv = ActionConverter(ontology_namespace="http://ont/", ontology_service=MockOntology())
    r = DummyRelation(relation_type="a")
    aset = conv.from_relations([r])
    predicates = [p.predicate for p in aset.path_actions]
    assert any("b" in pred for pred in predicates)


def test_serialization_to_file(tmp_path: Path) -> None:
    conv = ActionConverter()
    aset = conv.from_entities([DummyEntity(entity_type="Foo")])
    out_file = tmp_path / "actions.json"
    written = conv.write_json(aset, out_file)
    assert written == out_file
    loaded = conv.read_json(out_file)
    assert loaded == aset.to_json_list()


# ---------------------------------------------------------------------------
# edge cases
# ---------------------------------------------------------------------------

def test_from_entities_skips_duplicates_and_empty() -> None:
    conv = ActionConverter()
    class Foo:
        entity_type = "A"

    objs = [Foo(), Foo(), object()]  # last object has no type
    aset = conv.from_entities(objs)
    # only one action despite duplicates
    assert len(aset.path_actions) == 1


def test_from_relations_skips_unknowns() -> None:
    conv = ActionConverter()
    class Foo:
        pass

    aset = conv.from_relations([Foo()])
    assert aset.path_actions == []
