from __future__ import annotations

import pytest

from kgbuilder.storage.protocol import Node
from kgbuilder.validation.consistency_checker import ConsistencyChecker, ConsistencyReport
from kgbuilder.validation.models import Conflict, ConflictType


class DummyStore:
    """Minimal in-memory store for testing."""

    def __init__(self, nodes: list[Node]) -> None:
        self._nodes = list(nodes)

    def get_all_nodes(self) -> list[Node]:
        return list(self._nodes)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def test_get_node_by_id_returns_correct_node() -> None:
    a = Node(id="1", node_type="TypeA")
    b = Node(id="2", node_type="TypeB")
    store = DummyStore([a, b])
    found = ConsistencyChecker._get_node_by_id(store, "2")
    assert found is b
    assert ConsistencyChecker._get_node_by_id(store, "does-not-exist") is None


def test_compute_similarity_various_cases() -> None:
    # same type and identical labels -> max score
    n1 = Node(id="1", node_type="Person", label="Alice")
    n2 = Node(id="2", node_type="Person", label="Alice")
    score = ConsistencyChecker.compute_similarity(n1, n2)
    # Because of the 0.3/0.4/0.3 weighting, identical nodes score 0.7
    assert score == pytest.approx(0.7)

    # different types should drop type component to zero
    n3 = Node(id="3", node_type="Org", label="Alice")
    score = ConsistencyChecker.compute_similarity(n1, n3)
    # type component zero, label similarity 1 => 0.4 total
    assert score == pytest.approx(0.4)

    # property overlap contributes
    n4 = Node(
        id="4", node_type="Person", label="Bob", properties={"a": 1, "b": 2}
    )
    n5 = Node(
        id="5", node_type="Person", label="Bobby", properties={"b": 3, "c": 4}
    )
    score = ConsistencyChecker.compute_similarity(n4, n5)
    # they share type and one property key ('b'), so score positive
    assert 0 < score < 1


def test_report_to_dict_serialisation() -> None:
    conflict = Conflict(
        entity_id="1",
        conflict_type=ConflictType.TYPE_CONFLICT,
        description="oops",
    )
    report = ConsistencyReport(conflicts=[conflict], duplicates=[{"entities": ["1"]}])
    # make conflict_count consistent with contents
    report.conflict_count = len(report.conflicts)
    d = report.to_dict()
    assert d["conflict_count"] == 1
    assert d["conflicts"][0]["conflict_type"] == ConflictType.TYPE_CONFLICT.value
    assert "duplicates" in d
    assert d["recommendations"] == []


# ---------------------------------------------------------------------------
# individual consistency rules
# ---------------------------------------------------------------------------

def test_type_conflict_detection() -> None:
    # node with incompatible types in properties['types'] list
    n = Node(
        id="n",
        node_type="Whatever",
        properties={"types": ["Person", "Organization"]},
    )
    store = DummyStore([n])
    conflicts = ConsistencyChecker()._check_type_conflicts(store)
    # algorithm produces two entries (person/org and org/person) but at least one
    assert len(conflicts) >= 1
    assert all(c.conflict_type == ConflictType.TYPE_CONFLICT for c in conflicts)


def test_value_conflict_detection() -> None:
    n = Node(
        id="n", node_type="T", properties={"p": ["a", "b", "a"]}
    )
    store = DummyStore([n])
    conflicts = ConsistencyChecker()._check_value_conflicts(store)
    assert len(conflicts) == 1
    assert conflicts[0].conflict_type == ConflictType.VALUE_CONFLICT


def test_cardinality_conflict_detection() -> None:
    n = Node(id="n", node_type="T", properties={"email": ["one", "two"]})
    store = DummyStore([n])
    conflicts = ConsistencyChecker()._check_cardinality_conflicts(store)
    assert len(conflicts) == 1
    assert conflicts[0].conflict_type == ConflictType.CARDINALITY_CONFLICT


def test_find_conflicts_pairwise() -> None:
    # two nodes same type, same property key with different values
    a = Node(id="a", node_type="Person", properties={"age": 30})
    b = Node(id="b", node_type="Person", properties={"age": 31})
    store = DummyStore([a, b])
    conflicts = ConsistencyChecker().find_conflicts(store, "a")
    assert len(conflicts) == 1
    c = conflicts[0]
    assert c.entity_id == "a"
    assert c.conflict_type == ConflictType.VALUE_CONFLICT
    assert "age" in c.description


def test_find_duplicates_threshold() -> None:
    # create two very similar nodes
    a = Node(id="a", node_type="Person", label="Alice")
    b = Node(id="b", node_type="Person", label="Alice")
    store = DummyStore([a, b])
    dups = ConsistencyChecker().find_duplicates(store, threshold=0.5)
    assert len(dups) == 1
    assert set(dups[0]["entities"]) == {"a", "b"}


def test_check_consistency_aggregates_conflicts_and_recs() -> None:
    a = Node(id="x", node_type="T", properties={"p": [1, 2]})
    store = DummyStore([a])
    report = ConsistencyChecker().check_consistency(store)
    # value conflict should be detected
    assert report.conflict_count == 1
    assert report.recommendations
    assert report.duplicates == []


# ---------------------------------------------------------------------------
# error handling
# ---------------------------------------------------------------------------

def test_check_consistency_handles_store_error(monkeypatch) -> None:
    class BadStore(DummyStore):
        def get_all_nodes(self):
            raise RuntimeError("boom")

    report = ConsistencyChecker().check_consistency(BadStore([]))
    assert report.conflict_count == 0
    # The internal checks swallow exceptions; we simply ensure no exception is raised
    assert isinstance(report.recommendations, list)
