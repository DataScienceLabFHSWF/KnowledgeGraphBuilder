"""Tests for KG analytics: structural, embeddings, comparison, and plots.

Uses InMemoryGraphStore with a synthetic knowledge graph that has clear
community structure so we can validate community detection, centrality
rankings, and the full analysis pipelines.
"""

from __future__ import annotations

import numpy as np
import pytest

from kgbuilder.storage.protocol import Edge, InMemoryGraphStore, Node


# ============================================================================
# Fixtures — synthetic KG with 2 communities
# ============================================================================


def _build_two_community_graph() -> InMemoryGraphStore:
    """Build a small graph with 2 clear communities + 1 bridge node.

    Community A (Person): alice, bob, carol (triangle)
    Community B (Org): acme, beta, gamma (triangle)
    Bridge: alice → acme (cross-community edge)
    """
    store = InMemoryGraphStore()

    # Community A — Person triangle
    for nid in ["alice", "bob", "carol"]:
        store.add_node(Node(id=nid, node_type="Person", label=nid.capitalize()))

    store.add_edge(Edge(id="e1", source_id="alice", target_id="bob", edge_type="knows"))
    store.add_edge(Edge(id="e2", source_id="bob", target_id="carol", edge_type="knows"))
    store.add_edge(Edge(id="e3", source_id="carol", target_id="alice", edge_type="knows"))

    # Community B — Org triangle
    for nid in ["acme", "beta", "gamma"]:
        store.add_node(Node(id=nid, node_type="Organization", label=nid.capitalize()))

    store.add_edge(Edge(id="e4", source_id="acme", target_id="beta", edge_type="partner"))
    store.add_edge(Edge(id="e5", source_id="beta", target_id="gamma", edge_type="partner"))
    store.add_edge(Edge(id="e6", source_id="gamma", target_id="acme", edge_type="partner"))

    # Bridge
    store.add_edge(Edge(id="e7", source_id="alice", target_id="acme", edge_type="works_at"))

    return store


@pytest.fixture
def two_community_store() -> InMemoryGraphStore:
    """InMemoryGraphStore with 6 nodes, 7 edges, 2 communities."""
    return _build_two_community_graph()


@pytest.fixture
def larger_store() -> InMemoryGraphStore:
    """A slightly larger graph (15 nodes, ~30 edges) for richer analytics."""
    store = InMemoryGraphStore()

    # 3 clusters of 5 nodes each
    for cluster_idx in range(3):
        prefix = f"c{cluster_idx}"
        node_type = ["Person", "Organization", "Concept"][cluster_idx]
        for i in range(5):
            nid = f"{prefix}_n{i}"
            store.add_node(Node(id=nid, node_type=node_type, label=f"Node {nid}"))

        # Fully connect within cluster
        edge_count = 0
        for i in range(5):
            for j in range(i + 1, 5):
                eid = f"{prefix}_e{edge_count}"
                store.add_edge(Edge(
                    id=eid,
                    source_id=f"{prefix}_n{i}",
                    target_id=f"{prefix}_n{j}",
                    edge_type="related",
                ))
                edge_count += 1

    # Inter-cluster bridges
    store.add_edge(Edge(
        id="bridge_01", source_id="c0_n0", target_id="c1_n0", edge_type="bridge",
    ))
    store.add_edge(Edge(
        id="bridge_12", source_id="c1_n0", target_id="c2_n0", edge_type="bridge",
    ))

    return store


# ============================================================================
# Tests — structural.py
# ============================================================================


class TestGraphStoreToNetworkx:
    """Test conversion from InMemoryGraphStore to NetworkX."""

    def test_converts_nodes_and_edges(self, two_community_store: InMemoryGraphStore) -> None:
        from kgbuilder.analytics.structural import graph_store_to_networkx

        G = graph_store_to_networkx(two_community_store)
        assert G.number_of_nodes() == 6
        assert G.number_of_edges() == 7

    def test_preserves_node_type(self, two_community_store: InMemoryGraphStore) -> None:
        from kgbuilder.analytics.structural import graph_store_to_networkx

        G = graph_store_to_networkx(two_community_store)
        assert G.nodes["alice"]["node_type"] == "Person"
        assert G.nodes["acme"]["node_type"] == "Organization"

    def test_preserves_edge_type(self, two_community_store: InMemoryGraphStore) -> None:
        from kgbuilder.analytics.structural import graph_store_to_networkx

        G = graph_store_to_networkx(two_community_store)
        edge_data = G.get_edge_data("alice", "acme")
        assert edge_data is not None
        # MultiDiGraph returns {key: {attrs}} — check first edge
        first_edge = next(iter(edge_data.values()))
        assert first_edge["edge_type"] == "works_at"


class TestComputeCentralities:
    """Test centrality computation."""

    def test_returns_all_requested_measures(
        self, two_community_store: InMemoryGraphStore
    ) -> None:
        from kgbuilder.analytics.structural import (
            compute_centralities,
            graph_store_to_networkx,
        )

        G = graph_store_to_networkx(two_community_store)
        measures = ["degree", "pagerank", "betweenness"]
        result = compute_centralities(G, measures=measures)

        assert set(result.keys()) == set(measures)

    def test_top_k_ordering(self, two_community_store: InMemoryGraphStore) -> None:
        from kgbuilder.analytics.structural import (
            compute_centralities,
            graph_store_to_networkx,
        )

        G = graph_store_to_networkx(two_community_store)
        result = compute_centralities(G, measures=["degree"], top_k=3)
        top = result["degree"].top_k
        # Should be sorted descending
        values = [v for _, v in top]
        assert values == sorted(values, reverse=True)

    def test_alice_highest_degree(self, two_community_store: InMemoryGraphStore) -> None:
        """Alice has 3 outgoing edges (bob, carol, acme) so should rank top."""
        from kgbuilder.analytics.structural import (
            compute_centralities,
            graph_store_to_networkx,
        )

        G = graph_store_to_networkx(two_community_store)
        result = compute_centralities(G, measures=["out_degree"], top_k=1)
        top_node = result["out_degree"].top_k[0][0]
        assert top_node == "alice"

    def test_gini_and_stats(self, two_community_store: InMemoryGraphStore) -> None:
        from kgbuilder.analytics.structural import (
            compute_centralities,
            graph_store_to_networkx,
        )

        G = graph_store_to_networkx(two_community_store)
        result = compute_centralities(G, measures=["pagerank"])
        pr = result["pagerank"]
        assert 0.0 <= pr.gini <= 1.0
        assert pr.mean > 0
        assert pr.std >= 0


class TestDetectCommunities:
    """Test community detection algorithms."""

    def test_louvain_detects_two_communities(
        self, two_community_store: InMemoryGraphStore
    ) -> None:
        from kgbuilder.analytics.structural import (
            detect_communities,
            graph_store_to_networkx,
        )

        G = graph_store_to_networkx(two_community_store)
        result = detect_communities(G, algorithms=["louvain"])
        assert "louvain" in result
        comm = result["louvain"]
        assert comm.num_communities >= 2

    def test_modularity_positive(self, two_community_store: InMemoryGraphStore) -> None:
        from kgbuilder.analytics.structural import (
            detect_communities,
            graph_store_to_networkx,
        )

        G = graph_store_to_networkx(two_community_store)
        result = detect_communities(G, algorithms=["louvain"])
        assert result["louvain"].modularity > 0

    def test_all_nodes_assigned(self, two_community_store: InMemoryGraphStore) -> None:
        from kgbuilder.analytics.structural import (
            detect_communities,
            graph_store_to_networkx,
        )

        G = graph_store_to_networkx(two_community_store)
        result = detect_communities(G, algorithms=["louvain"])
        assigned = set(result["louvain"].node_to_community.keys())
        assert assigned == set(G.nodes())


class TestComputeTopology:
    """Test topology metrics."""

    def test_basic_topology_metrics(self, two_community_store: InMemoryGraphStore) -> None:
        from kgbuilder.analytics.structural import (
            compute_topology,
            graph_store_to_networkx,
        )

        G = graph_store_to_networkx(two_community_store)
        topo = compute_topology(G)

        assert topo.num_nodes == 6
        assert topo.num_edges == 7
        assert 0.0 <= topo.density <= 1.0
        assert topo.num_connected_components >= 1
        assert 0.0 <= topo.avg_clustering <= 1.0
        assert topo.avg_degree > 0

    def test_degree_distribution(self, two_community_store: InMemoryGraphStore) -> None:
        from kgbuilder.analytics.structural import (
            compute_topology,
            graph_store_to_networkx,
        )

        G = graph_store_to_networkx(two_community_store)
        topo = compute_topology(G)

        assert len(topo.degree_distribution) > 0
        total = sum(topo.degree_distribution.values())
        assert total == 6  # one entry per node


class TestRunStructuralAnalysis:
    """Integration test for the full structural pipeline."""

    def test_returns_structural_analysis(
        self, two_community_store: InMemoryGraphStore
    ) -> None:
        from kgbuilder.analytics.structural import run_structural_analysis

        result = run_structural_analysis(
            two_community_store,
            centrality_measures=["degree", "pagerank"],
            community_algorithms=["louvain"],
        )
        assert result.topology.num_nodes == 6
        assert "degree" in result.centralities
        assert "pagerank" in result.centralities
        assert "louvain" in result.communities

    def test_larger_graph(self, larger_store: InMemoryGraphStore) -> None:
        from kgbuilder.analytics.structural import run_structural_analysis

        result = run_structural_analysis(larger_store)
        assert result.topology.num_nodes == 15
        assert result.topology.num_edges == 32
        assert "louvain" in result.communities
        # Should find roughly 3 communities
        assert result.communities["louvain"].num_communities >= 2


# ============================================================================
# Tests — embeddings.py
# ============================================================================


def _make_store_with_embeddings() -> tuple[InMemoryGraphStore, dict[str, list[float]]]:
    """Build a small store where we inject synthetic embeddings.

    Two clusters in embedding space:
    - a1, a2, a3: near [1, 0, 0]
    - b1, b2, b3: near [0, 1, 0]
    """
    store = InMemoryGraphStore()
    rng = np.random.RandomState(42)

    embeddings: dict[str, list[float]] = {}
    for nid in ["a1", "a2", "a3"]:
        emb = [1.0, 0.0, 0.0] + rng.normal(0, 0.05, 3).tolist()
        store.add_node(Node(
            id=nid, node_type="TypeA", label=nid,
            properties={"embedding": emb},
        ))
        embeddings[nid] = emb

    for nid in ["b1", "b2", "b3"]:
        emb = [0.0, 1.0, 0.0] + rng.normal(0, 0.05, 3).tolist()
        store.add_node(Node(
            id=nid, node_type="TypeB", label=nid,
            properties={"embedding": emb},
        ))
        embeddings[nid] = emb

    # Edges within clusters
    store.add_edge(Edge(id="ea1", source_id="a1", target_id="a2", edge_type="r"))
    store.add_edge(Edge(id="ea2", source_id="a2", target_id="a3", edge_type="r"))
    store.add_edge(Edge(id="eb1", source_id="b1", target_id="b2", edge_type="r"))
    store.add_edge(Edge(id="eb2", source_id="b2", target_id="b3", edge_type="r"))
    # Bridge
    store.add_edge(Edge(id="eab", source_id="a1", target_id="b1", edge_type="bridge"))

    return store, embeddings


class TestCollectEmbeddings:
    """Test embedding collection from store properties."""

    def test_collects_from_properties(self) -> None:
        from kgbuilder.analytics.embeddings import collect_embeddings

        store, _ = _make_store_with_embeddings()
        node_ids, matrix = collect_embeddings(store, embedding_key="embedding")

        assert len(node_ids) == 6
        assert matrix.shape == (6, 6)  # 6 nodes × 6-dim embeddings


class TestClusterEmbeddings:
    """Test embedding clustering."""

    def test_kmeans_finds_two_clusters(self) -> None:
        from kgbuilder.analytics.embeddings import cluster_embeddings

        store, _ = _make_store_with_embeddings()
        from kgbuilder.analytics.embeddings import collect_embeddings

        node_ids, matrix = collect_embeddings(store, embedding_key="embedding")
        result = cluster_embeddings(node_ids, matrix, n_clusters=2, method="kmeans")

        assert result.algorithm == "kmeans"
        assert len(set(result.node_to_cluster.values())) == 2
        # Silhouette should be reasonably high for well-separated clusters
        assert result.silhouette_score is not None
        assert result.silhouette_score > 0.3


class TestReduceDimensions:
    """Test dimensionality reduction."""

    def test_pca_returns_2d(self) -> None:
        from kgbuilder.analytics.embeddings import collect_embeddings, reduce_dimensions

        store, _ = _make_store_with_embeddings()
        node_ids, matrix = collect_embeddings(store, embedding_key="embedding")
        reduction = reduce_dimensions(node_ids, matrix, method="pca", n_components=2)

        assert reduction.method == "pca"
        assert reduction.coords.shape == (6, 2)
        assert len(reduction.node_ids) == 6
        assert reduction.explained_variance_ratio is not None
        assert len(reduction.explained_variance_ratio) == 2


class TestComparePartitions:
    """Test partition alignment metrics."""

    def test_identical_partitions_perfect_score(self) -> None:
        from kgbuilder.analytics.embeddings import compare_partitions

        partition = {"a": 0, "b": 0, "c": 1, "d": 1}
        result = compare_partitions(partition, partition)

        assert result.adjusted_rand_index == pytest.approx(1.0)
        assert result.normalized_mutual_info == pytest.approx(1.0)

    def test_different_partitions_lower_score(self) -> None:
        from kgbuilder.analytics.embeddings import compare_partitions

        part_a = {"a": 0, "b": 0, "c": 1, "d": 1}
        part_b = {"a": 0, "b": 1, "c": 0, "d": 1}
        result = compare_partitions(part_a, part_b)

        assert result.adjusted_rand_index < 1.0


class TestComputeCoherence:
    """Test intra-group cosine similarity."""

    def test_coherence_high_for_tight_clusters(self) -> None:
        from kgbuilder.analytics.embeddings import collect_embeddings, compute_coherence

        store, _ = _make_store_with_embeddings()
        node_ids, matrix = collect_embeddings(store, embedding_key="embedding")

        # Assign a1,a2,a3 → 0 and b1,b2,b3 → 1
        partition = {}
        for nid in node_ids:
            partition[nid] = 0 if nid.startswith("a") else 1

        coh = compute_coherence(node_ids, matrix, partition)
        assert coh.mean_cosine_similarity > 0.7


class TestRunEmbeddingAnalysis:
    """Integration test for the embedding analysis pipeline."""

    def test_full_pipeline(self) -> None:
        from kgbuilder.analytics.embeddings import run_embedding_analysis

        store, _ = _make_store_with_embeddings()
        communities = {"a1": 0, "a2": 0, "a3": 0, "b1": 1, "b2": 1, "b3": 1}

        result = run_embedding_analysis(
            store,
            communities=communities,
            embedding_key="embedding",
            n_clusters=2,
            reduction_methods=["pca"],
        )

        assert "kmeans" in result.clusters
        assert "pca" in result.reductions
        assert len(result.alignments) > 0
        assert result.embedding_matrix.shape[0] == 6


# ============================================================================
# Tests — comparison.py
# ============================================================================


class TestExtractProfile:
    """Test metric extraction from analysis results."""

    def test_extracts_structural_metrics(
        self, two_community_store: InMemoryGraphStore
    ) -> None:
        from kgbuilder.analytics.comparison import extract_profile
        from kgbuilder.analytics.structural import run_structural_analysis

        structural = run_structural_analysis(
            two_community_store,
            centrality_measures=["pagerank"],
            community_algorithms=["louvain"],
        )
        profile = extract_profile("test", structural=structural)

        assert profile.name == "test"
        assert profile.metrics["num_nodes"] == 6.0
        assert profile.metrics["num_edges"] == 7.0
        assert "density" in profile.metrics
        assert "modularity" in profile.metrics


class TestCompareSettings:
    """Test cross-setting comparison."""

    def test_requires_at_least_two_profiles(self) -> None:
        from kgbuilder.analytics.comparison import SettingProfile, compare_settings

        with pytest.raises(ValueError, match="at least 2"):
            compare_settings([SettingProfile(name="only_one")])

    def test_comparison_produces_ranking(self) -> None:
        from kgbuilder.analytics.comparison import SettingProfile, compare_settings

        p1 = SettingProfile(
            name="setting_A",
            metrics={"modularity": 0.6, "density": 0.05, "avg_clustering": 0.7},
        )
        p2 = SettingProfile(
            name="setting_B",
            metrics={"modularity": 0.3, "density": 0.02, "avg_clustering": 0.4},
        )
        result = compare_settings([p1, p2])

        assert result.best_setting in ["setting_A", "setting_B"]
        assert len(result.composite_scores) == 2
        assert result.composite_scores["setting_A"] >= result.composite_scores["setting_B"]


class TestGenerateQualityArgument:
    """Test quality argument generation."""

    def test_generates_markdown(self) -> None:
        from kgbuilder.analytics.comparison import SettingProfile, generate_quality_argument

        profile = SettingProfile(
            name="baseline",
            description="Default pipeline settings",
            metrics={
                "num_nodes": 100,
                "num_edges": 300,
                "density": 0.03,
                "avg_degree": 6.0,
                "modularity": 0.55,
                "power_law_exponent": 2.5,
                "avg_clustering": 0.4,
                "transitivity": 0.3,
                "num_connected_components": 1,
            },
        )
        text = generate_quality_argument(profile)

        assert "# Quality Argument: baseline" in text
        assert "scale-free" in text.lower() or "Power-law" in text
        assert "Modularity" in text or "modularity" in text


# ============================================================================
# Tests — plots.py
# ============================================================================


class TestPlots:
    """Test that plot functions run without errors and return Figure objects.

    We don't assert pixel-level correctness — just that they produce
    valid figures and don't crash on real data.
    """

    @pytest.fixture(autouse=True)
    def _setup_matplotlib(self) -> None:
        """Ensure matplotlib is in non-interactive mode."""
        import matplotlib
        matplotlib.use("Agg")

    def test_plot_degree_distribution(
        self, two_community_store: InMemoryGraphStore
    ) -> None:
        from kgbuilder.analytics.plots import plot_degree_distribution
        from kgbuilder.analytics.structural import (
            compute_topology,
            graph_store_to_networkx,
        )

        G = graph_store_to_networkx(two_community_store)
        topo = compute_topology(G)
        fig = plot_degree_distribution(topo)
        assert fig is not None
        import matplotlib.pyplot as plt
        plt.close(fig)

    def test_plot_centrality_topk(
        self, two_community_store: InMemoryGraphStore
    ) -> None:
        from kgbuilder.analytics.plots import plot_centrality_topk
        from kgbuilder.analytics.structural import (
            compute_centralities,
            graph_store_to_networkx,
        )

        G = graph_store_to_networkx(two_community_store)
        cents = compute_centralities(G, measures=["pagerank", "betweenness"])
        fig = plot_centrality_topk(cents)
        assert fig is not None
        import matplotlib.pyplot as plt
        plt.close(fig)

    def test_plot_centrality_correlation(
        self, two_community_store: InMemoryGraphStore
    ) -> None:
        from kgbuilder.analytics.plots import plot_centrality_correlation
        from kgbuilder.analytics.structural import (
            compute_centralities,
            graph_store_to_networkx,
        )

        G = graph_store_to_networkx(two_community_store)
        cents = compute_centralities(G, measures=["pagerank", "betweenness", "degree"])
        fig = plot_centrality_correlation(cents)
        assert fig is not None
        import matplotlib.pyplot as plt
        plt.close(fig)

    def test_plot_community_sizes(
        self, two_community_store: InMemoryGraphStore
    ) -> None:
        from kgbuilder.analytics.plots import plot_community_sizes
        from kgbuilder.analytics.structural import (
            detect_communities,
            graph_store_to_networkx,
        )

        G = graph_store_to_networkx(two_community_store)
        comms = detect_communities(G, algorithms=["louvain"])
        fig = plot_community_sizes(comms)
        assert fig is not None
        import matplotlib.pyplot as plt
        plt.close(fig)

    def test_plot_graph_layout(
        self, two_community_store: InMemoryGraphStore
    ) -> None:
        from kgbuilder.analytics.plots import plot_graph_layout

        fig = plot_graph_layout(two_community_store)
        assert fig is not None
        import matplotlib.pyplot as plt
        plt.close(fig)

    def test_plot_embedding_scatter(self) -> None:
        from kgbuilder.analytics.embeddings import collect_embeddings, reduce_dimensions
        from kgbuilder.analytics.plots import plot_embedding_scatter

        store, _ = _make_store_with_embeddings()
        node_ids, matrix = collect_embeddings(store, embedding_key="embedding")
        reduction = reduce_dimensions(node_ids, matrix, method="pca", n_components=2)

        partition = {nid: 0 if nid.startswith("a") else 1 for nid in node_ids}
        fig = plot_embedding_scatter(reduction, partition=partition)
        assert fig is not None
        import matplotlib.pyplot as plt
        plt.close(fig)

    def test_plot_radar_comparison(self) -> None:
        from kgbuilder.analytics.plots import plot_radar_comparison

        settings = {
            "A": {"modularity": 0.5, "density": 0.03, "clustering": 0.4},
            "B": {"modularity": 0.3, "density": 0.06, "clustering": 0.6},
        }
        fig = plot_radar_comparison(settings)
        assert fig is not None
        import matplotlib.pyplot as plt
        plt.close(fig)

    def test_plot_analytics_dashboard(
        self, two_community_store: InMemoryGraphStore
    ) -> None:
        from kgbuilder.analytics.plots import plot_analytics_dashboard
        from kgbuilder.analytics.structural import run_structural_analysis

        structural = run_structural_analysis(
            two_community_store,
            centrality_measures=["pagerank"],
            community_algorithms=["louvain"],
        )
        fig = plot_analytics_dashboard(structural)
        assert fig is not None
        import matplotlib.pyplot as plt
        plt.close(fig)


# ============================================================================
# Tests — GraphSAGE (DeepWalk fallback only, no PyG needed)
# ============================================================================


class TestGraphSAGE:
    """Test GraphSAGE / DeepWalk training and comparison."""

    def test_deepwalk_produces_embeddings(
        self, two_community_store: InMemoryGraphStore
    ) -> None:
        from kgbuilder.analytics.graphsage import train_graphsage

        node_ids, structural, losses = train_graphsage(
            two_community_store,
            output_dim=8,
            epochs=5,
        )
        assert len(node_ids) == 6
        # dim = min(output_dim, n-1) = min(8, 5) = 5 for DeepWalk fallback
        assert structural.shape[0] == 6
        assert structural.shape[1] <= 8
        assert isinstance(losses, list)

    def test_compare_embeddings(self, two_community_store: InMemoryGraphStore) -> None:
        from kgbuilder.analytics.graphsage import compare_embeddings, train_graphsage

        node_ids, structural, _ = train_graphsage(
            two_community_store,
            output_dim=8,
            epochs=5,
        )
        # Synthetic semantic embeddings
        rng = np.random.RandomState(99)
        semantic = rng.randn(len(node_ids), 12).astype(np.float32)

        result = compare_embeddings(
            node_ids_structural=node_ids,
            structural_matrix=structural,
            node_ids_semantic=node_ids,
            semantic_matrix=semantic,
        )
        assert len(result.cosine_similarities) == 6
        assert result.procrustes_disparity is not None
        assert result.procrustes_disparity >= 0
        assert result.fused_embeddings.shape[0] == 6

    def test_run_graphsage_analysis(
        self, two_community_store: InMemoryGraphStore
    ) -> None:
        from kgbuilder.analytics.graphsage import run_graphsage_analysis

        rng = np.random.RandomState(42)
        node_ids = ["alice", "bob", "carol", "acme", "beta", "gamma"]
        semantic = rng.randn(6, 10).astype(np.float32)

        result = run_graphsage_analysis(
            two_community_store,
            semantic_node_ids=node_ids,
            semantic_matrix=semantic,
            output_dim=8,
            epochs=5,
        )
        assert result.structural_embeddings.shape[0] == 6
        assert len(result.cosine_similarities) == 6
