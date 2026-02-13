"""Integration-style tests for static validation pipeline (shapes → actions → validator).

These tests avoid running the real SHACL2FOL binary by monkeypatching the
subprocess invocation while still exercising the generator, converter, and
KGBuilder wiring used in production.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from kgbuilder.validation.shacl_generator import SHACLShapeGenerator
from kgbuilder.validation.static_validator import StaticValidator, StaticValidatorConfig
from kgbuilder.validation.action_converter import ActionConverter


class DummyEntity:
    def __init__(self, entity_type: str) -> None:
        self.entity_type = entity_type


def _fake_completed(stdout: str = "VALID"):
    class C:
        def __init__(self, stdout: str):
            self.stdout = stdout
            self.returncode = 0

    return C(stdout)


def test_end_to_end_static_validation_valid(tmp_path: Path, monkeypatch) -> None:
    # Create shapes from a mock ontology service
    class Svc:
        def get_all_classes(self):
            return ["Facility"]

        def get_class_properties(self, cls):
            return [("hasOperator", "ObjectProperty", "Organization")]

        def get_special_properties(self):
            return {"functional": ["hasOperator"]}

    gen = SHACLShapeGenerator(Svc())
    g = gen.generate()
    shapes_path = tmp_path / "shapes.ttl"
    gen.save(g, shapes_path)

    # Touch a fake JAR so StaticValidator._invoke_jar doesn't raise FileNotFoundError
    cfg = StaticValidatorConfig(jar_path=tmp_path / "SHACL2FOL.jar", vampire_path=tmp_path / "vampire", work_dir=tmp_path)
    cfg.jar_path.write_text("")

    sv = StaticValidator(cfg)

    # Prepare actions (one entity + no relations)
    entities = [DummyEntity("Facility")]
    actions = ActionConverter().from_entities(entities)

    # Mock subprocess run to return a VALID response
    with patch("subprocess.run") as pr:
        pr.return_value = _fake_completed("VALID\n")
        res = sv.validate_entities_and_relations(shapes_path, entities, [])
        assert res.valid is True


def test_end_to_end_static_validation_invalid(tmp_path: Path, monkeypatch) -> None:
    # Build shapes as above
    class Svc:
        def get_all_classes(self):
            return ["Facility"]

        def get_class_properties(self, cls):
            return [("hasOperator", "ObjectProperty", "Organization")]

        def get_special_properties(self):
            return {"functional": ["hasOperator"]}

    gen = SHACLShapeGenerator(Svc())
    g = gen.generate()
    shapes_path = tmp_path / "shapes.ttl"
    gen.save(g, shapes_path)

    cfg = StaticValidatorConfig(jar_path=tmp_path / "SHACL2FOL.jar", vampire_path=tmp_path / "vampire", work_dir=tmp_path)
    cfg.jar_path.write_text("")
    sv = StaticValidator(cfg)

    # Two entities would violate the functional constraint
    entities = [DummyEntity("Facility"), DummyEntity("Facility")]

    with patch("subprocess.run") as pr:
        pr.return_value = _fake_completed("INVALID: counterexample ...\n")
        res = sv.validate_entities_and_relations(shapes_path, entities, [])
        assert res.valid is False
        assert "counterexample" in res.counterexample.lower() or res.error
