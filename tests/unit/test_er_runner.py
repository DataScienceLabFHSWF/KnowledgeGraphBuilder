"""Tests for internal ER runner (find_merge_candidates)."""
from __future__ import annotations

from kgbuilder.analytics.er_runner import find_merge_candidates
from kgbuilder.storage.protocol import InMemoryGraphStore, Node


def test_find_merge_candidates_basic() -> None:
    store = InMemoryGraphStore()
    # Two similar labels, one distinct
    store.add_node(Node(id="n1", node_type="Concept", label="Kernbrennstoff", properties={"embedding": [1.0, 0.0]}))
    store.add_node(Node(id="n2", node_type="Concept", label="nuklearer Brennstoff", properties={"embedding": [0.99, 0.1]}))
    store.add_node(Node(id="n3", node_type="Concept", label="Facility", properties={"embedding": [0.0, 1.0]}))

    candidates = find_merge_candidates(store, node_types=["Concept"], edit_weight=0.3, sim_threshold=0.7)
    assert any({"n1", "n2"}.issubset(c.ids) for c in candidates)
    # ensure distinct node not merged
    assert not any({"n3", "n1"}.issubset(c.ids) for c in candidates)
