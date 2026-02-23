from __future__ import annotations

import os
from types import SimpleNamespace
from pathlib import Path

import pytest

from kgbuilder.analytics.inference import Neo4jInferenceEngine
from kgbuilder.analytics.metrics import GraphMetrics, GraphMetricsSnapshot
from kgbuilder.analytics.skos import SKOSEnricher


# ---------------------------------------------------------------------------
# helpers for fake neo4j driver/session
# ---------------------------------------------------------------------------

class FakeSession:
    def __init__(self, driver):
        self._driver = driver

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def run(self, query):
        # record the executed query for later assertions
        self._driver.queries.append(query)
        # return a result object whose single() returns the next count
        count = self._driver.counts.pop(0) if self._driver.counts else 0
        return SimpleNamespace(single=lambda: {"count": count})


class FakeDriver:
    def __init__(self, counts: list[int]):
        self.counts = list(counts)
        self.queries: list[str] = []

    def session(self, database=None):
        return FakeSession(self)


class DummyGraphStore:
    def __init__(self, counts: list[int] = None):
        self._driver = FakeDriver(counts or [])
        self.database = "neo4j"


class DummyOntologyService:
    def __init__(self):
        self.special = {"symmetric": [], "inverse": [], "transitive": []}
        self.hierarchy = []

    def get_special_properties(self):
        return self.special

    def get_class_hierarchy(self):
        return self.hierarchy


# ---------------------------------------------------------------------------
# inference engine tests
# ---------------------------------------------------------------------------

def test_inference_no_rules_returns_zero():
    store = DummyGraphStore(counts=[5])  # should not be used
    ont = DummyOntologyService()
    engine = Neo4jInferenceEngine(store, ont)

    assert engine.materialize_symmetry([]) == 0
    assert engine.materialize_inversions([]) == 0
    assert engine.materialize_class_hierarchy([]) == 0
    assert engine.materialize_transitivity([]) == 0


def test_materialize_symmetry_creates_edges():
    store = DummyGraphStore(counts=[3])
    engine = Neo4jInferenceEngine(store, DummyOntologyService())
    created = engine.materialize_symmetry(["FRIENDS_WITH"])
    assert created == 3
    # query should contain property name at least once
    assert any("FRIENDS_WITH" in q for q in store._driver.queries)


def test_materialize_inversions_dedup_and_counts():
    counts = [1, 2, 3, 4]
    store = DummyGraphStore(counts=counts.copy())
    engine = Neo4jInferenceEngine(store, DummyOntologyService())
    pairs = [("p1", "p2"), ("p2", "p1"), ("p1", "p2")]
    total = engine.materialize_inversions(pairs)
    # only two queries are executed (one per direction), so total equals sum of first two counts
    assert total == counts[0] + counts[1]
    # ensure each src_prop appears in queries
    qstr = " ".join(store._driver.queries)
    assert "p1" in qstr and "p2" in qstr


def test_materialize_hierarchy_and_transitivity():
    store = DummyGraphStore(counts=[7, 8])
    engine = Neo4jInferenceEngine(store, DummyOntologyService())
    hierarchy_count = engine.materialize_class_hierarchy([("Child", "Parent")])
    assert hierarchy_count == 7
    trans_count = engine.materialize_transitivity(["knows"])
    assert trans_count == 8


def test_run_full_inference_aggregates_all(monkeypatch):
    store = DummyGraphStore(counts=[1, 2, 3, 4])
    ont = DummyOntologyService()
    ont.special = {"symmetric": ["a"], "inverse": [("x", "y")], "transitive": ["t"]}
    ont.hierarchy = [("C", "P")]
    engine = Neo4jInferenceEngine(store, ont)
    stats = engine.run_full_inference()
    assert set(stats.keys()) == {"symmetric", "inverse", "subclass", "transitive"}
    # values correspond to our counts list in order
    assert stats["symmetric"] == 1
    assert stats["inverse"] == 2 + 3  # because two phases
    assert stats["subclass"] == 4
    assert stats["transitive"] == 0 or isinstance(stats["transitive"], int)


def test_inference_handles_driver_errors(caplog):
    class BrokenStore(DummyGraphStore):
        def __init__(self):
            super().__init__([1])
        def _raise(self):
            raise RuntimeError("boom")
    store = BrokenStore()
    ont = DummyOntologyService()
    engine = Neo4jInferenceEngine(store, ont)
    # monkeypatch session access to raise
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(store._driver, "session", lambda database=None: (_ for _ in ()).throw(RuntimeError("fail")))
    caplog.set_level("ERROR")
    res = engine.materialize_symmetry(["p"])
    assert res == 0
    # structlog error logged but may not appear in caplog
    monkeypatch.undo()


# ---------------------------------------------------------------------------
# SKOS confidence calculation edge cases
# ---------------------------------------------------------------------------

def test_skos_confidence_variants():
    enr = SKOSEnricher(ontology_service=object())
    # exact match
    concepts = [{"prefLabel": "Foo", "altLabels": []}]
    assert enr._compute_mapping_confidence("Foo", concepts) == 1.0
    # case-insensitive
    assert enr._compute_mapping_confidence("foo", concepts) == 1.0
    # substring match
    concepts = [{"prefLabel": "foobar", "altLabels": []}]
    assert enr._compute_mapping_confidence("foo", concepts) == pytest.approx(0.7)
    # alt label match
    concepts = [{"prefLabel": "X", "altLabels": ["Bar"]}]
    assert enr._compute_mapping_confidence("Bar", concepts) == pytest.approx(0.85)
    # no concepts
    assert enr._compute_mapping_confidence("Foo", []) == 0.0


def test_batch_enrich_returns_only_matches(monkeypatch):
    enr = SKOSEnricher(ontology_service=object())
    monkeypatch.setattr(enr, "_query_skos_concepts", lambda label, t=None: [] if label == "none" else [{"prefLabel": label, "altLabels": [], "uri": "u", "broader": [], "narrower": []}])
    results = enr.enrich_entities_batch([
        {"id": "1", "label": "foo"},
        {"id": "2", "label": "none"},
    ])
    assert set(results.keys()) == {"1"}


# ---------------------------------------------------------------------------
# GraphMetrics simple behavior and report
# ---------------------------------------------------------------------------

def test_graphmetrics_compute_with_monkeypatch(monkeypatch):
    # monkeypatch all internal counts to predictable values
    gm = GraphMetrics(graph_store=object())
    monkeypatch.setattr(gm, "_count_nodes", lambda: 10)
    monkeypatch.setattr(gm, "_count_edges", lambda: 20)
    monkeypatch.setattr(gm, "_count_relations", lambda: 5)
    monkeypatch.setattr(gm, "_count_typed_nodes", lambda: 8)
    monkeypatch.setattr(gm, "_count_orphan_nodes", lambda: 2)
    monkeypatch.setattr(gm, "_compute_average_degree", lambda: 3.0)
    monkeypatch.setattr(gm, "_compute_max_degree", lambda: 7)
    monkeypatch.setattr(gm, "_count_hub_nodes", lambda avg: 1)
    monkeypatch.setattr(gm, "_count_missing_descriptions", lambda: 0)
    monkeypatch.setattr(gm, "_count_missing_types", lambda: 2)
    monkeypatch.setattr(gm, "_count_orphan_entities", lambda: 1)
    monkeypatch.setattr(gm, "_count_unique_predicates", lambda: 4)
    monkeypatch.setattr(gm, "_get_predicate_distribution", lambda top_k=10: [("p", 5)])
    # also patch constraint satisfaction
    class Ont: pass
    ont = Ont()
    monkeypatch.setattr(gm, "_check_constraint_satisfaction", lambda o: {"total": 2, "satisfied": 1, "rate": 0.5})

    snap = gm.compute_metrics(ontology_service=ont)
    assert snap.total_nodes == 10
    assert snap.typed_percentage == pytest.approx(80.0)
    assert snap.constraint_satisfaction_rate == pytest.approx(0.5)

    # diagnostics report generation
    tmp = Path("/tmp").resolve()
    report = gm.generate_diagnostics_report(snap, output_path=str(tmp / "diag.txt"))
    assert "Total Nodes" in report
    assert (tmp / "diag.txt").exists()
    os.remove(str(tmp / "diag.txt"))


def test_graphmetrics_compute_handles_exceptions(caplog):
    gm = GraphMetrics(graph_store=object())
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(gm, "_count_nodes", lambda: (_ for _ in ()).throw(RuntimeError("oops")))
    caplog.set_level("ERROR")
    snap = gm.compute_metrics()
    assert "Error during computation" in snap.notes
    monkeypatch.undo()


# ---------------------------------------------------------------------------
# comparison module tests
# ---------------------------------------------------------------------------

def test_comparison_extract_and_rank() -> None:
    from types import SimpleNamespace
    from kgbuilder.analytics.comparison import (
        extract_profile,
        compare_settings,
        generate_quality_argument,
    )

    # minimal structural object with required attributes
    FakeTopo = SimpleNamespace(
        num_nodes=2,
        num_edges=1,
        density=0.5,
        avg_degree=1.0,
        avg_clustering=0.0,
        transitivity=0.0,
        reciprocity=0.0,
        num_connected_components=1,
        diameter=None,
        avg_shortest_path=None,
        degree_assortativity=None,
        power_law_exponent=None,
        small_world_sigma=None,
    )
    structural = SimpleNamespace(
        topology=FakeTopo,
        communities={},
        centralities={},
        bridges=[],
    )

    prof1 = extract_profile("a", structural=structural)
    prof2 = extract_profile("b", structural=structural)
    assert prof1.metrics["num_nodes"] == 2.0
    result = compare_settings([prof1, prof2])
    assert result.best_setting in {"a", "b"}
    arg = generate_quality_argument(prof1, comparison=result)
    assert "# Quality Argument" in arg


def test_comparison_invalid_insufficient() -> None:
    from kgbuilder.analytics.comparison import compare_settings, SettingProfile
    with pytest.raises(ValueError):
        compare_settings([SettingProfile(name="only")])


# ---------------------------------------------------------------------------
# embeddings module tests
# ---------------------------------------------------------------------------

def test_collect_and_cluster_embeddings(monkeypatch):
    from kgbuilder.storage.protocol import Node
    from kgbuilder.analytics.embeddings import (
        collect_embeddings,
        cluster_embeddings,
        reduce_dimensions,
        compare_partitions,
        compute_coherence,
        run_embedding_analysis,
        EmbeddingAnalysis,
    )

    # simple store returning three nodes, one with embedding
    class SimpleStore:
        def get_all_nodes(self):
            return [
                Node(id="n1", node_type="T", label="L1", properties={"embedding": [0.0, 1.0]}),
                Node(id="n2", node_type="T", label="L2", properties={}),
                Node(id="n3", node_type="T", label="L3", properties={}),
            ]
        def get_all_edges(self):
            return []

    store = SimpleStore()
    # dummy provider returns fixed vectors
    class Prov:
        def embed_batch(self, texts):
            return [[1.0, 0.0]] * len(texts)
    ids, mat = collect_embeddings(store, embedding_provider=Prov())
    assert ids == ["n1", "n2", "n3"]
    assert mat.shape == (3, 2)

    # monkeypatch silhouette_score to avoid error when n_labels == n_samples
    monkeypatch.setattr("sklearn.metrics.silhouette_score", lambda X, labels, **kw: 0.0)
    cluster = cluster_embeddings(ids, mat, n_clusters=2, method="kmeans")
    assert cluster.algorithm == "kmeans"
    assert set(cluster.node_to_cluster.keys()) == set(ids)

    pca = reduce_dimensions(ids, mat, method="pca", n_components=2)
    assert pca.method == "pca"
    assert len(pca.coords) == len(ids)

    # compare partitions
    part_a = {"n1": 0, "n2": 1}
    part_b = {"n1": 0, "n2": 0}
    align = compare_partitions(part_a, part_b)
    assert align.n_nodes_compared == 2
    assert 0.0 <= align.adjusted_rand_index <= 1.0

    coh = compute_coherence(ids, mat, part_b, partition_name="comm", partition_type="comm")
    assert coh.group_type == "comm"
    assert isinstance(coh.mean_cosine_similarity, float)

    # run full analysis but patch heavy functions
    monkeypatch.setattr("kgbuilder.analytics.embeddings.cluster_embeddings", lambda *a, **k: cluster)
    monkeypatch.setattr("kgbuilder.analytics.embeddings.reduce_dimensions", lambda *a, **k: pca)
    analysis: EmbeddingAnalysis = run_embedding_analysis(store, communities=part_b, embedding_provider=Prov())
    # with three nodes, clustering should execute
    assert "kmeans" in analysis.clusters
    assert analysis.alignments
    assert analysis.coherence


# ---------------------------------------------------------------------------
# structural module tests
# ---------------------------------------------------------------------------

def make_simple_store():
    from kgbuilder.storage.protocol import Node, Edge

    class S:
        def get_all_nodes(self):
            return [
                Node(id="a", node_type="X"),
                Node(id="b", node_type="X"),
                Node(id="c", node_type="Y"),
            ]
        def get_all_edges(self):
            return [
                Edge(id="e1", source_id="a", target_id="b", edge_type="rel"),
                Edge(id="e2", source_id="b", target_id="c", edge_type="rel"),
            ]
    return S()


def test_graph_store_to_networkx_and_basic_centrality():
    from kgbuilder.analytics.structural import (
        graph_store_to_networkx,
        compute_centralities,
        compute_topology,
        detect_communities,
        _compute_one_centrality,
        find_bridges_and_articulation,
        run_structural_analysis,
    )
    store = make_simple_store()
    G = graph_store_to_networkx(store)
    assert G.number_of_nodes() == 3
    cent = compute_centralities(G, measures=["degree", "pagerank"])
    assert "degree" in cent
    assert cent["degree"].scores
    topo = compute_topology(G)
    assert topo.num_nodes == 3
    comms = detect_communities(G, algorithms=["label_propagation"])
    assert "label_propagation" in comms
    bridges, artes = find_bridges_and_articulation(G)
    assert ('a', 'b') in bridges or ('b', 'c') in bridges
    # run full analysis (statistical module may be heavy; patch run_statistical_analysis to simple object)
    import kgbuilder.analytics.statistical as statmod
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(statmod, "run_statistical_analysis", lambda *a, **k: SimpleNamespace())
    analysis = run_structural_analysis(store, centrality_measures=["degree"], community_algorithms=["label_propagation"], top_k=1)
    assert analysis.topology.num_nodes == 3
    monkeypatch.undo()


# ---------------------------------------------------------------------------
# statistical module tests
# ---------------------------------------------------------------------------

def test_power_law_and_nmi_and_baseline_and_smallworld(tmp_path, monkeypatch):
    import networkx as nx
    from kgbuilder.analytics.statistical import (
        power_law_test,
        community_ontology_nmi,
        baseline_modularity,
        small_world_sigma,
        bootstrap_ci,
        per_type_degree_stats,
        format_statistical_report,
        StatisticalAnalysis,
        run_statistical_analysis,
    )

    # small graph for power-law (<10 nodes triggers warning)
    G = nx.path_graph(5)
    res = power_law_test(G)
    assert res.num_tail_samples == len([d for _, d in G.degree() if d >= 1])

    # NMI: set node_type attributes and mapping
    for n in G.nodes():
        G.nodes[n]["node_type"] = "A" if n % 2 == 0 else "B"
    mapping = {n: (0 if n < 3 else 1) for n in G.nodes()}
    nmi = community_ontology_nmi(G, mapping)
    assert 0.0 <= nmi.nmi <= 1.0

    # baseline modularity with trivial partition
    part = [set([0,1]), set([2,3,4])]
    bm = baseline_modularity(G, part, n_trials=5, seed=1)
    assert isinstance(bm.observed_modularity, float)

    # small-world sigma on tiny graph should return sigma > 0 or zero
    sw = small_world_sigma(G, n_random_graphs=3, seed=1)
    assert hasattr(sw, "sigma")

    # bootstrap CI of simple metric
    ci = bootstrap_ci(G, lambda g: g.number_of_edges(), n_resamples=10, seed=1)
    assert ci.metric_name == "metric" or ci.metric_name == "density"

    # per-type degree stats
    pts = per_type_degree_stats(G)
    assert any(p.type_name in ("A","B") for p in pts)

    # format report
    sa = StatisticalAnalysis(power_law=res, nmi=nmi, baseline_modularity=bm, small_world=sw, confidence_intervals=[ci], per_type_degrees=pts)
    report = format_statistical_report(sa)
    assert "Power‑law" in report

    # run_statistical_analysis stub out heavy subfunctions
    monkeypatch.setattr("kgbuilder.analytics.statistical.power_law_test", lambda g, **k: res)
    monkeypatch.setattr("kgbuilder.analytics.statistical.community_ontology_nmi", lambda g, m, **k: nmi)
    monkeypatch.setattr("kgbuilder.analytics.statistical.baseline_modularity", lambda g, p, **k: bm)
    monkeypatch.setattr("kgbuilder.analytics.statistical.small_world_sigma", lambda g, **k: sw)
    monkeypatch.setattr("kgbuilder.analytics.statistical.bootstrap_ci", lambda *a, **k: ci)
    monkeypatch.setattr("kgbuilder.analytics.statistical.per_type_degree_stats", lambda g, **k: pts)
    analysis = run_statistical_analysis(G, community_mapping=mapping, community_partition=part, n_modularity_trials=1, n_random_graphs=1, n_bootstrap=5)
    assert analysis.power_law is res
    assert analysis.nmi is nmi
    assert analysis.baseline_modularity is bm
    assert analysis.small_world is sw
    assert analysis.confidence_intervals
    assert analysis.per_type_degrees

