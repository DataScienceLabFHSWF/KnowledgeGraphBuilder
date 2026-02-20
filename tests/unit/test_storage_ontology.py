import pytest

from unittest.mock import MagicMock

from kgbuilder.storage.ontology import FusekiOntologyService


@pytest.fixture
def sample_hierarchy_result() -> dict:
    return {
        "results": {
            "bindings": [
                {
                    "child": {"value": "http://example.org#ChildA"},
                    "childLabel": {"value": "ChildA"},
                    "parent": {"value": "http://example.org#Parent1"},
                    "parentLabel": {"value": "Parent1"},
                },
                {
                    "child": {"value": "http://example.org#ChildB"},
                    "childLabel": {"value": "ChildB"},
                    "parent": {"value": "http://example.org#Parent1"},
                    "parentLabel": {"value": "Parent1"},
                },
                {
                    "child": {"value": "http://example.org#GrandChild"},
                    "childLabel": {"value": "GrandChild"},
                    "parent": {"value": "http://example.org#ChildA"},
                    "parentLabel": {"value": "ChildA"},
                },
            ]
        }
    }


def make_service_with_mock_store(sample_result: dict) -> FusekiOntologyService:
    # Avoid network calls in FusekiStore.__init__ by creating the object
    # without invoking __init__, then inject a mocked `store`.
    svc = object.__new__(FusekiOntologyService)
    svc.store = MagicMock()
    svc.store.query_sparql.return_value = sample_result
    svc._classes_cache = None
    return svc


def test_get_class_hierarchy_full_returns_pairs(sample_hierarchy_result: dict) -> None:
    svc = make_service_with_mock_store(sample_hierarchy_result)

    pairs = svc.get_class_hierarchy()

    assert isinstance(pairs, list)
    assert ("ChildA", "Parent1") in pairs
    assert ("GrandChild", "ChildA") in pairs
    assert ("ChildB", "Parent1") in pairs


def test_get_class_hierarchy_for_class_returns_dict(sample_hierarchy_result: dict) -> None:
    svc = make_service_with_mock_store(sample_hierarchy_result)

    info = svc.get_class_hierarchy("ChildA")

    assert isinstance(info, dict)
    assert info["parents"] == ["Parent1"]
    assert info["children"] == ["GrandChild"]
    # ChildA has one ancestor (Parent1) -> depth should be 1
    assert info["depth"] == 1

    # Unknown class returns empty structure
    empty = svc.get_class_hierarchy("NonExistent")
    assert empty == {"parents": [], "children": [], "depth": 0}
