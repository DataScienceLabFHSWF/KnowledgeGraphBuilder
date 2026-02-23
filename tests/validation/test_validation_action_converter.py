"""Tests for SHACL2FOL action converter."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from kgbuilder.validation.action_converter import (
    ActionConverter,
    ActionSet,
    PathAction,
    ShapeAction,
)


class TestShapeAction:
    """Test ShapeAction dataclass."""

    def test_to_dict_format(self) -> None:
        action = ShapeAction(
            predicate="http://ex.org/hasPart",
            subject_shape="@prefix sh: ... :s a sh:NodeShape ; sh:class <http://ex.org/Facility> .",
            object_shape="@prefix sh: ... :s a sh:NodeShape ; sh:class <http://ex.org/Organization> .",
        )
        d = action.to_dict()
        assert d["type"] == "ShapeAction"
        assert d["isAdd"] is True
        assert d["predicate"] == "http://ex.org/hasPart"
        assert "Facility" in d["subjectShape"]
        assert "Organization" in d["objectShape"]

    def test_is_add_false(self) -> None:
        action = ShapeAction(
            predicate="http://ex.org/hasPart",
            subject_shape="...",
            object_shape="...",
            is_add=False,
        )
        d = action.to_dict()
        assert d["isAdd"] is False


class TestPathAction:
    """Test PathAction dataclass."""

    def test_to_dict_format(self) -> None:
        action = PathAction(
            predicate="http://ex.org/requires",
            path="<http://ex.org/requires>",
        )
        d = action.to_dict()
        assert d["type"] == "PathAction"
        assert d["isAdd"] is True
        assert d["predicate"] == "http://ex.org/requires"
        assert d["path"] == "<http://ex.org/requires>"

    def test_is_add_false(self) -> None:
        action = PathAction(
            predicate="http://ex.org/requires",
            path="<http://ex.org/requires>",
            is_add=False,
        )
        d = action.to_dict()
        assert d["isAdd"] is False


class TestActionSet:
    """Test ActionSet collection."""

    def test_empty_set(self) -> None:
        action_set = ActionSet()
        assert action_set.total_actions == 0
        assert action_set.to_json_list() == []

    def test_mixed_actions(self) -> None:
        action_set = ActionSet(
            shape_actions=[
                ShapeAction(
                    predicate="http://ex.org/p",
                    subject_shape="...",
                    object_shape="...",
                ),
            ],
            path_actions=[
                PathAction(predicate="http://ex.org/prop", path="<http://ex.org/prop>"),
            ],
        )
        assert action_set.total_actions == 2
        json_list = action_set.to_json_list()
        assert len(json_list) == 2
        assert json_list[0]["type"] == "ShapeAction"
        assert json_list[1]["type"] == "PathAction"


class TestActionConverter:
    """Test ActionConverter."""

    def test_init_default_namespaces(self) -> None:
        converter = ActionConverter()
        assert "shapes" in converter._shapes_ns
        assert "ontology" in converter._ont_ns

    def test_init_custom_namespaces(self) -> None:
        converter = ActionConverter(
            shapes_namespace="http://custom.org/shapes/",
            ontology_namespace="http://custom.org/onto#",
        )
        assert converter._shapes_ns == "http://custom.org/shapes/"
        assert converter._ont_ns == "http://custom.org/onto#"

    def test_write_json_creates_file(self, tmp_path: Path) -> None:
        converter = ActionConverter()
        action_set = ActionSet(
            path_actions=[
                PathAction(predicate="http://ex.org/p", path="<http://ex.org/p>"),
            ],
        )
        path = converter.write_json(action_set, tmp_path / "actions.json")
        assert path.exists()

        with open(path) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["type"] == "PathAction"

    def test_read_json_round_trip(self, tmp_path: Path) -> None:
        converter = ActionConverter()
        action_set = ActionSet(
            shape_actions=[
                ShapeAction(
                    predicate="http://ex.org/p",
                    subject_shape="...",
                    object_shape="...",
                ),
            ],
            path_actions=[
                PathAction(predicate="http://ex.org/prop", path="<http://ex.org/prop>"),
            ],
        )
        path = converter.write_json(action_set, tmp_path / "actions.json")
        loaded = ActionConverter.read_json(path)
        assert len(loaded) == 2

    def test_from_entities_creates_path_actions(self) -> None:
        converter = ActionConverter()
        entity = MagicMock()
        entity.entity_type = "Facility"
        actions = converter.from_entities([entity])
        assert actions.total_actions == 1
        assert len(actions.path_actions) == 1
        assert actions.path_actions[0].predicate.endswith("type")
        assert actions.path_actions[0].is_add is True

    def test_from_entities_deduplicates_by_type(self) -> None:
        converter = ActionConverter()
        e1 = MagicMock()
        e1.entity_type = "Facility"
        e2 = MagicMock()
        e2.entity_type = "Facility"
        actions = converter.from_entities([e1, e2])
        assert actions.total_actions == 1

    def test_from_entities_remove_sets_is_add_false(self) -> None:
        converter = ActionConverter()
        entity = MagicMock()
        entity.entity_type = "Facility"
        actions = converter.from_entities([entity], operation="remove")
        assert actions.path_actions[0].is_add is False
        d = actions.path_actions[0].to_dict()
        assert d["isAdd"] is False

    def test_from_relations_creates_path_actions(self) -> None:
        converter = ActionConverter()
        relation = MagicMock()
        relation.relation_type = "requires"
        relation.source_type = "Facility"
        relation.target_type = "Document"
        actions = converter.from_relations([relation])
        assert len(actions.path_actions) == 1
        assert "requires" in actions.path_actions[0].predicate
        assert actions.path_actions[0].is_add is True

    def test_from_relations_expands_inverse_using_ontology(self) -> None:
        mock_onto = MagicMock()
        mock_onto.get_special_properties.return_value = {
            "inverse": [("requires", "requiredBy")],
        }
        converter = ActionConverter(ontology_service=mock_onto)
        rel = MagicMock()
        rel.relation_type = "requires"
        rel.source_type = "Facility"
        rel.target_type = "Document"
        actions = converter.from_relations([rel])
        predicates = [p.predicate for p in actions.path_actions]
        assert any(p.endswith("requires") for p in predicates)
        assert any(p.endswith("requiredBy") for p in predicates)

    def test_update_produces_remove_and_add(self) -> None:
        """Update operation should produce both is_add=False and is_add=True actions."""
        converter = ActionConverter()
        entity = MagicMock()
        entity.entity_type = "Facility"
        actions = converter.from_entities([entity], operation="update")
        json_list = actions.to_json_list()
        is_add_values = {a["isAdd"] for a in json_list}
        assert True in is_add_values
        assert False in is_add_values
