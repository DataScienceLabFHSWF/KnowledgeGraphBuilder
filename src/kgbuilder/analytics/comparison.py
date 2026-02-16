"""Cross-setting KG comparison.

Compare knowledge graphs built with different pipeline configurations
(e.g. chunk sizes, LLM models, extraction prompts) to understand how
build parameters affect graph quality.

Produces normalised metrics suitable for radar charts and tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# ============================================================================
# Data models
# ============================================================================


@dataclass
class SettingProfile:
    """Summary of a single build setting.

    Collects structural, embedding, and GraphSAGE metrics into a flat
    dictionary suitable for comparison and radar-chart plotting.
    """

    name: str
    description: str = ""
    metrics: dict[str, float] = field(default_factory=dict)
    raw_structural: Any | None = None
    raw_embedding: Any | None = None
    raw_graphsage: Any | None = None


@dataclass
class ComparisonResult:
    """Result of comparing multiple build settings."""

    profiles: list[SettingProfile]
    ranked_metrics: dict[str, list[tuple[str, float]]]
    best_setting: str
    metric_weights: dict[str, float]
    composite_scores: dict[str, float]


# ============================================================================
# Metric extraction
# ============================================================================

_DEFAULT_WEIGHTS: dict[str, float] = {
    "modularity": 1.0,
    "density": 0.5,
    "avg_clustering": 1.0,
    "num_connected_components_inv": 0.8,   # fewer = better → inverted
    "transitivity": 0.7,
    "embedding_community_ari": 1.5,
    "embedding_community_nmi": 1.2,
    "mean_coherence": 1.0,
    "structural_semantic_cosine": 1.2,
    "procrustes_fit": 1.0,
    "hub_authority_gini": -0.5,   # negative weight → lower is better
    "power_law_exponent": 0.3,
}


def extract_profile(
    name: str,
    structural: Any | None = None,
    embedding: Any | None = None,
    graphsage: Any | None = None,
    description: str = "",
) -> SettingProfile:
    """Extract a flat metric dictionary from analysis results.

    Args:
        name: Human-readable label for this setting.
        structural: StructuralAnalysis result.
        embedding: EmbeddingAnalysis result.
        graphsage: GraphSAGEResult result.
        description: Optional description of the build setting.

    Returns:
        SettingProfile with metrics dict.
    """
    metrics: dict[str, float] = {}

    if structural:
        topo = structural.topology
        metrics["num_nodes"] = float(topo.num_nodes)
        metrics["num_edges"] = float(topo.num_edges)
        metrics["density"] = topo.density
        metrics["avg_degree"] = topo.avg_degree
        metrics["avg_clustering"] = topo.avg_clustering
        metrics["transitivity"] = topo.transitivity
        metrics["reciprocity"] = topo.reciprocity
        metrics["num_connected_components"] = float(topo.num_connected_components)
        metrics["num_connected_components_inv"] = (
            1.0 / topo.num_connected_components if topo.num_connected_components > 0 else 0.0
        )

        if topo.diameter is not None:
            metrics["diameter"] = float(topo.diameter)
        if topo.avg_shortest_path is not None:
            metrics["avg_shortest_path"] = topo.avg_shortest_path
        if topo.degree_assortativity is not None:
            metrics["degree_assortativity"] = topo.degree_assortativity
        if topo.power_law_exponent is not None:
            metrics["power_law_exponent"] = topo.power_law_exponent
        if topo.small_world_sigma is not None:
            metrics["small_world_sigma"] = topo.small_world_sigma

        # Community metrics
        for alg_name, comm in structural.communities.items():
            metrics[f"{alg_name}_modularity"] = comm.modularity
            metrics[f"{alg_name}_num_communities"] = float(comm.num_communities)
        # Use best modularity
        if structural.communities:
            best_mod = max(c.modularity for c in structural.communities.values())
            metrics["modularity"] = best_mod

        # Centrality metrics
        for cent_name, cr in structural.centralities.items():
            metrics[f"{cent_name}_gini"] = cr.gini
            metrics[f"{cent_name}_mean"] = cr.mean
            metrics[f"{cent_name}_std"] = cr.std

        if "pagerank" in structural.centralities:
            metrics["hub_authority_gini"] = structural.centralities["pagerank"].gini

        # Bridges
        metrics["num_bridges"] = float(len(structural.bridges))

    if embedding:
        # Cluster quality
        for alg, cl in embedding.clusters.items():
            if cl.silhouette_score is not None:
                metrics[f"{alg}_silhouette"] = cl.silhouette_score

        # Alignment with communities
        if embedding.alignments:
            a = embedding.alignments[0]  # primary alignment
            metrics["embedding_community_ari"] = a.adjusted_rand_index
            metrics["embedding_community_nmi"] = a.normalized_mutual_info
            metrics["embedding_community_v_measure"] = a.v_measure

        # Coherence
        if embedding.coherence:
            for coh in embedding.coherence:
                metrics[f"{coh.group_name}_mean_coherence"] = coh.mean_cosine_similarity
            comm_coh = [c for c in embedding.coherence if c.group_type == "community"]
            if comm_coh:
                metrics["mean_coherence"] = comm_coh[0].mean_cosine_similarity

    if graphsage:
        if graphsage.mean_cosine_similarity is not None:
            metrics["structural_semantic_cosine"] = graphsage.mean_cosine_similarity
        if graphsage.procrustes_disparity is not None:
            metrics["procrustes_fit"] = 1.0 - graphsage.procrustes_disparity
        if graphsage.divergent_nodes:
            metrics["num_divergent_nodes"] = float(len(graphsage.divergent_nodes))

    return SettingProfile(
        name=name,
        description=description,
        metrics=metrics,
        raw_structural=structural,
        raw_embedding=embedding,
        raw_graphsage=graphsage,
    )


# ============================================================================
# Comparison engine
# ============================================================================


def compare_settings(
    profiles: list[SettingProfile],
    weights: dict[str, float] | None = None,
) -> ComparisonResult:
    """Compare multiple build settings using composite scoring.

    Metrics are min-max normalised across the provided profiles before
    weighting so that each metric contributes proportionally.

    Args:
        profiles: List of setting profiles to compare.
        weights: Metric name → weight. Positive = higher is better.

    Returns:
        ComparisonResult with rankings and composite scores.

    Raises:
        ValueError: If fewer than 2 profiles provided.
    """
    if len(profiles) < 2:
        raise ValueError("Need at least 2 profiles to compare")

    w = weights or _DEFAULT_WEIGHTS

    # Collect all metric names across profiles
    all_metric_names: set[str] = set()
    for p in profiles:
        all_metric_names.update(p.metrics.keys())

    # Build ranked metrics
    ranked: dict[str, list[tuple[str, float]]] = {}
    for m in sorted(all_metric_names):
        entries = [(p.name, p.metrics.get(m, 0.0)) for p in profiles]
        entries.sort(key=lambda x: x[1], reverse=True)
        ranked[m] = entries

    # Min-max normalise per metric, then compute composite score
    normalised: dict[str, dict[str, float]] = {}  # metric → {setting_name → normalised value}
    for m in all_metric_names:
        vals = [p.metrics.get(m, 0.0) for p in profiles]
        lo, hi = min(vals), max(vals)
        spread = hi - lo if hi != lo else 1.0
        normalised[m] = {
            p.name: (p.metrics.get(m, 0.0) - lo) / spread for p in profiles
        }

    composite: dict[str, float] = {}
    for p in profiles:
        score = 0.0
        total_weight = 0.0
        for m, mw in w.items():
            if m in normalised and p.name in normalised[m]:
                score += mw * normalised[m][p.name]
                total_weight += abs(mw)
        composite[p.name] = score / total_weight if total_weight > 0 else 0.0

    best = max(composite, key=composite.get)  # type: ignore[arg-type]

    logger.info(
        "settings_compared",
        num_settings=len(profiles),
        best_setting=best,
        composite_scores=composite,
    )

    return ComparisonResult(
        profiles=profiles,
        ranked_metrics=ranked,
        best_setting=best,
        metric_weights=w,
        composite_scores=composite,
    )


# ============================================================================
# Quality argumentation
# ============================================================================


def generate_quality_argument(
    profile: SettingProfile,
    comparison: ComparisonResult | None = None,
) -> str:
    """Generate a structured quality argument for a KG build setting.

    Produces a Markdown-formatted argument summary covering:
    - Structural properties (scale-free, small-world, density)
    - Community quality (modularity, alignment with embeddings)
    - Embedding coherence
    - Structural-semantic agreement
    - Comparative standing (if comparison provided)

    Args:
        profile: The setting profile to argue about.
        comparison: Optional comparison result for relative ranking.

    Returns:
        Markdown-formatted quality argument text.
    """
    m = profile.metrics
    lines: list[str] = []

    lines.append(f"# Quality Argument: {profile.name}")
    if profile.description:
        lines.append(f"\n_{profile.description}_\n")
    lines.append("")

    # -- Scale and density --
    lines.append("## 1. Graph Scale & Density")
    lines.append(f"- **Nodes**: {int(m.get('num_nodes', 0)):,}")
    lines.append(f"- **Edges**: {int(m.get('num_edges', 0)):,}")
    lines.append(f"- **Density**: {m.get('density', 0):.4f}")
    lines.append(f"- **Avg degree**: {m.get('avg_degree', 0):.2f}")
    if m.get("density", 0) < 0.01:
        lines.append("\n> _The graph is sparse, which is typical for real-world KGs._")
    lines.append("")

    # -- Topology --
    lines.append("## 2. Topological Properties")
    if m.get("power_law_exponent"):
        alpha = m["power_law_exponent"]
        lines.append(f"- **Power-law exponent**: α = {alpha:.2f}")
        if 2.0 < alpha < 3.5:
            lines.append("  - ✓ Within the [2, 3.5] range typical for scale-free networks")
        else:
            lines.append("  - ⚠ Outside typical scale-free range")

    if m.get("small_world_sigma"):
        sigma = m["small_world_sigma"]
        lines.append(f"- **Small-world σ**: {sigma:.2f}")
        if sigma > 1.0:
            lines.append("  - ✓ Graph exhibits small-world properties (σ > 1)")

    lines.append(f"- **Clustering coefficient**: {m.get('avg_clustering', 0):.3f}")
    lines.append(f"- **Transitivity**: {m.get('transitivity', 0):.3f}")
    lines.append(f"- **Connected components**: {int(m.get('num_connected_components', 0))}")
    if m.get("diameter"):
        lines.append(f"- **Diameter**: {int(m['diameter'])}")
    lines.append("")

    # -- Communities --
    lines.append("## 3. Community Structure")
    mod = m.get("modularity", 0)
    lines.append(f"- **Best modularity**: {mod:.3f}")
    if mod > 0.4:
        lines.append("  - ✓ Strong community structure (Q > 0.4)")
    elif mod > 0.2:
        lines.append("  - ~ Moderate community structure (0.2 < Q < 0.4)")
    else:
        lines.append("  - ⚠ Weak community structure (Q < 0.2)")
    lines.append("")

    # -- Embedding alignment --
    if m.get("embedding_community_ari") is not None:
        lines.append("## 4. Embedding ↔ Community Alignment")
        ari = m["embedding_community_ari"]
        nmi = m.get("embedding_community_nmi", 0)
        lines.append(f"- **ARI**: {ari:.3f}")
        lines.append(f"- **NMI**: {nmi:.3f}")
        if ari > 0.5:
            lines.append("  - ✓ Good alignment — semantic embeddings capture graph structure")
        elif ari > 0.2:
            lines.append("  - ~ Moderate alignment — partial semantic-structural correspondence")
        else:
            lines.append("  - ⚠ Low alignment — semantic and structural views diverge")
        lines.append("")

    # -- Structural vs semantic --
    if m.get("structural_semantic_cosine") is not None:
        lines.append("## 5. Structural vs Semantic Embeddings")
        cos = m["structural_semantic_cosine"]
        proc = m.get("procrustes_fit", 0)
        lines.append(f"- **Mean cosine similarity**: {cos:.3f}")
        lines.append(f"- **Procrustes fit**: {proc:.4f}")
        if cos > 0.6:
            lines.append(
                "  - ✓ Structural and semantic views agree well — "
                "graph topology reflects textual meaning"
            )
        elif cos > 0.3:
            lines.append("  - ~ Partial agreement — some entities have divergent roles")
        else:
            lines.append("  - ⚠ Low agreement — graph structure differs from semantic content")
        lines.append("")

    # -- Comparative standing --
    if comparison:
        lines.append("## 6. Comparative Standing")
        score = comparison.composite_scores.get(profile.name, 0)
        rank = sorted(
            comparison.composite_scores.items(), key=lambda x: x[1], reverse=True
        )
        position = next(i for i, (n, _) in enumerate(rank) if n == profile.name) + 1
        total = len(rank)
        lines.append(f"- **Composite score**: {score:.3f}")
        lines.append(f"- **Rank**: {position}/{total}")
        if position == 1:
            lines.append("  - ✓ Best setting among those compared")
        lines.append("")

    return "\n".join(lines)
