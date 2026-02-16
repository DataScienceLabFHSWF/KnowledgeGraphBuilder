"""Tests for statistical rigor metrics (Phase 1).

Tests power-law KS test, NMI, baseline modularity, small-world σ,
bootstrap CIs, and per-type degree stats using synthetic graphs with
known properties.
"""

from __future__ import annotations

import numpy as np
import pytest

from kgbuilder.storage.protocol import Edge, InMemoryGraphStore, Node


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def two_type_graph():
    """NetworkX graph with 2 node types and clear community structure.

    Type A nodes (6): fully connected among themselves
    Type B nodes (6): fully connected among themselves
    Bridge: 1 edge between type A and type B
    """
    import networkx as nx

    G = nx.Graph()
    # Type A cluster
    for i in range(6):
        G.add_node(f"a{i}", node_type="Paragraf")
    for i in range(6):
        for j in range(i + 1, 6):
            G.add_edge(f"a{i}", f"a{j}")

    # Type B cluster
    for i in range(6):
        G.add_node(f"b{i}", node_type="Facility")
    for i in range(6):
        for j in range(i + 1, 6):
            G.add_edge(f"b{i}", f"b{j}")

    # One bridge
    G.add_edge("a0", "b0")
    return G


@pytest.fixture
def power_law_graph():
    """Barabási–Albert graph (should follow power-law degree distribution)."""
    import networkx as nx

    G = nx.barabasi_albert_graph(200, 2, seed=42)
    for n in G.nodes():
        G.nodes[n]["node_type"] = "Entity"
    return G


@pytest.fixture
def small_graph():
    """Tiny graph for edge cases."""
    import networkx as nx

    G = nx.Graph()
    G.add_node("x", node_type="A")
    G.add_node("y", node_type="B")
    G.add_edge("x", "y")
    return G


@pytest.fixture
def two_community_store() -> InMemoryGraphStore:
    """InMemory store with 6 nodes, 7 edges, 2 communities."""
    store = InMemoryGraphStore()
    for nid in ["alice", "bob", "carol"]:
        store.add_node(Node(id=nid, node_type="Person", label=nid.capitalize()))
    store.add_edge(Edge(id="e1", source_id="alice", target_id="bob", edge_type="knows"))
    store.add_edge(Edge(id="e2", source_id="bob", target_id="carol", edge_type="knows"))
    store.add_edge(Edge(id="e3", source_id="carol", target_id="alice", edge_type="knows"))
    for nid in ["acme", "beta", "gamma"]:
        store.add_node(Node(id=nid, node_type="Organization", label=nid.capitalize()))
    store.add_edge(Edge(id="e4", source_id="acme", target_id="beta", edge_type="partner"))
    store.add_edge(Edge(id="e5", source_id="beta", target_id="gamma", edge_type="partner"))
    store.add_edge(Edge(id="e6", source_id="gamma", target_id="acme", edge_type="partner"))
    store.add_edge(Edge(id="e7", source_id="alice", target_id="acme", edge_type="works_at"))
    return store


# ============================================================================
# Tests — power_law_test
# ============================================================================


class TestPowerLawTest:
    """Test KS goodness-of-fit for power-law distributions."""

    def test_barabasi_albert_returns_result(self, power_law_graph) -> None:
        from kgbuilder.analytics.statistical import power_law_test

        result = power_law_test(power_law_graph)
        assert result.alpha > 1.0
        assert result.xmin >= 1
        assert result.num_tail_samples > 0
        assert result.ks_statistic >= 0

    def test_ba_graph_has_reasonable_alpha(self, power_law_graph) -> None:
        from kgbuilder.analytics.statistical import power_law_test

        result = power_law_test(power_law_graph)
        # BA graphs typically have alpha in [2, 3]
        assert 1.5 <= result.alpha <= 5.0

    def test_small_graph_returns_empty(self, small_graph) -> None:
        from kgbuilder.analytics.statistical import power_law_test

        result = power_law_test(small_graph)
        assert result.num_tail_samples <= 10

    def test_lognormal_comparison_populated(self, power_law_graph) -> None:
        from kgbuilder.analytics.statistical import power_law_test

        result = power_law_test(power_law_graph)
        # R and p should be finite numbers
        assert np.isfinite(result.comparison_lognormal_R)
        assert np.isfinite(result.comparison_lognormal_p)


# ============================================================================
# Tests — community_ontology_nmi
# ============================================================================


class TestCommunityOntologyNMI:
    """Test NMI between community partition and node types."""

    def test_perfect_alignment(self, two_type_graph) -> None:
        """If communities exactly match types, NMI should be 1.0."""
        from kgbuilder.analytics.statistical import community_ontology_nmi

        # Create mapping that matches types perfectly
        mapping = {}
        for n in two_type_graph.nodes():
            mapping[n] = 0 if n.startswith("a") else 1

        result = community_ontology_nmi(two_type_graph, mapping)
        assert result.nmi == pytest.approx(1.0, abs=0.01)
        assert result.num_communities == 2
        assert result.num_types == 2

    def test_random_assignment_low_nmi(self, two_type_graph) -> None:
        """Random community assignment should yield lower NMI."""
        from kgbuilder.analytics.statistical import community_ontology_nmi

        rng = np.random.RandomState(42)
        mapping = {n: rng.randint(0, 4) for n in two_type_graph.nodes()}
        result = community_ontology_nmi(two_type_graph, mapping)
        # Should be less than perfect alignment
        assert result.nmi < 0.9

    def test_contingency_table_populated(self, two_type_graph) -> None:
        from kgbuilder.analytics.statistical import community_ontology_nmi

        mapping = {n: 0 if n.startswith("a") else 1 for n in two_type_graph.nodes()}
        result = community_ontology_nmi(two_type_graph, mapping)
        assert "Paragraf" in result.contingency_table
        assert "Facility" in result.contingency_table

    def test_empty_mapping_returns_zero(self, two_type_graph) -> None:
        from kgbuilder.analytics.statistical import community_ontology_nmi

        result = community_ontology_nmi(two_type_graph, {})
        assert result.nmi == 0.0


# ============================================================================
# Tests — baseline_modularity
# ============================================================================


class TestBaselineModularity:
    """Test modularity comparison against configuration model."""

    def test_structured_graph_beats_random(self, two_type_graph) -> None:
        """A graph with clear communities should significantly beat random."""
        from kgbuilder.analytics.statistical import baseline_modularity

        partition = [
            {f"a{i}" for i in range(6)},
            {f"b{i}" for i in range(6)},
        ]

        result = baseline_modularity(
            two_type_graph, partition, n_trials=30, seed=42
        )
        assert result.observed_modularity > 0
        assert result.z_score > 0  # should be above random
        assert result.n_trials >= 20

    def test_reports_significance(self, two_type_graph) -> None:
        from kgbuilder.analytics.statistical import baseline_modularity

        partition = [
            {f"a{i}" for i in range(6)},
            {f"b{i}" for i in range(6)},
        ]
        result = baseline_modularity(
            two_type_graph, partition, n_trials=50, seed=42
        )
        assert isinstance(result.significant, bool)
        assert 0.0 <= result.p_value <= 1.0


# ============================================================================
# Tests — small_world_sigma
# ============================================================================


class TestSmallWorldSigma:
    """Test small-world coefficient computation."""

    def test_returns_positive_sigma(self, two_type_graph) -> None:
        from kgbuilder.analytics.statistical import small_world_sigma

        result = small_world_sigma(two_type_graph, n_random_graphs=5, seed=42)
        assert result.sigma > 0
        assert result.C_observed > 0
        assert result.L_observed > 0

    def test_clustered_graph_has_high_sigma(self) -> None:
        """A Watts–Strogatz small-world graph should have σ > 1."""
        import networkx as nx
        from kgbuilder.analytics.statistical import small_world_sigma

        G = nx.watts_strogatz_graph(50, 4, 0.1, seed=42)
        for n in G.nodes():
            G.nodes[n]["node_type"] = "Entity"

        result = small_world_sigma(G, n_random_graphs=5, seed=42)
        assert result.sigma > 1.0

    def test_tiny_graph_returns_empty(self, small_graph) -> None:
        from kgbuilder.analytics.statistical import small_world_sigma

        result = small_world_sigma(small_graph)
        assert result.sigma == 0.0


# ============================================================================
# Tests — bootstrap_ci
# ============================================================================


class TestBootstrapCI:
    """Test bootstrap confidence intervals."""

    def test_ci_has_valid_bounds(self, two_type_graph) -> None:
        import networkx as nx
        from kgbuilder.analytics.statistical import bootstrap_ci

        result = bootstrap_ci(
            two_type_graph,
            nx.density,
            metric_name="density",
            n_resamples=200,
            seed=42,
        )
        # CI bounds should be ordered and non-negative
        assert result.ci_lower <= result.ci_upper
        assert result.ci_lower >= 0
        assert result.std_error >= 0
        # observed should be computed correctly
        assert result.observed == pytest.approx(nx.density(two_type_graph))

    def test_narrow_ci_for_stable_metric(self) -> None:
        """On a complete graph, density is always 1.0 → CI should be tight."""
        import networkx as nx
        from kgbuilder.analytics.statistical import bootstrap_ci

        K = nx.complete_graph(8)
        result = bootstrap_ci(K, nx.density, metric_name="density", n_resamples=100)
        # CI should be narrow since density is nearly constant
        assert result.ci_upper - result.ci_lower < 0.3

    def test_ci_with_small_graph(self, small_graph) -> None:
        import networkx as nx
        from kgbuilder.analytics.statistical import bootstrap_ci

        result = bootstrap_ci(small_graph, nx.density, metric_name="density")
        # Should degrade gracefully
        assert result.observed == pytest.approx(nx.density(small_graph))


# ============================================================================
# Tests — per_type_degree_stats
# ============================================================================


class TestPerTypeDegreeStats:
    """Test per-type degree distribution breakdown."""

    def test_finds_two_types(self, two_type_graph) -> None:
        from kgbuilder.analytics.statistical import per_type_degree_stats

        results = per_type_degree_stats(two_type_graph)
        type_names = [r.type_name for r in results]
        assert "Paragraf" in type_names
        assert "Facility" in type_names

    def test_correct_counts(self, two_type_graph) -> None:
        from kgbuilder.analytics.statistical import per_type_degree_stats

        results = per_type_degree_stats(two_type_graph)
        for stats in results:
            assert stats.count == 6  # 6 nodes per type

    def test_degree_stats_reasonable(self, two_type_graph) -> None:
        from kgbuilder.analytics.statistical import per_type_degree_stats

        results = per_type_degree_stats(two_type_graph)
        for stats in results:
            assert stats.mean_degree > 0
            assert stats.min_degree >= 0
            assert stats.max_degree >= stats.min_degree
            assert len(stats.degree_distribution) > 0

    def test_bridge_node_has_higher_degree(self, two_type_graph) -> None:
        """a0 and b0 are bridge nodes → higher degree than others in type."""
        from kgbuilder.analytics.statistical import per_type_degree_stats

        results = per_type_degree_stats(two_type_graph)
        for stats in results:
            # Non-bridge nodes have degree 5 (fully connected within cluster)
            # Bridge nodes (a0, b0) have degree 6
            assert stats.max_degree == 6


# ============================================================================
# Tests — run_statistical_analysis (integration)
# ============================================================================


class TestRunStatisticalAnalysis:
    """Integration test for the full statistical analysis pipeline."""

    def test_full_analysis_with_communities(self, two_type_graph) -> None:
        from kgbuilder.analytics.statistical import run_statistical_analysis

        mapping = {n: 0 if n.startswith("a") else 1 for n in two_type_graph.nodes()}
        partition = [
            {f"a{i}" for i in range(6)},
            {f"b{i}" for i in range(6)},
        ]

        result = run_statistical_analysis(
            two_type_graph,
            community_mapping=mapping,
            community_partition=partition,
            n_modularity_trials=20,
            n_random_graphs=5,
            n_bootstrap=100,
        )

        # Power-law may fail on small uniform-degree graphs — that's expected
        # (only 2 unique degree values in a near-complete graph)
        assert result.nmi is not None
        assert result.nmi.nmi > 0.5
        assert result.baseline_modularity is not None
        assert result.small_world is not None
        assert len(result.per_type_degrees) >= 2
        assert len(result.confidence_intervals) >= 1

    def test_analysis_without_communities(self, two_type_graph) -> None:
        from kgbuilder.analytics.statistical import run_statistical_analysis

        result = run_statistical_analysis(
            two_type_graph,
            n_modularity_trials=10,
            n_random_graphs=3,
            n_bootstrap=50,
        )

        # Power-law may fail on small graphs — that's acceptable
        assert result.nmi is None  # no community mapping provided
        assert result.baseline_modularity is None  # no partition provided
        assert result.small_world is not None
        assert len(result.per_type_degrees) >= 1


# ============================================================================
# Tests — integration with structural.run_structural_analysis
# ============================================================================


class TestStructuralIntegration:
    """Test that statistical metrics flow through run_structural_analysis."""

    def test_structural_analysis_includes_statistical(
        self, two_community_store: InMemoryGraphStore
    ) -> None:
        from kgbuilder.analytics.structural import run_structural_analysis

        result = run_structural_analysis(
            two_community_store,
            centrality_measures=["degree"],
            community_algorithms=["louvain"],
        )

        # statistical should be populated
        assert result.statistical is not None
        assert result.statistical.per_type_degrees is not None
        assert len(result.statistical.per_type_degrees) >= 1

    def test_topology_backfills_from_statistical(
        self, two_community_store: InMemoryGraphStore
    ) -> None:
        from kgbuilder.analytics.structural import run_structural_analysis

        result = run_structural_analysis(
            two_community_store,
            centrality_measures=["degree"],
            community_algorithms=["louvain"],
        )

        # power_law fields should be populated from statistical module
        topo = result.topology
        if result.statistical and result.statistical.power_law:
            assert topo.power_law_ks_p is not None or topo.power_law_exponent is not None
