"""Tests for HermiT/Pellet OWL DL consistency reasoning (SEMANTiCS 2026 Phase C)."""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from kgbuilder.validation.consistency_reasoner import ConsistencyReasoner


def _install_fake_owlready2(
    monkeypatch, *, inconsistent_classes=None, load_error=None, reasoner_error=None,
):
    """Install a fake `owlready2` module in `sys.modules` for isolated testing."""
    fake = types.ModuleType("owlready2")

    fake_world = MagicMock()
    if load_error is not None:
        fake_world.get_ontology.return_value.load.side_effect = load_error
    else:
        fake_onto = MagicMock()
        fake_onto.__enter__ = MagicMock(return_value=fake_onto)
        fake_onto.__exit__ = MagicMock(return_value=False)
        fake_world.get_ontology.return_value.load.return_value = fake_onto
    fake_world.inconsistent_classes.return_value = inconsistent_classes or []

    fake.World = MagicMock(return_value=fake_world)

    def _sync_reasoner(*args, **kwargs):
        if reasoner_error is not None:
            raise reasoner_error

    fake.sync_reasoner_hermit = MagicMock(side_effect=_sync_reasoner)
    fake.sync_reasoner_pellet = MagicMock(side_effect=_sync_reasoner)

    monkeypatch.setitem(sys.modules, "owlready2", fake)
    return fake, fake_world


def test_invalid_reasoner_name_raises() -> None:
    with pytest.raises(ValueError):
        ConsistencyReasoner(reasoner="not-a-reasoner")


def test_missing_owlready2_module_reports_error(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "owlready2", None)  # forces ImportError on `import owlready2`

    result = ConsistencyReasoner().check_consistency("does-not-matter.owl")

    assert result.consistent is False
    assert result.error is not None
    assert "owlready2" in result.error
    assert "reasoning" in result.error  # points at the install extra


def test_missing_ontology_file_reports_error(monkeypatch, tmp_path: Path) -> None:
    _install_fake_owlready2(monkeypatch)

    result = ConsistencyReasoner().check_consistency(tmp_path / "nope.owl")

    assert result.consistent is False
    assert "not found" in result.error


def test_consistent_ontology_reports_no_unsatisfiable_classes(monkeypatch, tmp_path: Path) -> None:
    fake, fake_world = _install_fake_owlready2(monkeypatch, inconsistent_classes=[])
    onto_path = tmp_path / "onto.owl"
    onto_path.write_text("<rdf:RDF></rdf:RDF>")

    result = ConsistencyReasoner(reasoner="hermit").check_consistency(onto_path)

    assert result.consistent is True
    assert result.unsatisfiable_classes == []
    assert result.reasoner == "hermit"
    assert result.error is None
    fake.sync_reasoner_hermit.assert_called_once()
    fake.sync_reasoner_pellet.assert_not_called()


def test_inconsistent_ontology_reports_unsatisfiable_classes(monkeypatch, tmp_path: Path) -> None:
    _install_fake_owlready2(monkeypatch, inconsistent_classes=["onto.Facility", "onto.Waste"])
    onto_path = tmp_path / "onto.owl"
    onto_path.write_text("<rdf:RDF></rdf:RDF>")

    result = ConsistencyReasoner().check_consistency(onto_path)

    assert result.consistent is False
    assert result.unsatisfiable_classes == ["onto.Facility", "onto.Waste"]
    assert result.error is None  # a completed check with real findings is not an "error"


def test_pellet_reasoner_is_used_when_requested(monkeypatch, tmp_path: Path) -> None:
    fake, _ = _install_fake_owlready2(monkeypatch)
    onto_path = tmp_path / "onto.owl"
    onto_path.write_text("<rdf:RDF></rdf:RDF>")

    result = ConsistencyReasoner(reasoner="pellet").check_consistency(onto_path)

    assert result.reasoner == "pellet"
    fake.sync_reasoner_pellet.assert_called_once()
    fake.sync_reasoner_hermit.assert_not_called()


def test_ontology_load_failure_reports_error(monkeypatch, tmp_path: Path) -> None:
    _install_fake_owlready2(monkeypatch, load_error=RuntimeError("malformed RDF"))
    onto_path = tmp_path / "onto.owl"
    onto_path.write_text("not valid rdf")

    result = ConsistencyReasoner().check_consistency(onto_path)

    assert result.consistent is False
    assert "malformed RDF" in result.error


def test_reasoner_invocation_failure_reports_error(monkeypatch, tmp_path: Path) -> None:
    _install_fake_owlready2(monkeypatch, reasoner_error=RuntimeError("java process crashed"))
    onto_path = tmp_path / "onto.owl"
    onto_path.write_text("<rdf:RDF></rdf:RDF>")

    result = ConsistencyReasoner().check_consistency(onto_path)

    assert result.consistent is False
    assert "java process crashed" in result.error


def test_to_dict_serializes_result() -> None:
    from kgbuilder.validation.consistency_reasoner import ConsistencyCheckResult

    result = ConsistencyCheckResult(
        consistent=True, unsatisfiable_classes=[], reasoner="hermit", duration_ms=12.345,
    )

    assert result.to_dict() == {
        "consistent": True,
        "unsatisfiable_classes": [],
        "reasoner": "hermit",
        "duration_ms": 12.35,
        "error": None,
    }
