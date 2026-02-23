"""Tests for FusekiOntologyService behaviour (with a fake store)."""

from __future__ import annotations

from pathlib import Path

import pytest

from kgbuilder.storage.ontology import FusekiOntologyService


# fixture moved further down so DummyStore is defined first


class DummyStore:
    def __init__(self, results=None):
        self._results = results or {}
        self.queries = []

    def query_sparql(self, q: str):
        self.queries.append(q)
        return self._results


@pytest.fixture(autouse=True)
def _fake_store(monkeypatch):
    """Replace FusekiStore with DummyStore so ctor never hits network."""

    def factory(url, dataset_name, username=None, password=None):
        return DummyStore()

    monkeypatch.setattr("kgbuilder.storage.ontology.FusekiStore", factory)
    yield


def test_get_all_classes_caching(tmp_path: Path):
    fake_data = {
        "results": {
            "bindings": [
                {"class": {"value": "http://ex/A"}, "label": {"value": "A"}},
                {"class": {"value": "http://ex/B"}},
            ]
        }
    }
    svc = FusekiOntologyService("url", "ds")
    # replace internal store with dummy
    svc.store = DummyStore(results=fake_data)
    classes1 = svc.get_all_classes()
    assert classes1 == ["A", "B"]
    # call again should return cached version and not query again
    classes2 = svc.get_all_classes()
    assert classes2 == classes1
    assert len(svc.store.queries) == 1


def test_get_all_classes_failure(monkeypatch):
    svc = FusekiOntologyService("url", "ds")
    def bad_query(q):
        raise RuntimeError("fail")
    svc.store = DummyStore()
    svc.store.query_sparql = bad_query
    with pytest.raises(RuntimeError):
        svc.get_all_classes()


def test_get_class_properties_mapping():
    # prepare results with various datatypes
    fake = {
        "results": {"bindings": [
            {
                "prop": {"value": "http://ex/p1"},
                "propLabel": {"value": "Prop1"},
                "range": {"value": "xsd:integer"},
                "comment": {"value": "desc"},
            },
            {
                "prop": {"value": "http://ex/p2"},
                # missing label -> fallback to URI fragment
                "range": {"value": "xsd:string"},
            },
        ]}
    }
    svc = FusekiOntologyService("url", "ds")
    svc.store = DummyStore(results=fake)
    props = svc.get_class_properties("ClassX")
    # should return 2 tuples with expected types
    assert len(props) == 2
    names = [p[0] for p in props]
    assert "Prop1" in names


def test_get_class_properties_handles_errors():
    svc = FusekiOntologyService("url", "ds")
    svc.store = DummyStore()
    svc.store.query_sparql = lambda q: (_ for _ in ()).throw(ValueError("oops"))
    props = svc.get_class_properties("C")
    assert props == []


def test_get_class_relations_and_error():
    svc = FusekiOntologyService("url", "ds")
    # success case with missing label fallback
    fake = {"results": {"bindings": [
        {"prop": {"value": "http://ex/r1"}, "label": {"value": "Rel1"}},
        {"prop": {"value": "http://ex/r2"}},
    ]}}
    svc.store = DummyStore(results=fake)
    rels = svc.get_class_relations("http://ex/Class")
    assert set(rels) == {"Rel1", "r2"}
    # error path should raise RuntimeError
    svc.store = DummyStore()
    svc.store.query_sparql = lambda q: (_ for _ in ()).throw(Exception("fail"))
    with pytest.raises(RuntimeError):
        svc.get_class_relations("http://ex/Class")


def test_get_all_relations_and_error():
    svc = FusekiOntologyService("url", "ds")
    fake = {"results": {"bindings": [
        {"prop": {"value": "http://ex/o1"}, "label": {"value": "Obj1"}},
        {"prop": {"value": "http://ex/o2"}},
    ]}}
    svc.store = DummyStore(results=fake)
    all_rels = svc.get_all_relations()
    assert set(all_rels) == {"Obj1", "o2"}
    # failure returns empty list
    svc.store = DummyStore()
    svc.store.query_sparql = lambda q: (_ for _ in ()).throw(Exception("boom"))
    assert svc.get_all_relations() == []


def test_get_class_hierarchy_variants():
    svc = FusekiOntologyService("url", "ds")
    # include explicit labels so the service uses them rather than raw URIs
    fake = {"results": {"bindings": [
        {
            "child": {"value": "http://ex/Child"},
            "parent": {"value": "http://ex/Parent"},
            "childLabel": {"value": "Child"},
            "parentLabel": {"value": "Parent"},
        },
        {"child": {"value": "http://ex/Parent"}, "parent": {"value": "http://ex/Root"}, "childLabel": {"value": "P"}},
    ]}}
    svc.store = DummyStore(results=fake)
    # full list should include simplified tuples
    pairs = svc.get_class_hierarchy()
    assert ("Child", "Parent") in pairs
    # request specific by exact name
    info = svc.get_class_hierarchy("Child")
    assert info["parents"] == ["Parent"]
    # case-insensitive lookup
    info2 = svc.get_class_hierarchy("child")
    assert info2["children"] == []
    # missing class returns empty structure
    info3 = svc.get_class_hierarchy("Unknown")
    assert info3 == {"parents": [], "children": [], "depth": 0}
    # error path
    svc.store = DummyStore()
    svc.store.query_sparql = lambda q: (_ for _ in ()).throw(ValueError("err"))
    assert svc.get_class_hierarchy() == []
    assert svc.get_class_hierarchy("X") == {"parents": [], "children": [], "depth": 0}


def test_special_properties_and_error():
    svc = FusekiOntologyService("url", "ds")
    # prepare for transitive/symmetric/functional
    fake1 = {"results": {"bindings": [
        {"prop": {"value": "http://ex/t"}, "label": {"value": "T"}},
    ]}}
    # prepare inverses
    fake2 = {"results": {"bindings": [
        {"p1": {"value": "http://ex/a"}, "p1Label": {"value": "A"}, "p2": {"value": "http://ex/b"}},
    ]}}
    # sequence of results will be used by DummyStore sequentially
    class SeqStore(DummyStore):
        def __init__(self, results_list):
            super().__init__()
            self._results_list = results_list
        def query_sparql(self, q: str):
            return self._results_list.pop(0)
    svc.store = SeqStore([fake1, fake1, fake1, fake2])
    props = svc.get_special_properties()
    assert props["transitive"] == ["T"]
    # second element uses fallback splitting only on '#', so without '#' returns full URI
    assert props["inverse"] == [("A", "http://ex/b")]
    # error path returns empty categories
    svc.store = DummyStore()
    svc.store.query_sparql = lambda q: (_ for _ in ()).throw(RuntimeError("bad"))
    empt = svc.get_special_properties()
    assert empt == {"transitive": [], "symmetric": [], "functional": [], "inverse": []}
