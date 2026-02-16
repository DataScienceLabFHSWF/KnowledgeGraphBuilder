#!/usr/bin/env python3
"""Run comprehensive graph analytics on law, domain, and combined KGs from Neo4j.

Produces:
- Structural analysis (centrality, communities, topology) per graph
- Embedding analysis with community alignment (for graphs with embeddings)
- GraphSAGE structural vs semantic embedding comparison
- Cross-setting comparison with radar charts
- Quality argument per setting
- Full dashboard plots saved to output/analytics/

Usage:
    python scripts/run_graph_analytics.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

# Ensure src is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from kgbuilder.storage.protocol import Edge, InMemoryGraphStore, Node


# ---------------------------------------------------------------------------
# Neo4j → InMemoryGraphStore loaders
# ---------------------------------------------------------------------------

LAW_LABELS = {"Paragraf", "Abschnitt", "Gesetzbuch"}


def _connect_neo4j():
    """Create Neo4j driver from .env defaults."""
    from neo4j import GraphDatabase

    return GraphDatabase.driver(
        "bolt://localhost:7687", auth=("neo4j", "changeme")
    )


def _load_subgraph(
    driver,
    node_filter: str = "",
    edge_filter: str = "",
    label: str = "full",
) -> InMemoryGraphStore:
    """Load a filtered subgraph from Neo4j into InMemoryGraphStore."""
    store = InMemoryGraphStore()
    node_count = 0
    edge_count = 0
    skipped_edges = 0

    with driver.session(database="neo4j") as session:
        # Nodes
        node_query = f"""
        MATCH (n)
        {node_filter}
        RETURN n.id AS id, n.label AS label, labels(n)[0] AS node_type,
               n.properties AS properties
        """
        result = session.run(node_query)
        for record in result:
            nid = record["id"]
            if nid is None:
                # Use element id as fallback
                continue
            props = {}
            if record["properties"]:
                try:
                    props = json.loads(record["properties"])
                except (json.JSONDecodeError, TypeError):
                    pass
            store.add_node(Node(
                id=nid,
                node_type=record["node_type"] or "Unknown",
                label=record["label"] or nid,
                properties=props,
            ))
            node_count += 1

        # Edges – use Neo4j elementId to avoid r.id collisions across runs
        edge_query = f"""
        MATCH (s)-[r]->(t)
        {edge_filter}
        RETURN elementId(r) AS neo4j_eid, r.id AS id,
               s.id AS source_id, t.id AS target_id,
               type(r) AS edge_type, r.properties AS properties
        """
        result = session.run(edge_query)
        for record in result:
            src = record["source_id"]
            tgt = record["target_id"]
            if src is None or tgt is None:
                skipped_edges += 1
                continue
            # Prefer Neo4j element ID for uniqueness; fall back to r.id
            eid = record["neo4j_eid"] or record["id"]
            if eid is None:
                skipped_edges += 1
                continue
            # Only add if both endpoints exist
            if store.get_node(src) is None or store.get_node(tgt) is None:
                skipped_edges += 1
                continue
            props = {}
            if record["properties"]:
                try:
                    props = json.loads(record["properties"])
                except (json.JSONDecodeError, TypeError):
                    pass
            store.add_edge(Edge(
                id=eid,
                source_id=src,
                target_id=tgt,
                edge_type=record["edge_type"],
                properties=props,
            ))
            edge_count += 1

    print(f"  [{label}] Loaded {node_count} nodes, {edge_count} edges "
          f"(skipped {skipped_edges} edges)")
    return store


def load_law_graph(driver) -> InMemoryGraphStore:
    """Load law-only subgraph (Paragraf, Abschnitt, Gesetzbuch)."""
    return _load_subgraph(
        driver,
        node_filter="WHERE any(l IN labels(n) WHERE l IN ['Paragraf', 'Abschnitt', 'Gesetzbuch'])",
        edge_filter="""WHERE any(l IN labels(s) WHERE l IN ['Paragraf', 'Abschnitt', 'Gesetzbuch'])
                        AND any(l IN labels(t) WHERE l IN ['Paragraf', 'Abschnitt', 'Gesetzbuch'])""",
        label="law",
    )


def load_domain_graph(driver) -> InMemoryGraphStore:
    """Load domain-only subgraph (no law nodes)."""
    return _load_subgraph(
        driver,
        node_filter="WHERE NONE(l IN labels(n) WHERE l IN ['Paragraf', 'Abschnitt', 'Gesetzbuch'])",
        edge_filter="""WHERE NONE(l IN labels(s) WHERE l IN ['Paragraf', 'Abschnitt', 'Gesetzbuch'])
                        AND NONE(l IN labels(t) WHERE l IN ['Paragraf', 'Abschnitt', 'Gesetzbuch'])""",
        label="domain",
    )


def load_combined_graph(driver) -> InMemoryGraphStore:
    """Load full graph (law + domain + cross-links)."""
    return _load_subgraph(driver, label="combined")


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def run_analysis():
    """Execute full analytics pipeline on all three subgraphs."""
    import structlog
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO+
    )

    from kgbuilder.analytics.comparison import (
        compare_settings,
        extract_profile,
        generate_quality_argument,
    )
    from kgbuilder.analytics.graphsage import run_graphsage_analysis
    from kgbuilder.analytics.plots import save_all_plots
    from kgbuilder.analytics.interactive_plots import save_all_interactive_plots
    from kgbuilder.analytics.structural import run_structural_analysis

    output_dir = Path("output/analytics")
    output_dir.mkdir(parents=True, exist_ok=True)

    # -- Load graphs from Neo4j --
    print("=" * 70)
    print("LOADING GRAPHS FROM NEO4J")
    print("=" * 70)
    driver = _connect_neo4j()

    t0 = time.time()
    law_store = load_law_graph(driver)
    domain_store = load_domain_graph(driver)
    combined_store = load_combined_graph(driver)
    driver.close()
    print(f"  Loading time: {time.time() - t0:.1f}s\n")

    graphs = {
        "law": law_store,
        "domain": domain_store,
        "combined": combined_store,
    }

    # -- Structural analysis per graph --
    print("=" * 70)
    print("STRUCTURAL ANALYSIS")
    print("=" * 70)

    structural_results = {}
    centrality_measures = [
        "degree", "in_degree", "out_degree",
        "betweenness", "closeness", "pagerank",
        "eigenvector", "non_backtracking",
    ]
    community_algorithms = ["louvain", "label_propagation"]

    for name, store in graphs.items():
        print(f"\n--- {name.upper()} GRAPH ---")
        t0 = time.time()
        result = run_structural_analysis(
            store,
            centrality_measures=centrality_measures,
            community_algorithms=community_algorithms,
            top_k=20,
        )
        structural_results[name] = result
        elapsed = time.time() - t0

        topo = result.topology
        print(f"  Nodes: {topo.num_nodes}  Edges: {topo.num_edges}")
        print(f"  Density: {topo.density:.4f}  Avg degree: {topo.avg_degree:.2f}")
        print(f"  Connected components: {topo.num_connected_components}")
        if topo.diameter is not None:
            print(f"  Diameter: {topo.diameter}")
        print(f"  Clustering coefficient: {topo.avg_clustering:.4f}")
        print(f"  Transitivity: {topo.transitivity:.4f}")
        print(f"  Reciprocity: {topo.reciprocity:.4f}")
        if topo.power_law_exponent:
            print(f"  Power-law exponent: {topo.power_law_exponent:.3f}")
        if topo.small_world_sigma:
            print(f"  Small-world σ: {topo.small_world_sigma:.3f}")

        # Communities
        for alg, comm in result.communities.items():
            print(f"  {alg}: {comm.num_communities} communities, "
                  f"modularity={comm.modularity:.4f}")

        # Top centralities
        if "pagerank" in result.centralities:
            pr = result.centralities["pagerank"]
            top5 = pr.top_k[:5]
            print(f"  PageRank top-5: {[(n, f'{v:.4f}') for n, v in top5]}")
            print(f"  PageRank Gini: {pr.gini:.4f}")

        if "betweenness" in result.centralities:
            bt = result.centralities["betweenness"]
            top5 = bt.top_k[:5]
            print(f"  Betweenness top-5: {[(n, f'{v:.4f}') for n, v in top5]}")

        # Bridges
        if result.bridges:
            print(f"  Bridges: {len(result.bridges)}")

        print(f"  Analysis time: {elapsed:.1f}s")

    # -- GraphSAGE structural embeddings + comparison --
    print("\n" + "=" * 70)
    print("GRAPHSAGE STRUCTURAL EMBEDDINGS")
    print("=" * 70)

    graphsage_results = {}
    for name, store in graphs.items():
        print(f"\n--- {name.upper()} GRAPH ---")
        t0 = time.time()
        try:
            result = run_graphsage_analysis(
                store,
                output_dim=32,
                epochs=30,
            )
            graphsage_results[name] = result
            if result.structural_embeddings.size > 0:
                print(f"  Structural embeddings: {result.structural_embeddings.shape}")
            else:
                print("  No structural embeddings produced")
        except Exception as e:
            print(f"  GraphSAGE failed: {e}")
        print(f"  Time: {time.time() - t0:.1f}s")

    # -- Generate plots per graph --
    print("\n" + "=" * 70)
    print("GENERATING PLOTS")
    print("=" * 70)

    for name, store in graphs.items():
        plot_dir = output_dir / name
        print(f"\n--- {name.upper()} ---")
        saved = save_all_plots(
            output_dir=plot_dir,
            structural=structural_results[name],
            graphsage=graphsage_results.get(name),
            store=store,
            dpi=150,
        )
        for pname, ppath in saved.items():
            print(f"  {pname}: {ppath}")

    # -- Cross-setting comparison --
    print("\n" + "=" * 70)
    print("CROSS-SETTING COMPARISON")
    print("=" * 70)

    profiles = []
    for name in graphs:
        profile = extract_profile(
            name=name,
            structural=structural_results[name],
            graphsage=graphsage_results.get(name),
            description=f"{name} subgraph from Neo4j",
        )
        profiles.append(profile)
        print(f"\n  [{name}] {len(profile.metrics)} metrics extracted")

    comparison = compare_settings(profiles)
    print(f"\n  Best setting: {comparison.best_setting}")
    print(f"  Composite scores: {comparison.composite_scores}")

    # -- Interactive plots (Plotly HTML) --
    print("\n" + "=" * 70)
    print("GENERATING INTERACTIVE PLOTS (Plotly HTML)")
    print("=" * 70)

    # Build profile dicts for radar
    profile_metrics = {p.name: p.metrics for p in profiles}

    for name, store in graphs.items():
        iplot_dir = output_dir / name / "interactive"
        print(f"\n--- {name.upper()} ---")
        try:
            saved = save_all_interactive_plots(
                output_dir=iplot_dir,
                structural=structural_results[name],
                graphsage=graphsage_results.get(name),
                store=store,
                profiles=profile_metrics,
            )
            for pname, ppath in saved.items():
                print(f"  {pname}: {ppath}")
        except Exception as e:
            print(f"  Interactive plots failed: {e}")

    # Radar chart
    from kgbuilder.analytics.plots import plot_radar_comparison, plot_metric_comparison
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # Select key metrics for radar
    radar_metrics = [
        "density", "avg_clustering", "transitivity", "modularity",
        "num_connected_components_inv", "reciprocity",
    ]
    radar_data = {
        p.name: {m: p.metrics.get(m, 0) for m in radar_metrics}
        for p in profiles
    }

    fig = plot_radar_comparison(radar_data, metrics=radar_metrics)
    radar_path = output_dir / "cross_setting_radar.png"
    fig.savefig(radar_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  Radar chart: {radar_path}")

    # Metric comparison bars for key metrics
    for metric in ["modularity", "density", "avg_clustering", "transitivity"]:
        metric_data = {p.name: p.metrics for p in profiles}
        fig = plot_metric_comparison(metric_data, metric)
        path = output_dir / f"compare_{metric}.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)

    # -- Quality arguments --
    print("\n" + "=" * 70)
    print("QUALITY ARGUMENTS")
    print("=" * 70)

    for profile in profiles:
        argument = generate_quality_argument(profile, comparison)
        arg_path = output_dir / f"quality_argument_{profile.name}.md"
        arg_path.write_text(argument)
        print(f"\n  {profile.name}: saved to {arg_path}")
        # Print summary
        for line in argument.split("\n"):
            if line.startswith("- ") or line.startswith("  - "):
                print(f"    {line}")

    # -- Save raw metrics as JSON --
    metrics_export = {}
    for profile in profiles:
        metrics_export[profile.name] = profile.metrics

    metrics_path = output_dir / "all_metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics_export, f, indent=2, default=str)
    print(f"\n  All metrics saved to {metrics_path}")

    # -- Summary table --
    print("\n" + "=" * 70)
    print("SUMMARY COMPARISON TABLE")
    print("=" * 70)

    key_metrics = [
        "num_nodes", "num_edges", "density", "avg_degree",
        "avg_clustering", "transitivity", "reciprocity",
        "num_connected_components", "modularity",
    ]
    header = f"{'Metric':<30} {'Law':>12} {'Domain':>12} {'Combined':>12}"
    print(header)
    print("-" * len(header))
    for m in key_metrics:
        vals = []
        for name in ["law", "domain", "combined"]:
            p = next(p for p in profiles if p.name == name)
            v = p.metrics.get(m, 0)
            if isinstance(v, float) and v < 1:
                vals.append(f"{v:.4f}")
            else:
                vals.append(f"{v:.1f}")
        print(f"{m:<30} {vals[0]:>12} {vals[1]:>12} {vals[2]:>12}")

    print(f"\n{'Composite score':<30} ", end="")
    for name in ["law", "domain", "combined"]:
        print(f"{comparison.composite_scores[name]:>12.4f}", end="")
    print()

    print(f"\nAll outputs saved to: {output_dir.resolve()}")


if __name__ == "__main__":
    run_analysis()
