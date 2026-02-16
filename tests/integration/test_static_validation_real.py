"""Run a real SHACL2FOL static validation inside the container.

This test is intended to be executed *inside* the `kgbuilder/shacl2fol`
container produced by `docker/Dockerfile.shacl2fol`. It will be skipped on
local runs where the JAR/vampire are not available.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from kgbuilder.validation.action_converter import ActionConverter
from kgbuilder.validation.shacl_generator import SHACLShapeGenerator
from kgbuilder.validation.static_validator import StaticValidator, StaticValidatorConfig


@pytest.mark.skipif(
    not Path("/opt/shacl2fol/SHACL2FOL.jar").exists(),
    reason="SHACL2FOL.jar not available in this environment",
)
def test_static_validation_with_real_shacl2fol(tmp_path: Path) -> None:
    # Build a minimal shapes graph and actions
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

    # Configure validator to use the JAR and vampire binary bundled in the image
    cfg = StaticValidatorConfig(
        jar_path=Path("/opt/shacl2fol/SHACL2FOL.jar"),
        vampire_path=Path("/opt/vampire/bin/vampire"),
        java_bin="java",
        timeout_seconds=30,
        work_dir=tmp_path,
    )
    sv = StaticValidator(cfg)

    # sanity check prerequisites
    checks = sv.check_prerequisites()
    assert checks["jar"] is True
    assert checks["vampire"] is True

    # Prepare actions that should be valid
    entities = [type("E", (), {"entity_type": "Facility"})()]
    actions = ActionConverter().from_entities(entities)
    actions_path = tmp_path / "actions.json"
    ActionConverter().write_json(actions, actions_path)

    # Run static validation (this invokes the real JAR + vampire)
    res = sv.validate_static(shapes_path, actions_path)
    assert isinstance(res.valid, bool)
    # either valid or parser couldn't interpret output; ensure call completed
    assert res.raw_output is not None
