import pytest

from kgbuilder.storage.protocol import InMemoryGraphStore, Node, Edge


def make_sample_store():
    store = InMemoryGraphStore()
    n1 = Node(id="n1", node_type="A")
    n2 = Node(id="n2", node_type="B")
    store.add_node(n1)
    store.add_node(n2)
    store.add_edge(Edge(id="e1", source_id="n1", target_id="n2", edge_type="REL"))
    return store


def test_add_update_delete_and_query():
    store = make_sample_store()
    # update existing node
    assert store.update_node("n1", {"foo": "bar"})
    assert store.get_node("n1").properties["foo"] == "bar"
    # update missing returns False
    assert not store.update_node("no", {})

    # delete an edge by deleting node
    assert store.delete_node("n2")
    assert store.get_node("n2") is None
    # subsequent delete returns False
    assert not store.delete_node("n2")

    # query by type
    store = make_sample_store()
    results = store.query("A")
    assert results.records and results.records[0]["type"] == "A"
    results2 = store.query("*")
    assert len(results2.records) == 2


def test_query_and_edge_errors():
    store = InMemoryGraphStore()
    # missing source/target on edge should raise
    with pytest.raises(ValueError):
        store.add_edge(Edge(id="e2", source_id="x", target_id="y", edge_type="R"))


def test_clear_and_iterators():
    store = make_sample_store()
    assert list(store.get_all_nodes())
    assert list(store.get_all_edges())
    store.clear()
    assert list(store.get_all_nodes()) == []
    assert list(store.get_all_edges()) == []
