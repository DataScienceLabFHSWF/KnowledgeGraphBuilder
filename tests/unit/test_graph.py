import pytest

from kgbuilder.storage import graph
from kgbuilder.storage.graph import Neo4jStore, GraphStore
from kgbuilder.core.models import ExtractedEntity, ExtractedRelation


class DummySession:
    def __init__(self):
        self.calls = []
        # optional value that run() should return when set
        self.next_result = None

    def run(self, *args, **kwargs):
        # Accept either run(cypher, params) or run(cypher, **params)
        if len(args) >= 2 and isinstance(args[1], dict):
            cypher = args[0]
            params = args[1]
        else:
            cypher = args[0]
            params = kwargs

        # record stripped cypher and params dictionary
        self.calls.append((cypher.strip(), params))
        # if caller prepared a result object, return it
        if self.next_result is not None:
            val = self.next_result
            self.next_result = None
            return val

        # default result object supporting consume and iteration
        class R:
            def __iter__(self_inner):
                return iter([])

            def consume(self_inner):
                return None

        return R()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass


class DummyDriver:
    def __init__(self, session):
        self._session = session

    def session(self, database=None):
        return self._session

    def close(self):
        pass


@pytest.fixture(autouse=True)
def fake_neo4j(monkeypatch):
    """Patch the neo4j driver factory to return our dummy driver.

    The real GraphDatabase class is imported inside the module under test,
    so patching the outer package path fails. Instead we modify the
    `neo4j.GraphDatabase.driver` attribute directly.
    """
    sess = DummySession()
    monkeypatch.setattr(
        "neo4j.GraphDatabase.driver",
        lambda uri, auth=None: DummyDriver(sess),
        raising=False,
    )
    return sess


def test_neo4jstore_implements_protocol():
    # basic isinstance check against Protocol
    store = Neo4jStore(uri="bolt://x")
    assert isinstance(store, GraphStore)


def test_add_node_and_edge(fake_neo4j):
    store = Neo4jStore(uri="bolt://x")
    # call methods
    store.add_node("n1", "Label", {"a": 1})
    store.add_edge("n1", "n2", "REL", {"p": 3})

    # ensure at least three calls recorded (ping + maybe constraints + our ops)
    assert len(fake_neo4j.calls) >= 3
    # last two calls correspond to our add_node and add_edge operations
    cy, params = fake_neo4j.calls[-2]
    assert "MERGE (n:Label" in cy
    assert params["node_id"] == "n1"
    cy2, params2 = fake_neo4j.calls[-1]
    assert "MERGE (source)-[r:REL]" in cy2
    assert params2["source_id"] == "n1"


def test_query_returns_list(fake_neo4j):
    store = Neo4jStore(uri="bolt://x")
    # prepare a result object that yields one record
    class Rec:
        def __iter__(self):
            yield {"x": 1}

    fake_neo4j.next_result = Rec()
    result = store.query("MATCH (n) RETURN n")
    assert isinstance(result, list)
    assert result == [{"x": 1}]
    # call recorded
    assert fake_neo4j.calls[-1][0].startswith("MATCH (n)")


def test_add_entities_and_relations(fake_neo4j):
    store = Neo4jStore(uri="bolt://x")
    ent = ExtractedEntity(id="e1", label="L", entity_type="T", description="d", confidence=0.1)
    store.add_entities([ent])
    # entity added via add_node
    assert any("MERGE (n:Entity" in call[0] for call in fake_neo4j.calls)

    rel = ExtractedRelation(id="r1", source_entity_id="e1", target_entity_id="e2", predicate="pred")
    store.add_relations([rel])
    assert any("MERGE (source)-[r:pred]" in call[0] for call in fake_neo4j.calls)


def test_create_constraints_calls_methods(fake_neo4j):
    store = Neo4jStore(uri="bolt://x")
    # clear previous calls and call create_constraints explicitly
    fake_neo4j.calls.clear()
    store.create_constraints()
    assert len(fake_neo4j.calls) >= 2
    assert "CREATE CONSTRAINT" in fake_neo4j.calls[0][0]
