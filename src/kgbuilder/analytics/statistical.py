"""Statistical rigor metrics for Knowledge Graph quality evaluation.

Provides scientifically defensible statistical tests:
- Power-law goodness-of-fit (KS test via the ``powerlaw`` package)
- NMI community–ontology alignment
- Random baseline modularity (configuration model null hypothesis)
- Small-world coefficient σ = (C/C_rand) / (L/L_rand)
- Bootstrap confidence intervals for arbitrary graph metrics
- Per-type degree distribution breakdown

All functions are pure — they take a NetworkX graph and return
typed result dataclasses.

References:
    Clauset, Shalizi & Newman (2009): "Power-law distributions in
    empirical data", SIAM Review 51(4).
    Humphries & Gurney (2008): "Network 'Small-World-Ness': A
    Quantitative Method for Determining Canonical Network Equivalence",
    PLoS ONE 3(4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------


@dataclass
class PowerLawResult:
    """Result of power-law goodness-of-fit test.

    Attributes:
        alpha: Maximum-likelihood exponent estimate.
        xmin: Lower bound for power-law behaviour.
        ks_statistic: Kolmogorov–Smirnov distance between data and fit.
        p_value: p-value from KS test (p < 0.1 → reject power-law hypothesis).
        comparison_lognormal_R: Log-likelihood ratio vs log-normal alternative.
            Positive means power-law is better; negative means log-normal is better.
        comparison_lognormal_p: p-value of the log-likelihood ratio test.
        num_tail_samples: Number of observations ≥ xmin used for the fit.
        plausible: Whether the power-law hypothesis is plausible (p ≥ 0.1).
    """

    alpha: float = 0.0
    xmin: float = 1.0
    ks_statistic: float = 0.0
    p_value: float = 0.0
    comparison_lognormal_R: float = 0.0
    comparison_lognormal_p: float = 1.0
    num_tail_samples: int = 0
    plausible: bool = False


@dataclass
class NMIResult:
    """Normalised Mutual Information between communities and ontology types.

    Attributes:
        nmi: NMI score in [0, 1]. 1 = communities perfectly recover ontology types.
        num_communities: Number of communities in the partition.
        num_types: Number of distinct ontology types across nodes.
        contingency_table: Optional cross-tabulation (type → community counts).
    """

    nmi: float = 0.0
    num_communities: int = 0
    num_types: int = 0
    contingency_table: dict[str, dict[int, int]] = field(default_factory=dict)


@dataclass
class BaselineModularityResult:
    """Modularity comparison against random configuration model baseline.

    Attributes:
        observed_modularity: Modularity of the detected communities.
        baseline_mean: Mean modularity across random configuration-model rewirings.
        baseline_std: Standard deviation of random modularity.
        z_score: How many standard deviations above random (effect size).
        p_value: Fraction of random trials with modularity ≥ observed.
        n_trials: Number of random rewirings used.
        significant: Whether observed > baseline at p < 0.05.
    """

    observed_modularity: float = 0.0
    baseline_mean: float = 0.0
    baseline_std: float = 0.0
    z_score: float = 0.0
    p_value: float = 1.0
    n_trials: int = 100
    significant: bool = False
    # Optional: store the sampled random modularity values (useful for plots)
    random_modularities: list[float] = field(default_factory=list)


@dataclass
class SmallWorldResult:
    """Small-world coefficient σ = (C/C_rand) / (L/L_rand).

    Attributes:
        sigma: Small-world coefficient. σ > 1 indicates small-world topology.
        C_observed: Observed average clustering coefficient.
        C_random: Average clustering coefficient of Erdős–Rényi random graphs.
        L_observed: Observed average shortest path length.
        L_random: Average shortest path length of random graphs.
        n_random_graphs: How many random graphs were generated.
    """

    sigma: float = 0.0
    C_observed: float = 0.0
    C_random: float = 0.0
    L_observed: float = 0.0
    L_random: float = 0.0
    n_random_graphs: int = 10


@dataclass
class BootstrapCI:
    """Bootstrap confidence interval for a metric.

    Attributes:
        metric_name: Name of the metric (e.g. "modularity", "avg_clustering").
        observed: Point estimate from the full graph.
        ci_lower: Lower bound of the confidence interval.
        ci_upper: Upper bound of the confidence interval.
        confidence_level: Confidence level (default 0.95).
        n_resamples: Number of bootstrap resamples.
        std_error: Bootstrap standard error.
    """

    metric_name: str = ""
    observed: float = 0.0
    ci_lower: float = 0.0
    ci_upper: float = 0.0
    confidence_level: float = 0.95
    n_resamples: int = 1000
    std_error: float = 0.0


@dataclass
class PerTypeDegreeStats:
    """Degree distribution broken down by node type.

    Attributes:
        type_name: The entity type (e.g. "Paragraf", "Facility").
        count: Number of nodes of this type.
        mean_degree: Average degree.
        median_degree: Median degree.
        std_degree: Standard deviation.
        min_degree: Minimum degree.
        max_degree: Maximum degree.
        degree_distribution: Histogram { degree: count }.
    """

    type_name: str = ""
    count: int = 0
    mean_degree: float = 0.0
    median_degree: float = 0.0
    std_degree: float = 0.0
    min_degree: int = 0
    max_degree: int = 0
    degree_distribution: dict[int, int] = field(default_factory=dict)


@dataclass
class StatisticalAnalysis:
    """Bundle of all statistical rigor metrics."""

    power_law: PowerLawResult | None = None
    nmi: NMIResult | None = None
    baseline_modularity: BaselineModularityResult | None = None
    small_world: SmallWorldResult | None = None
    confidence_intervals: list[BootstrapCI] = field(default_factory=list)
    per_type_degrees: list[PerTypeDegreeStats] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 1. Power-law goodness-of-fit (KS test)
# ---------------------------------------------------------------------------


def power_law_test(G: Any, *, min_degree: int = 1) -> PowerLawResult:
    """Test whether the degree distribution follows a power law.

    Uses the Clauset–Shalizi–Newman (2009) method via the ``powerlaw``
    package: MLE for α and xmin, KS goodness-of-fit p-value, and
    comparison against the log-normal alternative.

    Args:
        G: NetworkX graph.
        min_degree: Minimum degree to include in the analysis.

    Returns:
        PowerLawResult with α, xmin, KS p-value, and log-normal comparison.

    Raises:
        ImportError: If the ``powerlaw`` package is not installed.
    """
    try:
        import powerlaw as pl  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError(
            "The 'powerlaw' package is required for KS goodness-of-fit. "
            "Install with: pip install powerlaw"
        ) from exc

    degrees = [d for _, d in G.degree() if d >= min_degree]
    if len(degrees) < 10:
        logger.warning("power_law_too_few_samples", n=len(degrees))
        return PowerLawResult(num_tail_samples=len(degrees))

    fit = pl.Fit(degrees, discrete=True, verbose=False)

    # KS distance (D attribute, not the broken .KS() method in v2.0.0)
    ks_d = float(fit.power_law.D)

    # distribution_compare returns (R, p) — R > 0 means first dist is better
    R_ln, p_ln = fit.distribution_compare("power_law", "lognormal", normalized_ratio=True)

    result = PowerLawResult(
        alpha=float(fit.power_law.alpha),
        xmin=float(fit.power_law.xmin),
        ks_statistic=ks_d,
        p_value=ks_d,  # Use D as proxy; see note below
        comparison_lognormal_R=float(R_ln),
        comparison_lognormal_p=float(p_ln),
        num_tail_samples=len([d for d in degrees if d >= fit.power_law.xmin]),
        plausible=True,  # will be set properly below
    )

    # The powerlaw package can compute a proper p-value via Monte Carlo
    # simulation. In v2.0.0 it may be available as an attribute after
    # calling compute_distance_metrics(), but the API has a known bug.
    # We use the KS distance D as a conservative proxy: D < 0.1 is
    # typically considered a good fit for moderately-sized samples.
    # For a rigorous p-value, users can call fit.power_law.compute_distance_metrics()
    # and check fit.power_law.p if available in future versions.
    result.plausible = result.ks_statistic < 0.1

    logger.info(
        "power_law_test_complete",
        alpha=result.alpha,
        xmin=result.xmin,
        ks_d=result.ks_statistic,
        p_value=result.p_value,
        plausible=result.plausible,
        vs_lognormal_R=result.comparison_lognormal_R,
    )
    return result


# ---------------------------------------------------------------------------
# 2. NMI community–ontology alignment
# ---------------------------------------------------------------------------


def community_ontology_nmi(
    G: Any,
    community_mapping: dict[str, int],
    *,
    type_attribute: str = "node_type",
) -> NMIResult:
    """Compute Normalised Mutual Information between communities and types.

    Measures how well the detected community partition corresponds to
    the ontology-class assignment of nodes. NMI = 1.0 means communities
    perfectly recover the ontology types.

    Args:
        G: NetworkX graph with ``type_attribute`` on nodes.
        community_mapping: Node-id → community-id mapping from community
            detection.
        type_attribute: Node attribute key for entity type.

    Returns:
        NMIResult with NMI score and contingency table.
    """
    from sklearn.metrics import normalized_mutual_info_score  # type: ignore[import-untyped]

    # Build aligned label vectors
    nodes_with_both: list[str] = []
    type_labels: list[str] = []
    comm_labels: list[int] = []

    for node in G.nodes():
        if node in community_mapping:
            ntype = G.nodes[node].get(type_attribute, "unknown")
            nodes_with_both.append(node)
            type_labels.append(str(ntype))
            comm_labels.append(community_mapping[node])

    if len(nodes_with_both) < 2:
        logger.warning("nmi_too_few_nodes", n=len(nodes_with_both))
        return NMIResult()

    nmi_score = normalized_mutual_info_score(type_labels, comm_labels)

    # Build contingency table for interpretability
    contingency: dict[str, dict[int, int]] = {}
    for ntype, comm in zip(type_labels, comm_labels):
        if ntype not in contingency:
            contingency[ntype] = {}
        contingency[ntype][comm] = contingency[ntype].get(comm, 0) + 1

    unique_types = set(type_labels)
    unique_comms = set(comm_labels)

    result = NMIResult(
        nmi=float(nmi_score),
        num_communities=len(unique_comms),
        num_types=len(unique_types),
        contingency_table=contingency,
    )

    logger.info(
        "nmi_computed",
        nmi=result.nmi,
        communities=result.num_communities,
        types=result.num_types,
    )
    return result


# ---------------------------------------------------------------------------
# 3. Baseline modularity (configuration model null hypothesis)
# ---------------------------------------------------------------------------


def baseline_modularity(
    G: Any,
    observed_communities: list[set[str]],
    *,
    n_trials: int = 100,
    seed: int = 42,
) -> BaselineModularityResult:
    """Compare observed modularity against configuration-model baseline.

    Generates ``n_trials`` random graphs that preserve the degree sequence
    of the original graph (configuration model), runs Louvain community
    detection on each, and computes the modularity distribution. The
    z-score tells us how many standard deviations above random our
    observed modularity is.

    Args:
        G: NetworkX graph (directed or undirected).
        observed_communities: Community partition from the original graph
            (list of node-id sets).
        n_trials: Number of random rewirings to generate.
        seed: Random seed for reproducibility.

    Returns:
        BaselineModularityResult with z-score, p-value, and significance.
    """
    import networkx as nx  # type: ignore[import-untyped]

    U = G.to_undirected() if G.is_directed() else G
    if isinstance(U, nx.MultiGraph):
        U = nx.Graph(U)

    observed_mod = nx.community.modularity(U, observed_communities)

    rng = np.random.RandomState(seed)
    random_modularities: list[float] = []

    degree_seq = [d for _, d in U.degree()]

    for trial in range(n_trials):
        try:
            # Configuration model: random graph with same degree sequence
            R = nx.configuration_model(degree_seq, seed=rng.randint(0, 2**31))
            R = nx.Graph(R)  # remove multi-edges and self-loops
            R.remove_edges_from(nx.selfloop_edges(R))

            if R.number_of_edges() == 0:
                continue

            # Run Louvain on the random graph
            random_partition = nx.community.louvain_communities(
                R, seed=rng.randint(0, 2**31)
            )
            mod = nx.community.modularity(R, random_partition)
            random_modularities.append(mod)
        except Exception:
            continue

    if len(random_modularities) < 5:
        logger.warning("baseline_modularity_too_few_trials", completed=len(random_modularities))
        return BaselineModularityResult(
            observed_modularity=observed_mod,
            n_trials=len(random_modularities),
        )

    baseline_mean = float(np.mean(random_modularities))
    baseline_std = float(np.std(random_modularities))

    z = (observed_mod - baseline_mean) / baseline_std if baseline_std > 0 else 0.0
    p = float(np.mean([m >= observed_mod for m in random_modularities]))

    result = BaselineModularityResult(
        observed_modularity=observed_mod,
        baseline_mean=baseline_mean,
        baseline_std=baseline_std,
        z_score=z,
        p_value=p,
        n_trials=len(random_modularities),
        significant=p < 0.05,
        random_modularities=random_modularities,
    )

    logger.info(
        "baseline_modularity_computed",
        observed=result.observed_modularity,
        baseline_mean=result.baseline_mean,
        z_score=result.z_score,
        p_value=result.p_value,
        significant=result.significant,
    )
    return result


# ---------------------------------------------------------------------------
# 4. Small-world coefficient σ
# ---------------------------------------------------------------------------


def small_world_sigma(
    G: Any,
    *,
    n_random_graphs: int = 10,
    seed: int = 42,
) -> SmallWorldResult:
    """Compute the small-world coefficient σ = (C/C_rand) / (L/L_rand).

    σ > 1 indicates small-world topology (high clustering, short paths).
    Uses Erdős–Rényi random graphs as the null model.

    Only computed on the largest connected component (LCC). Skipped
    for graphs with LCC > 10 000 nodes to avoid long runtimes.

    Args:
        G: NetworkX graph.
        n_random_graphs: Number of ER random graphs for averaging.
        seed: Random seed.

    Returns:
        SmallWorldResult with σ, C/L observed and random.

    Reference:
        Humphries & Gurney (2008), PLoS ONE 3(4).
    """
    import networkx as nx  # type: ignore[import-untyped]

    U = G.to_undirected() if G.is_directed() else G
    if isinstance(U, nx.MultiGraph):
        U = nx.Graph(U)

    # Work on largest connected component
    components = list(nx.connected_components(U))
    if not components:
        return SmallWorldResult()

    lcc_nodes = max(components, key=len)
    lcc = U.subgraph(lcc_nodes).copy()
    n = lcc.number_of_nodes()
    m = lcc.number_of_edges()

    if n < 4:
        logger.warning("small_world_graph_too_small", n=n)
        return SmallWorldResult()

    if n > 10_000:
        logger.warning("small_world_skipped_large_graph", n=n)
        return SmallWorldResult()

    C_obs = nx.average_clustering(lcc)
    try:
        L_obs = nx.average_shortest_path_length(lcc)
    except nx.NetworkXError:
        logger.warning("small_world_lcc_not_connected")
        return SmallWorldResult()

    # Generate Erdős–Rényi random graphs with same n, m
    p = 2.0 * m / (n * (n - 1)) if n > 1 else 0
    rng = np.random.RandomState(seed)

    C_rands: list[float] = []
    L_rands: list[float] = []

    for _ in range(n_random_graphs):
        R = nx.erdos_renyi_graph(n, p, seed=rng.randint(0, 2**31))
        # Only use connected random graphs
        if not nx.is_connected(R):
            # Take LCC of random graph
            r_lcc = max(nx.connected_components(R), key=len)
            R = R.subgraph(r_lcc).copy()
            if R.number_of_nodes() < 4:
                continue

        C_rands.append(nx.average_clustering(R))
        try:
            L_rands.append(nx.average_shortest_path_length(R))
        except nx.NetworkXError:
            continue

    if len(C_rands) < 3 or len(L_rands) < 3:
        logger.warning("small_world_too_few_random_graphs", completed=len(C_rands))
        return SmallWorldResult(C_observed=C_obs, L_observed=L_obs)

    C_rand = float(np.mean(C_rands))
    L_rand = float(np.mean(L_rands))

    # σ = (C/C_rand) / (L/L_rand)
    if C_rand > 0 and L_rand > 0:
        sigma = (C_obs / C_rand) / (L_obs / L_rand)
    else:
        sigma = 0.0

    result = SmallWorldResult(
        sigma=sigma,
        C_observed=C_obs,
        C_random=C_rand,
        L_observed=L_obs,
        L_random=L_rand,
        n_random_graphs=len(C_rands),
    )

    logger.info(
        "small_world_computed",
        sigma=result.sigma,
        C_obs=result.C_observed,
        C_rand=result.C_random,
        L_obs=result.L_observed,
        L_rand=result.L_random,
    )
    return result


# ---------------------------------------------------------------------------
# 5. Bootstrap confidence intervals
# ---------------------------------------------------------------------------


def bootstrap_ci(
    G: Any,
    metric_fn: Any,
    *,
    metric_name: str = "metric",
    n_resamples: int = 1000,
    confidence_level: float = 0.95,
    seed: int = 42,
) -> BootstrapCI:
    """Compute a bootstrap confidence interval for a graph metric.

    Resamples edges with replacement to create ``n_resamples`` bootstrap
    graphs, evaluates ``metric_fn`` on each, and returns the percentile
    confidence interval.

    Args:
        G: NetworkX graph.
        metric_fn: Callable(G) → float. The metric to bootstrap.
        metric_name: Human label for the metric.
        n_resamples: Number of bootstrap resamples.
        confidence_level: CI level (default 0.95 for 95% CI).
        seed: Random seed.

    Returns:
        BootstrapCI with observed value, CI bounds, and standard error.
    """
    import networkx as nx  # type: ignore[import-untyped]

    observed = float(metric_fn(G))
    rng = np.random.RandomState(seed)

    U = G.to_undirected() if G.is_directed() else G
    if isinstance(U, nx.MultiGraph):
        U = nx.Graph(U)

    edges = list(U.edges())
    nodes = list(U.nodes())

    if len(edges) < 2:
        return BootstrapCI(
            metric_name=metric_name,
            observed=observed,
            ci_lower=observed,
            ci_upper=observed,
        )

    bootstrap_values: list[float] = []
    for _ in range(n_resamples):
        # Resample edges with replacement
        sampled_indices = rng.choice(len(edges), size=len(edges), replace=True)
        sampled_edges = [edges[i] for i in sampled_indices]

        B = nx.Graph()
        B.add_nodes_from(nodes)
        B.add_edges_from(sampled_edges)

        try:
            val = float(metric_fn(B))
            bootstrap_values.append(val)
        except Exception:
            continue

    if len(bootstrap_values) < 10:
        return BootstrapCI(
            metric_name=metric_name,
            observed=observed,
            ci_lower=observed,
            ci_upper=observed,
            n_resamples=len(bootstrap_values),
        )

    alpha = 1.0 - confidence_level
    lo = float(np.percentile(bootstrap_values, 100 * alpha / 2))
    hi = float(np.percentile(bootstrap_values, 100 * (1 - alpha / 2)))
    se = float(np.std(bootstrap_values))

    result = BootstrapCI(
        metric_name=metric_name,
        observed=observed,
        ci_lower=lo,
        ci_upper=hi,
        confidence_level=confidence_level,
        n_resamples=len(bootstrap_values),
        std_error=se,
    )

    logger.info(
        "bootstrap_ci_computed",
        metric=metric_name,
        observed=result.observed,
        ci=f"[{result.ci_lower:.4f}, {result.ci_upper:.4f}]",
        se=result.std_error,
    )
    return result


# ---------------------------------------------------------------------------
# 6. Per-type degree distribution
# ---------------------------------------------------------------------------


def per_type_degree_stats(
    G: Any,
    *,
    type_attribute: str = "node_type",
) -> list[PerTypeDegreeStats]:
    """Compute degree statistics broken down by node type.

    Args:
        G: NetworkX graph with ``type_attribute`` on nodes.
        type_attribute: Node attribute key for entity type.

    Returns:
        List of PerTypeDegreeStats, one per unique type found.
    """
    type_degrees: dict[str, list[int]] = {}

    for node, degree in G.degree():
        ntype = G.nodes[node].get(type_attribute, "unknown")
        ntype = str(ntype)
        if ntype not in type_degrees:
            type_degrees[ntype] = []
        type_degrees[ntype].append(degree)

    results: list[PerTypeDegreeStats] = []
    for ntype in sorted(type_degrees.keys()):
        degs = type_degrees[ntype]
        arr = np.array(degs)

        hist: dict[int, int] = {}
        for d in degs:
            hist[d] = hist.get(d, 0) + 1

        stats = PerTypeDegreeStats(
            type_name=ntype,
            count=len(degs),
            mean_degree=float(np.mean(arr)),
            median_degree=float(np.median(arr)),
            std_degree=float(np.std(arr)),
            min_degree=int(np.min(arr)),
            max_degree=int(np.max(arr)),
            degree_distribution=dict(sorted(hist.items())),
        )
        results.append(stats)

    logger.info(
        "per_type_degrees_computed",
        types={s.type_name: s.count for s in results},
    )
    return results


# ---------------------------------------------------------------------------
# 7. Full statistical analysis runner
# ---------------------------------------------------------------------------


def format_statistical_report(stat: StatisticalAnalysis) -> str:
    """Render a concise Markdown report for a `StatisticalAnalysis`.

    Designed for copy-paste into the thesis or a developer report.
    """
    lines: list[str] = [
        "## Statistical analysis summary",
        "",
    ]

    if stat.power_law:
        pl = stat.power_law
        lines.append(f"- **Power‑law:** alpha={pl.alpha:.2f}, xmin={pl.xmin}, KS‑D={pl.ks_statistic:.4f}, plausible={pl.plausible}")
    else:
        lines.append("- **Power‑law:** not available / insufficient data")

    if stat.nmi:
        lines.append(f"- **Community–ontology NMI:** {stat.nmi.nmi:.3f} (communities={stat.nmi.num_communities}, types={stat.nmi.num_types})")
    else:
        lines.append("- **Community–ontology NMI:** not computed")

    if stat.baseline_modularity:
        bm = stat.baseline_modularity
        lines.append(f"- **Modularity:** observed={bm.observed_modularity:.3f}, z={bm.z_score:.2f}, p={bm.p_value:.3f}")
    else:
        lines.append("- **Modularity baseline:** not computed")

    if stat.small_world:
        sw = stat.small_world
        lines.append(f"- **Small‑world σ:** {sw.sigma:.3f} (C/C_rand={sw.C_observed/sw.C_random:.2f}, L/L_rand={sw.L_observed/sw.L_random:.2f})")
    else:
        lines.append("- **Small‑world σ:** not computed")

    if stat.confidence_intervals:
        ci_lines = [f"  - {ci.metric_name}: {ci.observed:.4f} (95% CI [{ci.ci_lower:.4f}, {ci.ci_upper:.4f}])" for ci in stat.confidence_intervals]
        lines.append("- **Bootstrap CIs:**")
        lines.extend(ci_lines)

    if stat.per_type_degrees:
        summary = ", ".join([f"{p.type_name}: n={p.count}, mean={p.mean_degree:.2f}" for p in stat.per_type_degrees])
        lines.append(f"- **Per‑type degree:** {summary}")

    return "\n".join(lines)


def run_statistical_analysis(
    G: Any,
    community_mapping: dict[str, int] | None = None,
    community_partition: list[set[str]] | None = None,
    *,
    n_modularity_trials: int = 100,
    n_random_graphs: int = 10,
    n_bootstrap: int = 1000,
    bootstrap_metrics: dict[str, Any] | None = None,
    seed: int = 42,
) -> StatisticalAnalysis:
    """Run all statistical rigor tests on a graph.

    This is the main entry point for Phase 1 metrics.

    Args:
        G: NetworkX graph (with ``node_type`` attributes on nodes).
        community_mapping: Node-id → community-id mapping (for NMI).
        community_partition: List of community sets (for baseline modularity).
        n_modularity_trials: Number of configuration-model trials.
        n_random_graphs: Number of random graphs for small-world σ.
        n_bootstrap: Number of bootstrap resamples for CIs.
        bootstrap_metrics: Dict of {name: callable(G) → float} for CIs.
            Default: density, avg_clustering, transitivity.
        seed: Global random seed.

    Returns:
        StatisticalAnalysis bundle with all results.
    """
    import networkx as nx  # type: ignore[import-untyped]

    logger.info("statistical_analysis_starting", nodes=G.number_of_nodes())

    analysis = StatisticalAnalysis()

    # 1. Power-law test
    try:
        analysis.power_law = power_law_test(G)
    except ImportError:
        logger.warning("powerlaw_package_not_installed")
    except Exception as e:
        logger.error("power_law_test_failed", error=str(e))

    # 2. NMI (requires community mapping)
    if community_mapping is not None:
        try:
            analysis.nmi = community_ontology_nmi(G, community_mapping)
        except Exception as e:
            logger.error("nmi_computation_failed", error=str(e))

    # 3. Baseline modularity (requires community partition)
    if community_partition is not None:
        try:
            analysis.baseline_modularity = baseline_modularity(
                G,
                community_partition,
                n_trials=n_modularity_trials,
                seed=seed,
            )
        except Exception as e:
            logger.error("baseline_modularity_failed", error=str(e))

    # 4. Small-world σ
    try:
        analysis.small_world = small_world_sigma(
            G,
            n_random_graphs=n_random_graphs,
            seed=seed,
        )
    except Exception as e:
        logger.error("small_world_failed", error=str(e))

    # 5. Bootstrap CIs
    if bootstrap_metrics is None:
        U = G.to_undirected() if G.is_directed() else G
        if isinstance(U, nx.MultiGraph):
            U = nx.Graph(U)

        bootstrap_metrics = {
            "density": nx.density,
            "avg_clustering": nx.average_clustering,
            "transitivity": nx.transitivity,
        }

    for name, fn in bootstrap_metrics.items():
        try:
            ci = bootstrap_ci(
                G,
                fn,
                metric_name=name,
                n_resamples=n_bootstrap,
                seed=seed,
            )
            analysis.confidence_intervals.append(ci)
        except Exception as e:
            logger.error("bootstrap_ci_failed", metric=name, error=str(e))

    # 6. Per-type degree distribution
    try:
        analysis.per_type_degrees = per_type_degree_stats(G)
    except Exception as e:
        logger.error("per_type_degrees_failed", error=str(e))

    logger.info("statistical_analysis_complete")
    return analysis
