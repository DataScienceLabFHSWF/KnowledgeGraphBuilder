"""Tests for SHACL2FOL action converter."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

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
            subject_shape="http://ex.org/FacilityShape",
            object_shape="http://ex.org/OrganizationShape",
        )
        d = action.to_dict()
        assert d["type"] == "ShapeAction"
        assert d["subjectShape"] == "http://ex.org/FacilityShape"
        assert d["objectShape"] == "http://ex.org/OrganizationShape"


class TestPathAction:
    """Test PathAction dataclass."""

    def test_to_dict_format(self) -> None:
        action = PathAction(path="http://ex.org/requires")
        d = action.to_dict()
        assert d["type"] == "PathAction"
        assert d["path"] == "http://ex.org/requires"


class TestActionSet:
    """Test ActionSet collection."""

    def test_empty_set(self) -> None:
        action_set = ActionSet()
        assert action_set.total_actions == 0
        assert action_set.to_json_list() == []

    def test_mixed_actions(self) -> None:
        action_set = ActionSet(
            shape_actions=[
                ShapeAction("http://ex.org/A", "http://ex.org/B"),
            ],
            path_actions=[
                PathAction("http://ex.org/prop"),
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
            shape_actions=[
                ShapeAction("http://ex.org/A", "http://ex.org/B"),
            ],
        )
        path = converter.write_json(action_set, tmp_path / "actions.json")
        assert path.exists()

        with open(path) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["type"] == "ShapeAction"

    def test_read_json_round_trip(self, tmp_path: Path) -> None:
        converter = ActionConverter()
        action_set = ActionSet(
            shape_actions=[
                ShapeAction("http://ex.org/A", "http://ex.org/B"),
            ],
            path_actions=[
                PathAction("http://ex.org/prop"),
            ],
        )
        path = converter.write_json(action_set, tmp_path / "actions.json")
        loaded = ActionConverter.read_json(path)
        assert len(loaded) == 2

    def test_from_entities_creates_shape_actions(self) -> None:
        converter = ActionConverter()
        entity = MagicMock()
        entity.entity_type = "Facility"
        entity.label = "KKW Emsland"
        actions = converter.from_entities([entity])
        assert actions.total_actions == 1
        assert actions.shape_actions[0].subject_shape.endswith("FacilityShape")

    def test_from_relations_creates_path_and_shape_actions(self) -> None:
        converter = ActionConverter()
        relation = MagicMock()
        relation.relation_type = "requires"
        relation.source_type = "Facility"
        relation.target_type = "Document"
        actions = converter.from_relations([relation])
        assert len(actions.path_actions) == 1
        assert len(actions.shape_actions) == 1
        assert actions.path_actions[0].path.endswith("requires")
