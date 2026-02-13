"""Unit tests for KGBuilder static validation wiring."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from kgbuilder.assembly.kg_builder import KGBuilder, KGBuilderConfig


class DummyStore:
    def __init__(self) -> None:
        self.nodes = []
        self.edges = []

    # GraphStore protocol expects batch_create_nodes(nodes: list)
    def batch_create_nodes(self, nodes):
        return [f"n{i}" for i, _ in enumerate(nodes)]

    def batch_create_edges(self, edges):
        return [f"e{i}" for i, _ in enumerate(edges)]

    def health_check(self):
        return True


class DummyStaticValidator:
    def __init__(self, valid: bool = True) -> None:
        self._valid = valid

    def validate_entities_and_relations(self, shapes_path: Path, entities, relations):
        class R:
            valid = self._valid
            counterexample = "" if self._valid else "violates shape"
        return R()


def test_build_aborts_when_static_validation_fails(tmp_path: Path) -> None:
    primary = DummyStore()
    cfg = KGBuilderConfig(enable_static_validation=True, static_shapes_path=str(tmp_path / "shapes.ttl"))
    sv = DummyStaticValidator(valid=False)
    builder = KGBuilder(primary, None, cfg, static_validator=sv)

    entities = [MagicMock(entity_type="Facility")]
    relations = []

    res = builder.build(entities, relations)
    assert res.nodes_created == 0
    assert any("Static validation failed" in w or "violates shape" in w for w in res.warnings)


def test_build_proceeds_when_static_validation_passes(tmp_path: Path) -> None:
    primary = DummyStore()
    cfg = KGBuilderConfig(enable_static_validation=True, static_shapes_path=str(tmp_path / "shapes.ttl"))
    sv = DummyStaticValidator(valid=True)
    builder = KGBuilder(primary, None, cfg, static_validator=sv)

    entities = [MagicMock(entity_type="Facility")]
    relations = []

    res = builder.build(entities, relations)
    assert res.nodes_created == 1
    assert res.edges_created == 0
