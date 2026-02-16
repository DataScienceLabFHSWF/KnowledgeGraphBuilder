"""Interactive Plotly visualizations for KG analytics.

Complements the static matplotlib plots in ``plots.py`` with interactive
HTML-based visualizations that support hover tooltips, zoom, pan, and
click-to-inspect.  These are particularly valuable for:

- Exploring graph topology (identify nodes by hovering)
- Investigating community structure (filter by community)
- Comparing centrality measures across nodes
- Presenting results in Jupyter notebooks or browser-based reports

All functions return ``plotly.graph_objects.Figure`` which can be:
- Shown interactively: ``fig.show()``
- Saved as HTML:       ``fig.write_html("graph.html")``
- Saved as PNG:        ``fig.write_image("graph.png")``  (requires kaleido)
- Embedded in notebooks: automatic rendering
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Lazy plotly import
# ---------------------------------------------------------------------------

_PALETTE = [
    "#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3",
    "#937860", "#DA8BC3", "#8C8C8C", "#CCB974", "#64B5CD",
    "#E377C2", "#7F7F7F", "#BCBD22", "#17BECF",
]


def _ensure_plotly() -> tuple[Any, Any]:
    """Import plotly and return (go, px)."""
    try:
        import plotly.graph_objects as go  # type: ignore[import-untyped]
        import plotly.express as px  # type: ignore[import-untyped]
        return go, px
    except ImportError as e:
        raise ImportError(
            "plotly is required for interactive plots. "
            "Install with: pip install plotly kaleido"
        ) from e


# ============================================================================
# INTERACTIVE GRAPH VISUALIZATION
# ============================================================================


def interactive_graph(
    store: Any,
    centralities: dict[str, Any] | None = None,
    communities: dict[str, Any] | None = None,
    measure: str = "pagerank",
    algorithm: str | None = None,
    color_by: str = "community",
    layout: str = "spring",
    title: str = "Knowledge Graph — Interactive View",
) -> Any:
    """Interactive graph visualization with hover tooltips.

    Each node shows its label, type, centrality scores, and community
    on hover.  Edges are drawn as lines.  Supports zoom/pan/select.

    Args:
        store: GraphStore backend.
        centralities: Dict of CentralityResult (optional).
        communities: Dict of CommunityResult (optional).
        measure: Centrality measure for node sizing.
        algorithm: Community algorithm for coloring (default: first).
        color_by: "community", "type", or "centrality".
        layout: Layout algorithm ("spring", "kamada_kawai").
        title: Plot title.

    Returns:
        plotly Figure.
    """
    go, _ = _ensure_plotly()
    from kgbuilder.analytics.structural import graph_store_to_networkx, _ensure_nx

    nx = _ensure_nx()
    G = graph_store_to_networkx(store)

    # Compute layout
    if layout == "kamada_kawai" and G.number_of_nodes() < 1500:
        pos = nx.kamada_kawai_layout(G)
    else:
        pos = nx.spring_layout(G, seed=42, k=1.8 / np.sqrt(max(G.number_of_nodes(), 1)))

    node_list = list(G.nodes())
    node_x = [pos[n][0] for n in node_list]
    node_y = [pos[n][1] for n in node_list]

    # Node metadata
    labels = [G.nodes[n].get("label", n) for n in node_list]
    types = [G.nodes[n].get("node_type", "unknown") for n in node_list]
    degrees = dict(G.degree())

    # Centrality scores for sizing + hover
    scores: dict[str, float] = {}
    all_centrality_text: list[str] = []
    if centralities:
        cr = centralities.get(measure)
        if cr:
            scores = cr.scores
        for n in node_list:
            parts = []
            for m_name, cr_obj in centralities.items():
                val = cr_obj.scores.get(n, 0.0)
                parts.append(f"{m_name}: {val:.4f}")
            all_centrality_text.append("<br>".join(parts))
    else:
        all_centrality_text = [""] * len(node_list)

    vals = np.array([scores.get(n, 0.0) for n in node_list])
    max_val = vals.max() if vals.max() > 0 else 1.0
    sizes = 5 + 35 * (vals / max_val) if max_val > 0 else np.full(len(node_list), 8.0)

    # Community assignments
    n2c: dict[str, int] = {}
    if communities:
        if algorithm is None:
            algorithm = next(iter(communities), None)
        if algorithm and algorithm in communities:
            n2c = communities[algorithm].node_to_community

    # Build hover text
    hover_texts = []
    for i, n in enumerate(node_list):
        cid = n2c.get(n, -1)
        comm_str = f"Community: {cid}" if cid >= 0 else "Community: none"
        hover = (
            f"<b>{labels[i]}</b><br>"
            f"ID: {n}<br>"
            f"Type: {types[i]}<br>"
            f"Degree: {degrees.get(n, 0)}<br>"
            f"{comm_str}<br>"
        )
        if all_centrality_text[i]:
            hover += f"<br><b>Centrality:</b><br>{all_centrality_text[i]}"
        hover_texts.append(hover)

    # Coloring
    if color_by == "community" and n2c:
        comm_ids = [n2c.get(n, -1) for n in node_list]
        node_colors = [_PALETTE[c % len(_PALETTE)] if c >= 0 else "#cccccc" for c in comm_ids]
    elif color_by == "centrality" and scores:
        node_colors = vals.tolist()  # continuous scale
    else:
        type_map: dict[str, int] = {}
        for t in types:
            if t not in type_map:
                type_map[t] = len(type_map)
        node_colors = [_PALETTE[type_map[t] % len(_PALETTE)] for t in types]

    # Edge traces
    edge_x: list[float | None] = []
    edge_y: list[float | None] = []
    for u, v, _k in G.edges(keys=True):
        if u in pos and v in pos:
            edge_x += [pos[u][0], pos[v][0], None]
            edge_y += [pos[u][1], pos[v][1], None]

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        mode="lines",
        line=dict(width=0.3, color="#888"),
        hoverinfo="none",
        showlegend=False,
    )

    # Node trace
    if color_by == "centrality" and scores:
        node_trace = go.Scatter(
            x=node_x, y=node_y,
            mode="markers",
            marker=dict(
                size=sizes,
                color=node_colors,
                colorscale="Viridis",
                colorbar=dict(title=measure),
                line=dict(width=0.5, color="#333"),
            ),
            text=hover_texts,
            hoverinfo="text",
            showlegend=False,
        )
    else:
        node_trace = go.Scatter(
            x=node_x, y=node_y,
            mode="markers",
            marker=dict(
                size=sizes,
                color=node_colors,
                line=dict(width=0.5, color="#333"),
            ),
            text=hover_texts,
            hoverinfo="text",
            showlegend=False,
        )

    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        title=title,
        showlegend=False,
        hovermode="closest",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor="white",
        width=1200,
        height=900,
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


# ============================================================================
# INTERACTIVE CENTRALITY BAR CHART
# ============================================================================


def interactive_centrality_topk(
    centralities: dict[str, Any],
    top_k: int = 20,
    store: Any | None = None,
) -> Any:
    """Interactive bar chart of top-k nodes per centrality measure.

    Uses a dropdown selector to switch between centrality measures.
    Hover shows node label, ID, and exact score.

    Args:
        centralities: Dict of CentralityResult.
        top_k: Number of top nodes to show per measure.
        store: Optional GraphStore for resolving labels.

    Returns:
        plotly Figure.
    """
    go, _ = _ensure_plotly()

    # Resolve node labels if store is available
    label_map: dict[str, str] = {}
    if store:
        for node in store.get_all_nodes():
            label_map[node.id] = node.label or node.id

    measures = list(centralities.keys())
    if not measures:
        fig = go.Figure()
        fig.add_annotation(text="No centrality data", showarrow=False)
        return fig

    # Build one bar trace per measure, only first visible
    traces = []
    buttons = []
    for i, m_name in enumerate(measures):
        cr = centralities[m_name]
        top_nodes = cr.top_k[:top_k]
        node_ids = [n for n, _ in top_nodes]
        node_labels = [label_map.get(n, n) for n in node_ids]
        node_scores = [v for _, v in top_nodes]

        hover = [
            f"<b>{label_map.get(nid, nid)}</b><br>ID: {nid}<br>{m_name}: {score:.6f}"
            for nid, score in top_nodes
        ]

        traces.append(go.Bar(
            x=node_labels,
            y=node_scores,
            text=hover,
            hoverinfo="text",
            marker_color=_PALETTE[i % len(_PALETTE)],
            visible=(i == 0),
            name=m_name,
        ))

        visibility = [False] * len(measures)
        visibility[i] = True
        buttons.append(dict(
            label=m_name,
            method="update",
            args=[
                {"visible": visibility},
                {"title": f"Top-{top_k} Nodes — {m_name}"},
            ],
        ))

    fig = go.Figure(data=traces)
    fig.update_layout(
        title=f"Top-{top_k} Nodes — {measures[0]}",
        updatemenus=[dict(
            type="dropdown",
            direction="down",
            x=0.02, y=1.12,
            buttons=buttons,
            active=0,
        )],
        xaxis_title="Node",
        yaxis_title="Score",
        plot_bgcolor="white",
        width=1000,
        height=600,
        margin=dict(l=60, r=30, t=100, b=80),
        xaxis=dict(tickangle=-45),
    )
    return fig


# ============================================================================
# INTERACTIVE COMMUNITY EXPLORER
# ============================================================================


def interactive_community_explorer(
    store: Any,
    communities: dict[str, Any],
    algorithm: str | None = None,
    layout: str = "spring",
) -> Any:
    """Interactive graph with community filtering via dropdown.

    Each community can be highlighted individually.  Nodes outside
    the selected community become semi-transparent.

    Args:
        store: GraphStore backend.
        communities: Dict of CommunityResult.
        algorithm: Which algorithm to use (default: first).
        layout: Layout algorithm.

    Returns:
        plotly Figure.
    """
    go, _ = _ensure_plotly()
    from kgbuilder.analytics.structural import graph_store_to_networkx, _ensure_nx

    nx = _ensure_nx()
    G = graph_store_to_networkx(store)

    if algorithm is None:
        algorithm = next(iter(communities), None)
    if not algorithm or algorithm not in communities:
        fig = go.Figure()
        fig.add_annotation(text="No community data", showarrow=False)
        return fig

    comm_result = communities[algorithm]
    n2c = comm_result.node_to_community

    # Layout
    if layout == "kamada_kawai" and G.number_of_nodes() < 1500:
        pos = nx.kamada_kawai_layout(G)
    else:
        pos = nx.spring_layout(G, seed=42, k=1.8 / np.sqrt(max(G.number_of_nodes(), 1)))

    node_list = list(G.nodes())
    degrees = dict(G.degree())

    # Group nodes by community
    comm_groups: dict[int, list[str]] = {}
    for n in node_list:
        cid = n2c.get(n, -1)
        comm_groups.setdefault(cid, []).append(n)

    # Sort by size
    sorted_comms = sorted(comm_groups.items(), key=lambda x: len(x[1]), reverse=True)
    max_comms = min(30, len(sorted_comms))

    # Edge trace (always visible)
    edge_x: list[float | None] = []
    edge_y: list[float | None] = []
    for u, v, _k in G.edges(keys=True):
        if u in pos and v in pos:
            edge_x += [pos[u][0], pos[v][0], None]
            edge_y += [pos[u][1], pos[v][1], None]

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        mode="lines",
        line=dict(width=0.3, color="#ddd"),
        hoverinfo="none",
        showlegend=False,
    )

    # Node trace with community coloring
    node_x = [pos[n][0] for n in node_list]
    node_y = [pos[n][1] for n in node_list]
    comm_ids = [n2c.get(n, -1) for n in node_list]
    base_colors = [_PALETTE[c % len(_PALETTE)] if c >= 0 else "#ccc" for c in comm_ids]
    sizes_arr = [6 + 20 * (degrees.get(n, 0) / max(max(degrees.values()), 1)) for n in node_list]

    hover_texts = []
    for n in node_list:
        label = G.nodes[n].get("label", n)
        ntype = G.nodes[n].get("node_type", "unknown")
        cid = n2c.get(n, -1)
        hover_texts.append(
            f"<b>{label}</b><br>Type: {ntype}<br>"
            f"Community: {cid}<br>Degree: {degrees.get(n, 0)}"
        )

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode="markers",
        marker=dict(size=sizes_arr, color=base_colors, line=dict(width=0.3, color="#333")),
        text=hover_texts,
        hoverinfo="text",
        showlegend=False,
    )

    fig = go.Figure(data=[edge_trace, node_trace])

    # Build dropdown buttons to highlight individual communities
    buttons = [dict(
        label="All communities",
        method="restyle",
        args=[{
            "marker.color": [None, base_colors],
            "marker.opacity": [None, [0.8] * len(node_list)],
        }],
    )]
    for cid, members in sorted_comms[:max_comms]:
        member_set = set(members)
        highlighted_colors = []
        highlighted_opacity = []
        for i, n in enumerate(node_list):
            if n in member_set:
                highlighted_colors.append(_PALETTE[cid % len(_PALETTE)] if cid >= 0 else "#ccc")
                highlighted_opacity.append(1.0)
            else:
                highlighted_colors.append("#eee")
                highlighted_opacity.append(0.1)

        # Build label from top members
        top = sorted(members, key=lambda x: degrees.get(x, 0), reverse=True)[:3]
        top_labels = [G.nodes[n].get("label", n)[:15] for n in top]
        btn_label = f"C{cid} ({len(members)}): {', '.join(top_labels)}"

        buttons.append(dict(
            label=btn_label[:60],
            method="restyle",
            args=[{
                "marker.color": [None, highlighted_colors],
                "marker.opacity": [None, highlighted_opacity],
            }],
        ))

    fig.update_layout(
        title=f"Community Explorer ({algorithm}, mod={comm_result.modularity:.3f})",
        updatemenus=[dict(
            type="dropdown",
            direction="down",
            x=0.02, y=1.12,
            buttons=buttons,
            active=0,
            bgcolor="white",
        )],
        showlegend=False,
        hovermode="closest",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor="white",
        width=1200,
        height=900,
        margin=dict(l=20, r=20, t=80, b=20),
    )
    return fig


# ============================================================================
# INTERACTIVE DEGREE DISTRIBUTION
# ============================================================================


def interactive_degree_distribution(
    topology: Any,
) -> Any:
    """Interactive log-log degree distribution with hover.

    Args:
        topology: TopologyResult from structural analysis.

    Returns:
        plotly Figure.
    """
    go, _ = _ensure_plotly()

    dd = topology.degree_distribution
    if not dd:
        fig = go.Figure()
        fig.add_annotation(text="No degree data", showarrow=False)
        return fig

    degrees_list = sorted(dd.keys())
    counts = [dd[d] for d in degrees_list]

    fig = go.Figure(go.Scatter(
        x=degrees_list,
        y=counts,
        mode="markers",
        marker=dict(size=8, color="#4C72B0"),
        text=[f"Degree {d}: {c} node(s)" for d, c in zip(degrees_list, counts)],
        hoverinfo="text",
    ))

    fig.update_xaxes(type="log", title="Degree (log)")
    fig.update_yaxes(type="log", title="Count (log)")

    # Power-law reference
    if topology.power_law_exponent and len(degrees_list) >= 2:
        alpha = topology.power_law_exponent
        x_ref = np.array(degrees_list, dtype=float)
        c_est = counts[0] * (degrees_list[0] ** alpha) if degrees_list[0] > 0 else 1.0
        y_ref = c_est * x_ref ** (-alpha)
        fig.add_trace(go.Scatter(
            x=x_ref.tolist(),
            y=y_ref.tolist(),
            mode="lines",
            line=dict(dash="dash", color="#C44E52", width=1.5),
            name=f"Power law (α={alpha:.2f})",
            hoverinfo="name",
        ))

    fig.update_layout(
        title="Degree Distribution (log-log)",
        plot_bgcolor="white",
        width=800,
        height=500,
        showlegend=True,
    )
    return fig


# ============================================================================
# INTERACTIVE POWER-LAW FIT (CCDF)
# ============================================================================


def interactive_power_law_fit(
    topology: Any,
    statistical: Any | None = None,
) -> Any:
    """Interactive CCDF with fitted power-law overlay and annotations.

    Uses `topology.degree_distribution` and (optionally) the
    `statistical.power_law` result to draw a fitted power-law line,
    mark xmin, and annotate α / KS p-value.
    """
    go, _ = _ensure_plotly()

    dd = topology.degree_distribution
    if not dd:
        fig = go.Figure()
        fig.add_annotation(text="No degree data", showarrow=False)
        return fig

    degrees = np.array(sorted(dd.keys(), reverse=True), dtype=float)
    counts = np.array([dd[int(d)] for d in degrees], dtype=float)
    cum = np.cumsum(counts[::-1])[::-1]
    ccdf = cum / float(cum[0])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=degrees, y=ccdf,
        mode="markers+lines",
        marker=dict(size=8, color=_PALETTE[0]),
        name="Empirical CCDF",
        hovertemplate="Degree %{x}<br>CCDF %{y:.4f}<extra></extra>",
    ))

    alpha = None
    xmin = None
    pval = None
    if statistical and getattr(statistical, "power_law", None):
        pl = statistical.power_law
        alpha = getattr(pl, "alpha", None)
        xmin = getattr(pl, "xmin", None)
        pval = getattr(pl, "p_value", None)

    if alpha and xmin:
        mask = degrees >= float(xmin)
        if mask.any():
            x_fit = degrees[mask]
            C = ccdf[mask][0] * (x_fit[0] ** (alpha - 1))
            y_fit = C * (x_fit ** (1.0 - alpha))
            fig.add_trace(go.Scatter(
                x=x_fit, y=y_fit,
                mode="lines",
                line=dict(dash="dash", color=_PALETTE[2]),
                name=f"Power-law fit (α={alpha:.2f})",
            ))
            fig.add_vline(x=float(xmin), line=dict(dash="dot", color="#C44E52"))

    annot_text = []
    if alpha:
        annot_text.append(f"α={alpha:.2f}")
    if xmin:
        annot_text.append(f"xmin={xmin}")
    if pval is not None:
        annot_text.append(f"KS p≈{pval:.3g}")

    if annot_text:
        fig.update_layout(annotations=[dict(text=" | ".join(annot_text), xref="paper", yref="paper", x=0.99, y=0.99, showarrow=False)])

    fig.update_xaxes(type="log", title="Degree (log)")
    fig.update_yaxes(type="log", title="CCDF (log)")
    fig.update_layout(title="Degree CCDF & Power-law Fit", plot_bgcolor="white", width=800, height=500)
    return fig


# ============================================================================
# INTERACTIVE NMI HEATMAP
# ============================================================================


def interactive_nmi_heatmap(nmi_result: Any) -> Any:
    """Heatmap of community × ontology-type contingency table."""
    go, _ = _ensure_plotly()

    table = nmi_result.contingency_table or {}
    if not table:
        fig = go.Figure()
        fig.add_annotation(text="No contingency data", showarrow=False)
        return fig

    types = sorted(table.keys())
    comm_ids = sorted({cid for row in table.values() for cid in row.keys()})

    z = []
    for t in types:
        row = [table[t].get(cid, 0) for cid in comm_ids]
        z.append(row)

    fig = go.Figure(go.Heatmap(
        z=z,
        x=[str(c) for c in comm_ids],
        y=types,
        colorscale="Blues",
        hovertemplate="Type: %{y}<br>Community: %{x}<br>Count: %{z}<extra></extra>",
    ))

    fig.update_layout(title=f"Community × Ontology Type (NMI={nmi_result.nmi:.3f})", width=900, height=600)
    return fig


# ============================================================================
# INTERACTIVE MODULARITY HISTOGRAM
# ============================================================================


def interactive_modularity_histogram(baseline: Any) -> Any:
    """Histogram of random baseline modularity with observed value annotated."""
    go, _ = _ensure_plotly()

    samples = getattr(baseline, "random_modularities", None) or []
    if not samples:
        fig = go.Figure()
        fig.add_annotation(text="No baseline samples (increase n_trials)", showarrow=False)
        return fig

    fig = go.Figure()
    fig.add_trace(go.Histogram(x=samples, nbinsx=20, marker_color=_PALETTE[1], name="Random Q"))
    fig.add_vline(x=baseline.observed_modularity, line=dict(color="#C44E52", width=2))
    fig.update_layout(title=f"Modularity vs Configuration-Model (z={baseline.z_score:.2f}, p={baseline.p_value:.3f})", xaxis_title="Modularity Q", yaxis_title="Count", width=800, height=450)
    return fig


# ============================================================================
# INTERACTIVE PER-TYPE DEGREE PLOT
# ============================================================================


def interactive_per_type_degree(stats: list[dict] | list[Any]) -> Any:
    """Violin plot (per-type) of degree distributions."""
    go, _ = _ensure_plotly()

    if not stats:
        fig = go.Figure()
        fig.add_annotation(text="No per-type degree data", showarrow=False)
        return fig

    fig = go.Figure()
    for i, s in enumerate(stats):
        dd = getattr(s, "degree_distribution", None) or s.get("degree_distribution", {})
        samples = []
        for degree, cnt in dd.items():
            samples.extend([int(degree)] * int(cnt))
        fig.add_trace(go.Violin(x=[s.type_name] * len(samples), y=samples, name=s.type_name, box_visible=True, meanline_visible=True, spanmode="hard", marker_color=_PALETTE[i % len(_PALETTE)]))

    fig.update_layout(title="Per-type Degree Distribution", yaxis_title="Degree", width=900, height=500)
    return fig


# ============================================================================
# INTERACTIVE CENTRALITY CORRELATION HEATMAP
# ============================================================================


def interactive_centrality_heatmap(
    centralities: dict[str, Any],
) -> Any:
    """Interactive heatmap of pairwise centrality correlations.

    Args:
        centralities: Dict of CentralityResult.

    Returns:
        plotly Figure.
    """
    go, _ = _ensure_plotly()

    measures = list(centralities.keys())
    if len(measures) < 2:
        fig = go.Figure()
        fig.add_annotation(text="Need ≥ 2 centrality measures", showarrow=False)
        return fig

    # Build score matrix
    all_nodes = set()
    for cr in centralities.values():
        all_nodes.update(cr.scores.keys())
    all_nodes_sorted = sorted(all_nodes)

    matrix = np.zeros((len(measures), len(all_nodes_sorted)))
    for i, m in enumerate(measures):
        for j, n in enumerate(all_nodes_sorted):
            matrix[i, j] = centralities[m].scores.get(n, 0.0)

    # Compute correlation
    corr = np.corrcoef(matrix)

    fig = go.Figure(go.Heatmap(
        z=corr,
        x=measures,
        y=measures,
        colorscale="RdBu_r",
        zmin=-1, zmax=1,
        text=np.round(corr, 3),
        texttemplate="%{text}",
        hovertemplate="<b>%{x}</b> vs <b>%{y}</b><br>Correlation: %{z:.3f}<extra></extra>",
    ))

    fig.update_layout(
        title="Centrality Measure Correlation",
        width=700,
        height=600,
        xaxis=dict(tickangle=-45),
        plot_bgcolor="white",
    )
    return fig


# ============================================================================
# INTERACTIVE RADAR / COMPARISON
# ============================================================================


def interactive_radar_comparison(
    profiles: dict[str, dict[str, float]],
    metrics: list[str] | None = None,
) -> Any:
    """Interactive radar chart comparing multiple graph settings.

    Args:
        profiles: Dict of {setting_name: {metric: value}}.
        metrics: Metrics to include on radar axes.

    Returns:
        plotly Figure.
    """
    go, _ = _ensure_plotly()

    if not profiles:
        fig = go.Figure()
        fig.add_annotation(text="No profiles", showarrow=False)
        return fig

    if metrics is None:
        # Gather all numeric metrics
        all_metrics: set[str] = set()
        for m_dict in profiles.values():
            all_metrics.update(k for k, v in m_dict.items() if isinstance(v, (int, float)))
        metrics = sorted(all_metrics)[:10]

    # Normalize each metric to [0, 1] across settings
    raw: dict[str, list[float]] = {m: [] for m in metrics}
    settings = list(profiles.keys())
    for m in metrics:
        for s in settings:
            raw[m].append(profiles[s].get(m, 0.0))

    normalized: dict[str, list[float]] = {}
    for m in metrics:
        vals = raw[m]
        mn, mx = min(vals), max(vals)
        rng = mx - mn if mx != mn else 1.0
        normalized[m] = [(v - mn) / rng for v in vals]

    fig = go.Figure()
    for i, s in enumerate(settings):
        r = [normalized[m][i] for m in metrics] + [normalized[metrics[0]][i]]
        theta = metrics + [metrics[0]]
        fig.add_trace(go.Scatterpolar(
            r=r, theta=theta,
            fill="toself",
            name=s,
            line_color=_PALETTE[i % len(_PALETTE)],
            opacity=0.6,
        ))

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
        title="Graph Quality Comparison (normalized)",
        showlegend=True,
        width=700,
        height=600,
    )
    return fig


# ============================================================================
# SAVE ALL INTERACTIVE PLOTS
# ============================================================================


def save_all_interactive_plots(
    output_dir: str | Path,
    structural: Any,
    graphsage: Any | None = None,
    store: Any | None = None,
    profiles: dict[str, dict[str, float]] | None = None,
    *,
    save_pngs: bool = False,
) -> dict[str, Path]:
    """Generate and save all interactive plots as HTML files (optionally PNG).

    Args:
        output_dir: Directory for output HTML files.
        structural: StructuralAnalysis result.
        graphsage: Optional GraphSAGEResult.
        store: Optional GraphStore for graph visualizations.
        profiles: Optional setting profiles for radar chart.
        save_pngs: When True, also export each figure as PNG (requires kaleido).

    Returns:
        Dict mapping plot name → file path.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    saved: dict[str, Path] = {}

    def _save(name: str, fig: Any) -> None:
        path = out / f"{name}.html"
        fig.write_html(str(path), include_plotlyjs="cdn")
        saved[name] = path
        if save_pngs:
            try:
                # require kaleido to write images
                fig.write_image(str(path.with_suffix(".png")))
                saved[f"{name}.png"] = path.with_suffix(".png")
            except Exception as e:
                logger.warning("save_png_failed", name=name, error=str(e))

    # Degree distribution
    _save("degree_distribution", interactive_degree_distribution(structural.topology))

    # Power-law fit (if available)
    if getattr(structural, "statistical", None) and getattr(structural.statistical, "power_law", None):
        _save("powerlaw_fit", interactive_power_law_fit(structural.topology, structural.statistical))

    # Centrality top-k
    if structural.centralities:
        _save("centrality_topk", interactive_centrality_topk(
            structural.centralities, top_k=20, store=store,
        ))

        if len(structural.centralities) >= 2:
            _save("centrality_heatmap", interactive_centrality_heatmap(
                structural.centralities,
            ))

    # NMI heatmap (if available)
    if getattr(structural, "statistical", None) and getattr(structural.statistical, "nmi", None):
        _save("nmi_heatmap", interactive_nmi_heatmap(structural.statistical.nmi))

    # Modularity histogram (if baseline samples available)
    if getattr(structural, "statistical", None) and getattr(structural.statistical, "baseline_modularity", None):
        bm = structural.statistical.baseline_modularity
        if getattr(bm, "random_modularities", None):
            _save("modularity_histogram", interactive_modularity_histogram(bm))

    # Per-type degree distribution
    if getattr(structural, "statistical", None) and structural.statistical.per_type_degrees:
        _save("per_type_degree", interactive_per_type_degree(structural.statistical.per_type_degrees))

    # Interactive graph
    if store:
        _save("graph_interactive", interactive_graph(
            store,
            centralities=structural.centralities,
            communities=structural.communities,
            color_by="community",
        ))

        _save("graph_centrality", interactive_graph(
            store,
            centralities=structural.centralities,
            color_by="centrality",
            title="Knowledge Graph — Centrality View",
        ))

        # Community explorer
        if structural.communities:
            _save("community_explorer", interactive_community_explorer(
                store, structural.communities,
            ))

    # Radar comparison
    if profiles:
        _save("radar_comparison", interactive_radar_comparison(profiles))

    logger.info("interactive_plots_saved", count=len(saved), directory=str(out))
    return saved
