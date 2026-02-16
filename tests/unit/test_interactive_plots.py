"""Unit tests for the new interactive Plotly visualizations.

Covers:
- interactive_power_law_fit
- interactive_nmi_heatmap
- interactive_modularity_histogram
- interactive_per_type_degree
"""
from __future__ import annotations

import networkx as nx
import pytest

from kgbuilder.analytics.statistical import (
    baseline_modularity,
    community_ontology_nmi,
    per_type_degree_stats,
    power_law_test,
)
from kgbuilder.analytics.structural import compute_topology
from kgbuilder.analytics.interactive_plots import (
    interactive_modularity_histogram,
    interactive_nmi_heatmap,
    interactive_power_law_fit,
    interactive_per_type_degree,
)


def test_interactive_power_law_fit_on_ba_graph() -> None:
    G = nx.barabasi_albert_graph(200, 2, seed=42)
    topo = compute_topology(G)
    pl = power_law_test(G)

    fig = interactive_power_law_fit(topo, statistical=type("S", (), {"power_law": pl}))
    # Basic sanity
    import plotly.graph_objects as go

    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1
    assert any("Empirical CCDF" in (t.name or "") for t in fig.data)


def test_interactive_nmi_heatmap_two_types() -> None:
    # Build a small two-type graph inline
    G = nx.Graph()
    for i in range(6):
        G.add_node(f"a{i}", node_type="Paragraf")
    for i in range(6):
        G.add_node(f"b{i}", node_type="Facility")
    for i in range(6):
        for j in range(i + 1, 6):
            G.add_edge(f"a{i}", f"a{j}")
            G.add_edge(f"b{i}", f"b{j}")
    G.add_edge("a0", "b0")

    mapping = {n: 0 if n.startswith("a") else 1 for n in G.nodes()}
    nmi = community_ontology_nmi(G, mapping, type_attribute="node_type")

    fig = interactive_nmi_heatmap(nmi)
    import plotly.graph_objects as go

    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1
    z = fig.data[0].z
    # z should be a 2x2 contingency for our synthetic graph
    assert len(z) == 2


def test_interactive_modularity_histogram() -> None:
    # Build inline two-community graph
    G = nx.Graph()
    for i in range(6):
        G.add_node(f"a{i}")
    for i in range(6):
        G.add_node(f"b{i}")
    for i in range(6):
        for j in range(i + 1, 6):
            G.add_edge(f"a{i}", f"a{j}")
            G.add_edge(f"b{i}", f"b{j}")
    G.add_edge("a0", "b0")

    partition = [
        {f"a{i}" for i in range(6)},
        {f"b{i}" for i in range(6)},
    ]
    res = baseline_modularity(G, partition, n_trials=20, seed=42)
    # Ensure samples are present (implementation populates random_modularities)
    assert getattr(res, "random_modularities", None)

    fig = interactive_modularity_histogram(res)
    import plotly.graph_objects as go

    assert isinstance(fig, go.Figure)
    # Expect at least one histogram trace
    assert any(getattr(t, "type", "") == "histogram" for t in fig.data)


def test_interactive_per_type_degree() -> None:
    # Build inline two-community graph
    G = nx.Graph()
    for i in range(6):
        G.add_node(f"a{i}", node_type="Paragraf")
    for i in range(6):
        G.add_node(f"b{i}", node_type="Facility")
    for i in range(6):
        for j in range(i + 1, 6):
            G.add_edge(f"a{i}", f"a{j}")
            G.add_edge(f"b{i}", f"b{j}")
    G.add_edge("a0", "b0")

    stats = per_type_degree_stats(G)
    fig = interactive_per_type_degree(stats)
    import plotly.graph_objects as go

    assert isinstance(fig, go.Figure)
    # one violin trace per type
    assert len(fig.data) == len(stats)
