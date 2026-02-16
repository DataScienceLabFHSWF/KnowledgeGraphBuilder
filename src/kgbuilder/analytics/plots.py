"""Visualization for KG analytics: structural, embedding, and comparison plots.

All plotting functions return ``matplotlib.figure.Figure`` objects so callers
can display interactively (``fig.show()``) or save to disk (``fig.savefig()``).
Every function also accepts an optional *ax* parameter for subplot composition.

Plot catalogue:
- Degree distribution (log-log)
- Centrality bar chart (top-k per measure)
- Centrality heatmap (cross-measure correlation)
- Community size distribution
- Community graph layout (spring / Kamada-Kawai)
- Embedding scatter (PCA / t-SNE / UMAP) coloured by community or type
- Cluster-vs-community Sankey / confusion matrix
- GraphSAGE training loss curve
- Structural-vs-semantic cosine similarity distribution
- Divergent / convergent entity highlight
- Cross-setting radar chart
- Cross-setting metric comparison bar chart
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Lazy matplotlib import
# ---------------------------------------------------------------------------

_mpl_imported = False


def _ensure_mpl() -> tuple[Any, Any]:
    """Import matplotlib and return (matplotlib, pyplot)."""
    global _mpl_imported
    import matplotlib  # type: ignore[import-untyped]

    if not _mpl_imported:
        matplotlib.use("Agg")  # non-interactive backend
        _mpl_imported = True
    import matplotlib.pyplot as plt  # type: ignore[import-untyped]

    return matplotlib, plt


# ---------------------------------------------------------------------------
# Style defaults
# ---------------------------------------------------------------------------

_PALETTE = [
    "#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3",
    "#937860", "#DA8BC3", "#8C8C8C", "#CCB974", "#64B5CD",
    "#E377C2", "#7F7F7F", "#BCBD22", "#17BECF",
]


def _style_ax(ax: Any, title: str, xlabel: str, ylabel: str) -> None:
    """Apply consistent styling to an axis."""
    ax.set_title(title, fontsize=13, fontweight="bold", pad=10)
    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.tick_params(labelsize=9)
    ax.grid(True, alpha=0.3, linestyle="--")


# ============================================================================
# STRUCTURAL PLOTS
# ============================================================================


def plot_degree_distribution(
    topology: Any,
    ax: Any | None = None,
) -> Any:
    """Log-log degree distribution with power-law reference line.

    Args:
        topology: TopologyResult from structural analysis.
        ax: Optional matplotlib Axes.

    Returns:
        matplotlib Figure.
    """
    _, plt = _ensure_mpl()

    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 5))
    else:
        fig = ax.figure

    dd = topology.degree_distribution
    if not dd:
        ax.text(0.5, 0.5, "No data", transform=ax.transAxes, ha="center")
        return fig

    degrees = sorted(dd.keys())
    counts = [dd[d] for d in degrees]

    ax.scatter(degrees, counts, c=_PALETTE[0], s=30, alpha=0.7, zorder=3)
    ax.set_xscale("log")
    ax.set_yscale("log")

    # Power-law reference
    if topology.power_law_exponent:
        x_ref = np.linspace(max(1, min(degrees)), max(degrees), 100)
        y_ref = x_ref ** (-topology.power_law_exponent) * counts[0]
        ax.plot(x_ref, y_ref, "--", color="gray", alpha=0.5,
                label=f"α ≈ {topology.power_law_exponent:.2f}")
        ax.legend(fontsize=9)

    _style_ax(ax, "Degree Distribution", "Degree (k)", "Count P(k)")
    fig.tight_layout()
    return fig


def plot_centrality_topk(
    centralities: dict[str, Any],
    measures: list[str] | None = None,
    k: int = 15,
    ax: Any | None = None,
) -> Any:
    """Horizontal bar chart of top-k entities per centrality measure.

    Args:
        centralities: Dict of CentralityResult from structural analysis.
        measures: Which measures to plot (default: pagerank, betweenness).
        k: Number of top entities.
        ax: Optional matplotlib Axes.

    Returns:
        matplotlib Figure.
    """
    _, plt = _ensure_mpl()

    if measures is None:
        measures = [m for m in ["pagerank", "betweenness", "non_backtracking"]
                    if m in centralities]

    n_measures = len(measures)
    if n_measures == 0:
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "No centrality data", transform=ax.transAxes, ha="center")
        return fig

    fig, axes = plt.subplots(1, n_measures, figsize=(6 * n_measures, max(6, k * 0.4)))
    if n_measures == 1:
        axes = [axes]

    for i, m in enumerate(measures):
        cr = centralities[m]
        top = cr.top_k[:k][::-1]
        if not top:
            continue
        labels = [_truncate(nid, 25) for nid, _ in top]
        values = [v for _, v in top]
        axes[i].barh(range(len(labels)), values, color=_PALETTE[i % len(_PALETTE)], alpha=0.85)
        axes[i].set_yticks(range(len(labels)))
        axes[i].set_yticklabels(labels, fontsize=8)
        _style_ax(axes[i], f"Top-{k} by {m}", "Score", "")
        # Add Gini annotation
        axes[i].annotate(
            f"Gini = {cr.gini:.3f}",
            xy=(0.95, 0.05), xycoords="axes fraction",
            ha="right", fontsize=9, style="italic",
            bbox=dict(boxstyle="round,pad=0.3", fc="wheat", alpha=0.5),
        )

    fig.tight_layout()
    return fig


def plot_centrality_correlation(
    centralities: dict[str, Any],
    ax: Any | None = None,
) -> Any:
    """Heatmap of pairwise Spearman correlations between centrality measures.

    High correlation between PageRank and non-backtracking centrality
    indicates the hub structure is robust. Low correlation between
    betweenness and PageRank suggests different roles for bridging vs
    authority nodes.
    """
    _, plt = _ensure_mpl()
    from scipy.stats import spearmanr  # type: ignore[import-untyped]

    measures = sorted(centralities.keys())
    n = len(measures)
    if n < 2:
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "Need ≥2 measures", transform=ax.transAxes, ha="center")
        return fig

    # Align node sets
    common_nodes = set.intersection(
        *(set(centralities[m].scores.keys()) for m in measures)
    )
    common_nodes = sorted(common_nodes)

    corr_matrix = np.zeros((n, n))
    for i, mi in enumerate(measures):
        for j, mj in enumerate(measures):
            vals_i = [centralities[mi].scores[nd] for nd in common_nodes]
            vals_j = [centralities[mj].scores[nd] for nd in common_nodes]
            rho, _ = spearmanr(vals_i, vals_j)
            corr_matrix[i, j] = rho

    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 6))
    else:
        fig = ax.figure

    im = ax.imshow(corr_matrix, cmap="RdYlGn", vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(n))
    ax.set_xticklabels(measures, rotation=45, ha="right", fontsize=9)
    ax.set_yticks(range(n))
    ax.set_yticklabels(measures, fontsize=9)
    for i in range(n):
        for j in range(n):
            ax.text(j, i, f"{corr_matrix[i, j]:.2f}", ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax, label="Spearman ρ")
    _style_ax(ax, "Centrality Measure Correlations", "", "")
    fig.tight_layout()
    return fig


def plot_community_sizes(
    communities: dict[str, Any],
    ax: Any | None = None,
) -> Any:
    """Bar chart of community sizes per algorithm."""
    _, plt = _ensure_mpl()

    algs = list(communities.keys())
    if not algs:
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "No community data", transform=ax.transAxes, ha="center")
        return fig

    fig, axes = plt.subplots(1, len(algs), figsize=(5 * len(algs), 4))
    if len(algs) == 1:
        axes = [axes]

    for i, alg in enumerate(algs):
        cr = communities[alg]
        sizes = cr.community_sizes
        axes[i].bar(range(len(sizes)), sizes, color=_PALETTE[i % len(_PALETTE)], alpha=0.8)
        _style_ax(
            axes[i],
            f"{alg} ({cr.num_communities} comm.)\nmod={cr.modularity:.3f}",
            "Community", "Size",
        )

    fig.tight_layout()
    return fig


def plot_graph_layout(
    store: Any,
    communities: dict[str, int] | None = None,
    layout: str = "spring",
    ax: Any | None = None,
) -> Any:
    """Graph visualisation coloured by community or node type.

    For small-to-medium graphs (<2000 nodes). Uses NetworkX layout algorithms.
    """
    _, plt = _ensure_mpl()
    from kgbuilder.analytics.structural import graph_store_to_networkx, _ensure_nx

    nx = _ensure_nx()
    G = graph_store_to_networkx(store)

    if G.number_of_nodes() > 2000:
        logger.warning("graph_too_large_for_layout", nodes=G.number_of_nodes())

    if ax is None:
        fig, ax = plt.subplots(figsize=(12, 10))
    else:
        fig = ax.figure

    # Layout
    if layout == "spring":
        pos = nx.spring_layout(G, seed=42, k=1.5 / np.sqrt(max(G.number_of_nodes(), 1)))
    elif layout == "kamada_kawai":
        pos = nx.kamada_kawai_layout(G)
    else:
        pos = nx.spring_layout(G, seed=42)

    # Colouring
    if communities:
        node_list = list(G.nodes())
        colors = [communities.get(n, -1) for n in node_list]
        max_comm = max(colors) + 1 if colors else 1
        cmap_colors = [_PALETTE[c % len(_PALETTE)] if c >= 0 else "#cccccc" for c in colors]
    else:
        node_list = list(G.nodes())
        type_map: dict[str, int] = {}
        colors = []
        for n in node_list:
            nt = G.nodes[n].get("node_type", "unknown")
            if nt not in type_map:
                type_map[nt] = len(type_map)
            colors.append(type_map[nt])
        cmap_colors = [_PALETTE[c % len(_PALETTE)] for c in colors]

    # Sizes proportional to degree
    degrees = dict(G.degree())
    max_deg = max(degrees.values()) if degrees else 1
    node_sizes = [30 + 200 * (degrees.get(n, 0) / max_deg) for n in node_list]

    nx.draw_networkx_nodes(G, pos, nodelist=node_list, node_color=cmap_colors,
                           node_size=node_sizes, alpha=0.8, ax=ax)
    nx.draw_networkx_edges(G, pos, alpha=0.15, width=0.5, ax=ax,
                           arrows=True, arrowsize=5)

    # Labels for top-degree nodes only (declutter)
    top_nodes = sorted(node_list, key=lambda n: degrees.get(n, 0), reverse=True)[:15]
    labels = {n: _truncate(G.nodes[n].get("label", n), 15) for n in top_nodes}
    nx.draw_networkx_labels(G, pos, labels, font_size=7, ax=ax)

    _style_ax(ax, "Knowledge Graph Structure", "", "")
    ax.set_axis_off()
    fig.tight_layout()
    return fig


def plot_centrality_graph(
    store: Any,
    centralities: dict[str, Any],
    measure: str = "pagerank",
    top_k: int = 20,
    layout: str = "spring",
    ax: Any | None = None,
) -> Any:
    """Graph layout with node size proportional to centrality, top-k labeled.

    Highlights the most central nodes so their structural role is visible.
    Peripheral nodes are drawn small and transparent.

    Args:
        store: GraphStore to convert.
        centralities: Dict of CentralityResult.
        measure: Which centrality measure drives node sizing.
        top_k: Number of top nodes to label.
        layout: Layout algorithm (spring, kamada_kawai).
        ax: Optional matplotlib Axes.

    Returns:
        matplotlib Figure.
    """
    _, plt = _ensure_mpl()
    from kgbuilder.analytics.structural import graph_store_to_networkx, _ensure_nx

    nx = _ensure_nx()
    G = graph_store_to_networkx(store)

    if measure not in centralities:
        measure = next(iter(centralities), None)
        if measure is None:
            fig, ax_ = plt.subplots()
            ax_.text(0.5, 0.5, "No centrality data", transform=ax_.transAxes, ha="center")
            return fig

    cr = centralities[measure]
    scores = cr.scores

    if ax is None:
        fig, ax = plt.subplots(figsize=(14, 11))
    else:
        fig = ax.figure

    # Layout
    if layout == "kamada_kawai":
        pos = nx.kamada_kawai_layout(G)
    else:
        pos = nx.spring_layout(G, seed=42, k=1.5 / np.sqrt(max(G.number_of_nodes(), 1)))

    node_list = list(G.nodes())
    vals = np.array([scores.get(n, 0.0) for n in node_list])
    max_val = vals.max() if vals.max() > 0 else 1.0

    # Size: linear map to [15, 600] based on centrality score
    sizes = 15 + 585 * (vals / max_val)
    # Alpha: high-centrality nodes opaque, peripheral transparent
    alphas = np.clip(0.15 + 0.85 * (vals / max_val), 0.08, 1.0)

    # Color by node type
    type_map: dict[str, int] = {}
    type_idx = []
    for n in node_list:
        nt = G.nodes[n].get("node_type", "unknown")
        if nt not in type_map:
            type_map[nt] = len(type_map)
        type_idx.append(type_map[nt])
    node_colors = [_PALETTE[c % len(_PALETTE)] for c in type_idx]

    # Draw nodes in order of centrality (low first, high on top)
    order = np.argsort(vals)
    for idx in order:
        n = node_list[idx]
        nx.draw_networkx_nodes(
            G, pos, nodelist=[n], node_color=[node_colors[idx]],
            node_size=[float(sizes[idx])], alpha=float(alphas[idx]), ax=ax,
        )

    nx.draw_networkx_edges(G, pos, alpha=0.08, width=0.3, ax=ax, arrows=False)

    # Label top-k nodes
    top_indices = np.argsort(vals)[-top_k:]
    labels = {}
    for idx in top_indices:
        n = node_list[idx]
        label = G.nodes[n].get("label", n)
        labels[n] = _truncate(label, 22)

    nx.draw_networkx_labels(G, pos, labels, font_size=7, font_weight="bold", ax=ax)

    # Legend for node types
    from matplotlib.lines import Line2D
    legend_items = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=_PALETTE[i % len(_PALETTE)],
               markersize=8, label=nt)
        for nt, i in sorted(type_map.items(), key=lambda x: x[1])
    ]
    if len(legend_items) <= 12:
        ax.legend(handles=legend_items, loc="lower left", fontsize=7,
                  framealpha=0.7, title="Node type", title_fontsize=8)

    _style_ax(ax, f"Central Nodes — {measure}", "", "")
    ax.set_axis_off()
    fig.tight_layout()
    return fig


def plot_community_graph(
    store: Any,
    communities: dict[str, Any],
    algorithm: str | None = None,
    top_k_labels: int = 5,
    layout: str = "spring",
    ax: Any | None = None,
) -> Any:
    """Graph layout coloured by community, with community names derived from members.

    Each community is labeled by its most representative members (highest
    PageRank or degree within the community).  This makes the community
    structure interpretable.

    Args:
        store: GraphStore to convert.
        communities: Dict of CommunityResult (algorithm → result).
        algorithm: Which algorithm's partition to use (default: first).
        top_k_labels: How many top members to use for naming each community.
        layout: Layout algorithm.
        ax: Optional matplotlib Axes.

    Returns:
        matplotlib Figure.
    """
    _, plt = _ensure_mpl()
    from kgbuilder.analytics.structural import graph_store_to_networkx, _ensure_nx

    nx = _ensure_nx()
    G = graph_store_to_networkx(store)

    if algorithm is None:
        algorithm = next(iter(communities), None)
    if algorithm is None or algorithm not in communities:
        fig, ax_ = plt.subplots()
        ax_.text(0.5, 0.5, "No community data", transform=ax_.transAxes, ha="center")
        return fig

    comm_result = communities[algorithm]
    n2c = comm_result.node_to_community

    if ax is None:
        fig, ax = plt.subplots(figsize=(16, 12))
    else:
        fig = ax.figure

    # Layout
    if layout == "kamada_kawai":
        pos = nx.kamada_kawai_layout(G)
    else:
        pos = nx.spring_layout(G, seed=42, k=1.8 / np.sqrt(max(G.number_of_nodes(), 1)),
                               iterations=80)

    node_list = list(G.nodes())
    degrees = dict(G.degree())

    # Community assignments
    comm_ids = [n2c.get(n, -1) for n in node_list]
    cmap_colors = [_PALETTE[c % len(_PALETTE)] if c >= 0 else "#cccccc" for c in comm_ids]
    sizes = [25 + 175 * (degrees.get(n, 0) / max(max(degrees.values()), 1)) for n in node_list]

    # Draw
    nx.draw_networkx_nodes(G, pos, nodelist=node_list, node_color=cmap_colors,
                           node_size=sizes, alpha=0.75, ax=ax)
    nx.draw_networkx_edges(G, pos, alpha=0.06, width=0.3, ax=ax, arrows=False)

    # Build community names from top members
    comm_members: dict[int, list[tuple[str, float, str]]] = {}
    for n in node_list:
        cid = n2c.get(n, -1)
        if cid < 0:
            continue
        label = G.nodes[n].get("label", n)
        deg = degrees.get(n, 0)
        if cid not in comm_members:
            comm_members[cid] = []
        comm_members[cid].append((n, deg, label))

    # Sort communities by size (descending)
    sorted_comms = sorted(comm_members.items(), key=lambda x: len(x[1]), reverse=True)

    # Label the largest communities at their centroid
    max_labeled = min(20, len(sorted_comms))
    comm_labels_text: list[str] = []
    for cid, members in sorted_comms[:max_labeled]:
        # Sort members by degree
        members.sort(key=lambda x: x[1], reverse=True)
        top_names = [_truncate(label, 18) for _, _, label in members[:top_k_labels]]
        name = ", ".join(top_names)
        comm_labels_text.append(f"C{cid} ({len(members)}): {name}")

        # Centroid
        cx = np.mean([pos[n][0] for n, _, _ in members if n in pos])
        cy = np.mean([pos[n][1] for n, _, _ in members if n in pos])
        ax.annotate(
            f"C{cid} ({len(members)})",
            xy=(cx, cy), fontsize=7, fontweight="bold", ha="center",
            color=_PALETTE[cid % len(_PALETTE)],
            bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.7, ec="none"),
        )

    # Label top-degree nodes across all communities
    all_sorted = sorted(node_list, key=lambda n: degrees.get(n, 0), reverse=True)
    labels = {n: _truncate(G.nodes[n].get("label", n), 18) for n in all_sorted[:15]}
    nx.draw_networkx_labels(G, pos, labels, font_size=6, ax=ax)

    _style_ax(ax, f"Communities ({algorithm}, mod={comm_result.modularity:.3f})", "", "")
    ax.set_axis_off()

    # Add community legend as text box
    legend_text = "\n".join(comm_labels_text[:15])
    ax.text(
        0.01, 0.01, legend_text, transform=ax.transAxes, fontsize=5.5,
        verticalalignment="bottom", fontfamily="monospace",
        bbox=dict(boxstyle="round,pad=0.4", fc="white", alpha=0.85, ec="gray"),
    )

    fig.tight_layout()
    return fig


# ============================================================================
# EMBEDDING PLOTS
# ============================================================================


def plot_embedding_scatter(
    reduction: Any,
    partition: dict[str, int] | None = None,
    partition_name: str = "community",
    node_labels: dict[str, str] | None = None,
    ax: Any | None = None,
) -> Any:
    """2D scatter plot of reduced embeddings, coloured by partition.

    Args:
        reduction: DimensionReduction result.
        partition: node_id → group_id for colouring.
        partition_name: Label for the legend.
        node_labels: node_id → display label for annotation.
        ax: Optional matplotlib Axes.

    Returns:
        matplotlib Figure.
    """
    _, plt = _ensure_mpl()

    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 8))
    else:
        fig = ax.figure

    coords = reduction.coords
    node_ids = reduction.node_ids

    if partition:
        groups = [partition.get(nid, -1) for nid in node_ids]
        unique_groups = sorted(set(groups))
        for gid in unique_groups:
            mask = [g == gid for g in groups]
            pts = coords[mask]
            color = _PALETTE[gid % len(_PALETTE)] if gid >= 0 else "#cccccc"
            label = f"{partition_name} {gid}" if gid >= 0 else "unassigned"
            ax.scatter(pts[:, 0], pts[:, 1], c=color, s=25, alpha=0.7, label=label)
    else:
        ax.scatter(coords[:, 0], coords[:, 1], c=_PALETTE[0], s=25, alpha=0.7)

    # Annotate extreme points
    if node_labels:
        for nid, lbl in node_labels.items():
            if nid in node_ids:
                idx = node_ids.index(nid)
                ax.annotate(lbl, coords[idx], fontsize=7, alpha=0.8)

    method = reduction.method.upper()
    title = f"Embedding Space ({method})"
    if reduction.explained_variance_ratio:
        evr = reduction.explained_variance_ratio
        title += f"\nPC1={evr[0]:.1%}, PC2={evr[1]:.1%}"

    _style_ax(ax, title, f"{method}₁", f"{method}₂")
    if partition and len(set(groups)) <= 12:
        ax.legend(fontsize=7, loc="best", framealpha=0.5)

    fig.tight_layout()
    return fig


def plot_cluster_community_confusion(
    alignment: Any,
    cluster_partition: dict[str, int],
    community_partition: dict[str, int],
    ax: Any | None = None,
) -> Any:
    """Confusion matrix between embedding clusters and graph communities.

    Shows how clusters map to communities. A diagonal-dominant matrix
    means the embedding space aligns well with graph structure.
    """
    _, plt = _ensure_mpl()

    common = sorted(set(cluster_partition.keys()) & set(community_partition.keys()))
    if len(common) < 2:
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "No data", transform=ax.transAxes, ha="center")
        return fig

    clust_labels = [cluster_partition[n] for n in common]
    comm_labels = [community_partition[n] for n in common]

    from sklearn.metrics import confusion_matrix  # type: ignore[import-untyped]
    cm = confusion_matrix(comm_labels, clust_labels)

    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 6))
    else:
        fig = ax.figure

    im = ax.imshow(cm, cmap="YlOrRd", aspect="auto")
    ax.set_xlabel("Embedding Cluster")
    ax.set_ylabel("Graph Community")
    fig.colorbar(im, ax=ax, label="Node count")

    # Annotate
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center", fontsize=8)

    _style_ax(
        ax,
        f"Cluster ↔ Community Alignment\nARI={alignment.adjusted_rand_index:.3f}  "
        f"NMI={alignment.normalized_mutual_info:.3f}",
        "Embedding Cluster", "Graph Community",
    )
    fig.tight_layout()
    return fig


# ============================================================================
# GRAPHSAGE PLOTS
# ============================================================================


def plot_graphsage_loss(
    losses: list[float],
    ax: Any | None = None,
) -> Any:
    """GraphSAGE training loss curve."""
    _, plt = _ensure_mpl()

    if ax is None:
        fig, ax = plt.subplots(figsize=(7, 4))
    else:
        fig = ax.figure

    ax.plot(range(1, len(losses) + 1), losses, color=_PALETTE[0], linewidth=1.5)
    _style_ax(ax, "GraphSAGE Training Loss", "Epoch", "Loss")
    fig.tight_layout()
    return fig


def plot_structural_vs_semantic(
    result: Any,
    ax: Any | None = None,
) -> Any:
    """Distribution of per-node cosine similarities between structural
    and semantic embedding spaces.

    Peaks near 1.0 = good agreement. Long left tail = divergent entities.
    """
    _, plt = _ensure_mpl()

    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 5))
    else:
        fig = ax.figure

    cosines = result.cosine_similarities
    if len(cosines) == 0:
        ax.text(0.5, 0.5, "No data", transform=ax.transAxes, ha="center")
        return fig

    ax.hist(cosines, bins=40, color=_PALETTE[0], alpha=0.7, edgecolor="white")
    ax.axvline(result.mean_cosine_similarity, color=_PALETTE[1], linestyle="--",
               label=f"μ = {result.mean_cosine_similarity:.3f}")
    ax.legend(fontsize=9)
    _style_ax(
        ax,
        f"Structural vs Semantic Similarity\n"
        f"Procrustes disparity = {result.procrustes_disparity:.4f}",
        "Cosine Similarity", "Count",
    )
    fig.tight_layout()
    return fig


def plot_divergent_entities(
    result: Any,
    store: Any | None = None,
    k: int = 15,
    ax: Any | None = None,
) -> Any:
    """Bar chart of most divergent entities (structural ≠ semantic).

    These are the entities where the graph neighbourhood tells a very
    different story than the text description — potential quality issues
    or interesting cross-domain links.
    """
    _, plt = _ensure_mpl()

    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 5))
    else:
        fig = ax.figure

    divergent = result.divergent_nodes[:k][::-1]
    if not divergent:
        ax.text(0.5, 0.5, "No data", transform=ax.transAxes, ha="center")
        return fig

    labels = [_truncate(nid, 30) for nid, _ in divergent]
    values = [v for _, v in divergent]

    colors = [_PALETTE[3] if v < 0 else _PALETTE[1] for v in values]
    ax.barh(range(len(labels)), values, color=colors, alpha=0.85)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.axvline(0, color="gray", linewidth=0.5)
    _style_ax(ax, "Most Divergent Entities\n(structural ≠ semantic)", "Cosine Similarity", "")
    fig.tight_layout()
    return fig


# ============================================================================
# CROSS-SETTING COMPARISON
# ============================================================================


def plot_radar_comparison(
    settings: dict[str, dict[str, float]],
    metrics: list[str] | None = None,
    ax: Any | None = None,
) -> Any:
    """Radar chart comparing KG quality across build settings.

    Args:
        settings: {setting_name: {metric_name: value}}.
        metrics: Which metrics to show on the radar.
        ax: Optional matplotlib Axes (must be polar).

    Returns:
        matplotlib Figure.
    """
    _, plt = _ensure_mpl()

    if metrics is None:
        # Collect all metrics from all settings
        all_metrics: set[str] = set()
        for vals in settings.values():
            all_metrics.update(vals.keys())
        metrics = sorted(all_metrics)

    n_metrics = len(metrics)
    if n_metrics < 3:
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "Need ≥3 metrics for radar", transform=ax.transAxes, ha="center")
        return fig

    angles = np.linspace(0, 2 * np.pi, n_metrics, endpoint=False).tolist()
    angles.append(angles[0])

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={"polar": True})

    for i, (name, vals) in enumerate(settings.items()):
        values = [vals.get(m, 0.0) for m in metrics]
        values.append(values[0])
        ax.plot(angles, values, "o-", linewidth=1.5, color=_PALETTE[i % len(_PALETTE)],
                label=name, markersize=4)
        ax.fill(angles, values, alpha=0.1, color=_PALETTE[i % len(_PALETTE)])

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metrics, fontsize=8)
    ax.set_title("KG Quality Across Build Settings", fontsize=13, fontweight="bold", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=8)
    fig.tight_layout()
    return fig


def plot_metric_comparison(
    settings: dict[str, dict[str, float]],
    metric_name: str,
    ax: Any | None = None,
) -> Any:
    """Grouped bar chart for a single metric across settings."""
    _, plt = _ensure_mpl()

    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 5))
    else:
        fig = ax.figure

    names = list(settings.keys())
    values = [settings[n].get(metric_name, 0.0) for n in names]

    bars = ax.bar(range(len(names)), values,
                  color=[_PALETTE[i % len(_PALETTE)] for i in range(len(names))],
                  alpha=0.85)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, rotation=20, ha="right", fontsize=9)

    # Value labels
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                f"{val:.3f}", ha="center", fontsize=8)

    _style_ax(ax, f"Comparison: {metric_name}", "Build Setting", metric_name)
    fig.tight_layout()
    return fig


# ============================================================================
# COMBINED REPORT FIGURE
# ============================================================================


def plot_analytics_dashboard(
    structural: Any,
    embedding: Any | None = None,
    graphsage: Any | None = None,
    store: Any | None = None,
) -> Any:
    """Generate a multi-panel analytics dashboard figure.

    Combines key plots into a single figure for quick overview.

    Returns:
        matplotlib Figure with 2×3 subplot grid.
    """
    _, plt = _ensure_mpl()

    fig, axes = plt.subplots(2, 3, figsize=(20, 12))
    fig.suptitle("Knowledge Graph Analytics Dashboard", fontsize=16, fontweight="bold", y=0.98)

    # 1. Degree distribution
    plot_degree_distribution(structural.topology, ax=axes[0, 0])

    # 2. Top centralities
    if structural.centralities:
        top_measure = "pagerank" if "pagerank" in structural.centralities else \
            list(structural.centralities.keys())[0]
        cr = structural.centralities[top_measure]
        top = cr.top_k[:10][::-1]
        if top:
            labels = [_truncate(n, 20) for n, _ in top]
            vals = [v for _, v in top]
            axes[0, 1].barh(range(len(labels)), vals, color=_PALETTE[0], alpha=0.85)
            axes[0, 1].set_yticks(range(len(labels)))
            axes[0, 1].set_yticklabels(labels, fontsize=7)
            _style_ax(axes[0, 1], f"Top-10 by {top_measure}", "Score", "")
        else:
            axes[0, 1].text(0.5, 0.5, "No centrality data", transform=axes[0, 1].transAxes, ha="center")

    # 3. Community sizes
    if structural.communities:
        plot_community_sizes(structural.communities, ax=axes[0, 2])
    else:
        axes[0, 2].text(0.5, 0.5, "No communities", transform=axes[0, 2].transAxes, ha="center")

    # 4. Embedding scatter
    if embedding and embedding.reductions:
        method = "pca" if "pca" in embedding.reductions else list(embedding.reductions.keys())[0]
        comm_partition = None
        if structural.communities:
            first_alg = list(structural.communities.keys())[0]
            comm_partition = structural.communities[first_alg].node_to_community
        plot_embedding_scatter(embedding.reductions[method], partition=comm_partition,
                               ax=axes[1, 0])
    else:
        axes[1, 0].text(0.5, 0.5, "No embeddings", transform=axes[1, 0].transAxes, ha="center")

    # 5. Structural vs semantic similarity
    if graphsage and len(graphsage.cosine_similarities) > 0:
        plot_structural_vs_semantic(graphsage, ax=axes[1, 1])
    else:
        axes[1, 1].text(0.5, 0.5, "No GraphSAGE data", transform=axes[1, 1].transAxes, ha="center")

    # 6. Summary statistics text
    ax_text = axes[1, 2]
    ax_text.axis("off")
    topo = structural.topology
    lines = [
        f"Nodes: {topo.num_nodes}",
        f"Edges: {topo.num_edges}",
        f"Density: {topo.density:.4f}",
        f"Components: {topo.num_connected_components}",
        f"Avg degree: {topo.avg_degree:.2f}",
        f"Clustering coeff: {topo.avg_clustering:.3f}",
        f"Transitivity: {topo.transitivity:.3f}",
        f"Reciprocity: {topo.reciprocity:.3f}",
    ]
    if topo.diameter is not None:
        lines.append(f"Diameter: {topo.diameter}")
    if topo.degree_assortativity is not None:
        lines.append(f"Degree assortativity: {topo.degree_assortativity:.3f}")
    if topo.power_law_exponent is not None:
        lines.append(f"Power-law α: {topo.power_law_exponent:.2f}")

    if embedding and embedding.alignments:
        a = embedding.alignments[0]
        lines.append("")
        lines.append("── Cluster ↔ Community ──")
        lines.append(f"ARI: {a.adjusted_rand_index:.3f}")
        lines.append(f"NMI: {a.normalized_mutual_info:.3f}")

    if graphsage and graphsage.procrustes_disparity is not None:
        lines.append("")
        lines.append("── Structural vs Semantic ──")
        lines.append(f"Mean cosine: {graphsage.mean_cosine_similarity:.3f}")
        lines.append(f"Procrustes: {graphsage.procrustes_disparity:.4f}")

    ax_text.text(0.05, 0.95, "\n".join(lines), transform=ax_text.transAxes,
                 fontsize=9, verticalalignment="top", fontfamily="monospace",
                 bbox=dict(boxstyle="round", fc="lightyellow", alpha=0.8))

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    return fig


# ============================================================================
# Save helpers
# ============================================================================

def save_all_plots(
    output_dir: str | Path,
    structural: Any,
    embedding: Any | None = None,
    graphsage: Any | None = None,
    store: Any | None = None,
    fmt: str = "png",
    dpi: int = 150,
) -> dict[str, Path]:
    """Generate and save all available plots to a directory.

    Returns:
        Dict mapping plot name → file path.
    """
    _, plt = _ensure_mpl()

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    saved: dict[str, Path] = {}

    def _save(name: str, fig: Any) -> None:
        path = out / f"{name}.{fmt}"
        fig.savefig(path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        saved[name] = path

    # Structural
    _save("degree_distribution", plot_degree_distribution(structural.topology))

    if structural.centralities:
        _save("centrality_topk", plot_centrality_topk(structural.centralities))
        if len(structural.centralities) >= 2:
            _save("centrality_correlation", plot_centrality_correlation(structural.centralities))

    if structural.communities:
        _save("community_sizes", plot_community_sizes(structural.communities))

    if store:
        comm = None
        if structural.communities:
            first_alg = list(structural.communities.keys())[0]
            comm = structural.communities[first_alg].node_to_community
        _save("graph_layout", plot_graph_layout(store, communities=comm))

        # Centrality graph — nodes sized by PageRank with labels
        if structural.centralities:
            _save("centrality_graph", plot_centrality_graph(
                store, structural.centralities, measure="pagerank", top_k=20,
            ))

        # Community graph — communities labeled with member names
        if structural.communities:
            _save("community_graph", plot_community_graph(
                store, structural.communities, top_k_labels=5,
            ))

    # Embedding
    if embedding:
        for method, reduction in embedding.reductions.items():
            comm = None
            if structural.communities:
                first_alg = list(structural.communities.keys())[0]
                comm = structural.communities[first_alg].node_to_community
            _save(
                f"embedding_{method}",
                plot_embedding_scatter(reduction, partition=comm),
            )

        if embedding.alignments and embedding.clusters.get("kmeans"):
            first_alg = list(structural.communities.keys())[0] if structural.communities else None
            if first_alg:
                _save(
                    "cluster_community_confusion",
                    plot_cluster_community_confusion(
                        embedding.alignments[0],
                        embedding.clusters["kmeans"].node_to_cluster,
                        structural.communities[first_alg].node_to_community,
                    ),
                )

    # GraphSAGE
    if graphsage:
        if graphsage.training_loss:
            _save("graphsage_loss", plot_graphsage_loss(graphsage.training_loss))
        if len(graphsage.cosine_similarities) > 0:
            _save("structural_vs_semantic", plot_structural_vs_semantic(graphsage))
            _save("divergent_entities", plot_divergent_entities(graphsage, store=store))

    # Dashboard
    _save("dashboard", plot_analytics_dashboard(structural, embedding, graphsage, store))

    logger.info("plots_saved", count=len(saved), directory=str(out))
    return saved


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _truncate(s: str, max_len: int = 25) -> str:
    """Truncate a string for display."""
    return s if len(s) <= max_len else s[: max_len - 2] + "…"
