"""Structural graph analytics: centrality, communities, topology.

Converts a GraphStore to a NetworkX graph and computes:
- Centrality measures (degree, betweenness, closeness, PageRank, eigenvector,
  non-backtracking / Hashimoto)
- Community detection (Louvain, label propagation, spectral)
- Topological statistics (diameter, clustering coefficient, component analysis,
  degree distribution, power-law fit, small-world sigma)
- Hub/authority analysis (HITS)

All algorithms operate on a NetworkX DiGraph snapshot so they work
with *any* GraphStore backend (InMemory, Neo4j, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Lazy imports — heavy deps loaded on first use
# ---------------------------------------------------------------------------

_nx = None  # type: Any


def _ensure_nx() -> Any:
    global _nx
    if _nx is None:
        try:
            import networkx as nx  # type: ignore[import-untyped]
            _nx = nx
        except ImportError as exc:
            raise ImportError(
                "networkx is required for structural analytics. "
                "Install it with: pip install networkx[default]"
            ) from exc
    return _nx


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------


@dataclass
class CentralityResult:
    """Centrality scores for every node, plus aggregate statistics."""

    measure: str  # e.g. "pagerank", "betweenness"
    scores: dict[str, float] = field(default_factory=dict)
    top_k: list[tuple[str, float]] = field(default_factory=list)

    # Aggregate stats
    mean: float = 0.0
    std: float = 0.0
    max_node: str = ""
    max_value: float = 0.0
    gini: float = 0.0  # inequality measure

    def compute_stats(self, k: int = 20) -> None:
        """Compute aggregate statistics from per-node scores."""
        if not self.scores:
            return
        vals = np.array(list(self.scores.values()))
        self.mean = float(np.mean(vals))
        self.std = float(np.std(vals))
        sorted_items = sorted(self.scores.items(), key=lambda x: x[1], reverse=True)
        self.top_k = sorted_items[:k]
        if self.top_k:
            self.max_node, self.max_value = self.top_k[0]
        # Gini coefficient
        if len(vals) > 0 and np.sum(vals) > 0:
            sorted_vals = np.sort(vals)
            n = len(sorted_vals)
            index = np.arange(1, n + 1)
            self.gini = float(
                (2 * np.sum(index * sorted_vals) - (n + 1) * np.sum(sorted_vals))
                / (n * np.sum(sorted_vals))
            )


@dataclass
class CommunityResult:
    """Community detection result."""

    algorithm: str  # "louvain", "label_propagation", "spectral"
    num_communities: int = 0
    node_to_community: dict[str, int] = field(default_factory=dict)
    community_sizes: list[int] = field(default_factory=list)
    modularity: float = 0.0


@dataclass
class TopologyResult:
    """Topological statistics of the graph."""

    num_nodes: int = 0
    num_edges: int = 0
    density: float = 0.0
    num_connected_components: int = 0
    largest_component_size: int = 0
    largest_component_fraction: float = 0.0
    diameter: int | None = None  # only for largest connected component
    avg_shortest_path: float | None = None
    avg_clustering: float = 0.0
    transitivity: float = 0.0
    reciprocity: float = 0.0
    degree_assortativity: float | None = None
    avg_degree: float = 0.0
    degree_distribution: dict[int, int] = field(default_factory=dict)
    power_law_exponent: float | None = None
    small_world_sigma: float | None = None

    # --- Phase-1 statistical rigor additions ---
    power_law_ks_p: float | None = None  # KS goodness-of-fit p-value
    power_law_plausible: bool | None = None  # p ≥ 0.1 → plausible


@dataclass
class StructuralAnalysis:
    """Complete structural analytics bundle."""

    topology: TopologyResult = field(default_factory=TopologyResult)
    centralities: dict[str, CentralityResult] = field(default_factory=dict)
    communities: dict[str, CommunityResult] = field(default_factory=dict)
    hubs: list[str] = field(default_factory=list)
    authorities: list[str] = field(default_factory=list)
    bridges: list[tuple[str, str]] = field(default_factory=list)

    # Phase-1 statistical rigor — populated by run_structural_analysis
    statistical: Any = None  # StatisticalAnalysis (lazy import to avoid circular)


# ---------------------------------------------------------------------------
# Converter: GraphStore → NetworkX
# ---------------------------------------------------------------------------


def graph_store_to_networkx(store: Any) -> Any:
    """Convert any GraphStore to a NetworkX MultiDiGraph.

    Uses MultiDiGraph because knowledge graphs are multi-relational:
    the same (source, target) pair can have multiple edges with
    different relation types.

    Node attributes preserved: node_type, label, properties.*
    Edge attributes preserved: edge_type, properties.*
    """
    nx = _ensure_nx()
    G = nx.MultiDiGraph()

    for node in store.get_all_nodes():
        attrs: dict[str, Any] = {
            "node_type": node.node_type,
            "label": node.label,
        }
        attrs.update(node.properties)
        G.add_node(node.id, **attrs)

    for edge in store.get_all_edges():
        attrs = {"edge_type": edge.edge_type}
        attrs.update(edge.properties)
        G.add_edge(edge.source_id, edge.target_id, key=edge.id, **attrs)

    return G


# ---------------------------------------------------------------------------
# Centrality
# ---------------------------------------------------------------------------


def compute_centralities(
    G: Any,
    measures: list[str] | None = None,
    top_k: int = 20,
) -> dict[str, CentralityResult]:
    """Compute multiple centrality measures.

    Args:
        G: NetworkX DiGraph.
        measures: Subset of measures to compute. Default: all.
            Available: degree, in_degree, out_degree, betweenness,
            closeness, pagerank, eigenvector, hits_hub, hits_authority,
            non_backtracking.
        top_k: Number of top nodes to retain per measure.

    Returns:
        Dict mapping measure name → CentralityResult.
    """
    nx = _ensure_nx()
    if measures is None:
        measures = [
            "degree", "in_degree", "out_degree",
            "betweenness", "closeness", "pagerank",
            "eigenvector", "hits_hub", "hits_authority",
            "non_backtracking",
        ]

    results: dict[str, CentralityResult] = {}

    for m in measures:
        try:
            scores = _compute_one_centrality(G, m, nx)
            cr = CentralityResult(measure=m, scores=scores)
            cr.compute_stats(k=top_k)
            results[m] = cr
        except Exception as e:
            logger.warning("centrality_computation_failed", measure=m, error=str(e))

    return results


def _compute_one_centrality(G: Any, measure: str, nx: Any) -> dict[str, float]:  # noqa: C901
    """Dispatch centrality computation to the right algorithm."""
    n = G.number_of_nodes()
    if n == 0:
        return {}

    if measure == "degree":
        return {v: d / max(n - 1, 1) for v, d in G.degree()}
    elif measure == "in_degree":
        return {v: d / max(n - 1, 1) for v, d in G.in_degree()}
    elif measure == "out_degree":
        return {v: d / max(n - 1, 1) for v, d in G.out_degree()}
    elif measure == "betweenness":
        return nx.betweenness_centrality(G, normalized=True)
    elif measure == "closeness":
        return nx.closeness_centrality(G)
    elif measure == "pagerank":
        return nx.pagerank(G, alpha=0.85)
    elif measure == "eigenvector":
        # Eigenvector centrality on undirected projection
        U = G.to_undirected()
        if isinstance(U, nx.MultiGraph):
            U = nx.Graph(U)
        try:
            return nx.eigenvector_centrality(U, max_iter=500, tol=1e-06)
        except nx.PowerIterationFailedConvergence:
            return nx.eigenvector_centrality_numpy(U)
    elif measure == "hits_hub":
        hubs, _auth = nx.hits(G, max_iter=500, tol=1e-06)
        return hubs
    elif measure == "hits_authority":
        _hubs, auth = nx.hits(G, max_iter=500, tol=1e-06)
        return auth
    elif measure == "non_backtracking":
        return _non_backtracking_centrality(G, nx)
    else:
        raise ValueError(f"Unknown centrality measure: {measure}")


def _non_backtracking_centrality(G: Any, nx: Any) -> dict[str, float]:
    """Non-backtracking (Hashimoto) centrality via the NB matrix.

    The non-backtracking matrix avoids the localization problem of
    standard eigenvector centrality in networks with hubs. Its leading
    eigenvector gives a better ranking in sparse, heterogeneous graphs
    typical of KGs.
    """
    from scipy import sparse as sp  # type: ignore[import-untyped]
    from scipy.sparse.linalg import eigs  # type: ignore[import-untyped]

    U = G.to_undirected()
    if isinstance(U, nx.MultiGraph):
        U = nx.Graph(U)
    edges = list(U.edges())
    if not edges:
        return {v: 0.0 for v in G.nodes()}

    # Build directed edge list (both orientations for each undirected edge)
    directed_edges: list[tuple[str, str]] = []
    for u, v in edges:
        directed_edges.append((u, v))
        directed_edges.append((v, u))

    edge_index = {e: i for i, e in enumerate(directed_edges)}
    m = len(directed_edges)

    # Build the Hashimoto (non-backtracking) matrix B
    # B[e1, e2] = 1 if target(e1) == source(e2) and source(e1) != target(e2)
    rows, cols = [], []
    for i, (u1, v1) in enumerate(directed_edges):
        for j, (u2, v2) in enumerate(directed_edges):
            if v1 == u2 and u1 != v2:
                rows.append(i)
                cols.append(j)

    if not rows:
        return {v: 0.0 for v in G.nodes()}

    B = sp.csr_matrix(
        (np.ones(len(rows)), (rows, cols)),
        shape=(m, m),
    )

    # Leading eigenvector
    try:
        eigenvalues, eigenvectors = eigs(B.astype(float), k=1, which="LM")
        leading = np.abs(eigenvectors[:, 0]).real
    except Exception:
        return {v: 0.0 for v in G.nodes()}

    # Aggregate: for each node, sum over directed edges starting from it
    node_scores: dict[str, float] = {v: 0.0 for v in G.nodes()}
    for i, (u, _v) in enumerate(directed_edges):
        node_scores[u] += leading[i]

    # Normalise
    max_score = max(node_scores.values()) if node_scores else 1.0
    if max_score > 0:
        node_scores = {v: s / max_score for v, s in node_scores.items()}

    return node_scores


# ---------------------------------------------------------------------------
# Community Detection
# ---------------------------------------------------------------------------


def detect_communities(
    G: Any,
    algorithms: list[str] | None = None,
) -> dict[str, CommunityResult]:
    """Run community detection algorithms on the graph.

    Args:
        G: NetworkX DiGraph (will be converted to undirected internally).
        algorithms: Subset to run. Default: all available.
            Available: louvain, label_propagation, greedy_modularity.

    Returns:
        Dict mapping algorithm name → CommunityResult.
    """
    nx = _ensure_nx()

    if algorithms is None:
        algorithms = ["louvain", "label_propagation", "greedy_modularity"]

    U = G.to_undirected()
    # Community algorithms need simple Graph, not MultiGraph
    if isinstance(U, nx.MultiGraph):
        U = nx.Graph(U)
    results: dict[str, CommunityResult] = {}

    for alg in algorithms:
        try:
            result = _detect_one_community(U, alg, nx)
            results[alg] = result
        except Exception as e:
            logger.warning("community_detection_failed", algorithm=alg, error=str(e))

    return results


def _detect_one_community(U: Any, algorithm: str, nx: Any) -> CommunityResult:
    """Run a single community detection algorithm."""
    if algorithm == "louvain":
        partition = nx.community.louvain_communities(U, seed=42)
        node_to_comm = _communities_to_mapping(partition)
        mod = nx.community.modularity(U, partition)
        return CommunityResult(
            algorithm="louvain",
            num_communities=len(partition),
            node_to_community=node_to_comm,
            community_sizes=sorted([len(c) for c in partition], reverse=True),
            modularity=mod,
        )
    elif algorithm == "label_propagation":
        partition = list(nx.community.label_propagation_communities(U))
        node_to_comm = _communities_to_mapping(partition)
        mod = nx.community.modularity(U, partition)
        return CommunityResult(
            algorithm="label_propagation",
            num_communities=len(partition),
            node_to_community=node_to_comm,
            community_sizes=sorted([len(c) for c in partition], reverse=True),
            modularity=mod,
        )
    elif algorithm == "greedy_modularity":
        partition = list(nx.community.greedy_modularity_communities(U))
        node_to_comm = _communities_to_mapping(partition)
        mod = nx.community.modularity(U, partition)
        return CommunityResult(
            algorithm="greedy_modularity",
            num_communities=len(partition),
            node_to_community=node_to_comm,
            community_sizes=sorted([len(c) for c in partition], reverse=True),
            modularity=mod,
        )
    else:
        raise ValueError(f"Unknown community algorithm: {algorithm}")


def _communities_to_mapping(partition: list[set[str]]) -> dict[str, int]:
    """Convert a list-of-sets partition to a node→community-id mapping."""
    mapping: dict[str, int] = {}
    for comm_id, members in enumerate(partition):
        for node in members:
            mapping[node] = comm_id
    return mapping


# ---------------------------------------------------------------------------
# Topology
# ---------------------------------------------------------------------------


def compute_topology(G: Any) -> TopologyResult:
    """Compute topological statistics of the graph."""
    nx = _ensure_nx()
    result = TopologyResult()

    n = G.number_of_nodes()
    e = G.number_of_edges()
    result.num_nodes = n
    result.num_edges = e
    result.density = nx.density(G)

    if n == 0:
        return result

    # Degree statistics
    degrees = [d for _, d in G.degree()]
    result.avg_degree = float(np.mean(degrees)) if degrees else 0.0
    deg_dist: dict[int, int] = {}
    for d in degrees:
        deg_dist[d] = deg_dist.get(d, 0) + 1
    result.degree_distribution = dict(sorted(deg_dist.items()))

    # Power-law exponent (simple MLE on degree ≥ 1)
    pos_degrees = [d for d in degrees if d >= 1]
    if len(pos_degrees) > 5:
        result.power_law_exponent = 1.0 + len(pos_degrees) / float(
            np.sum(np.log(np.array(pos_degrees, dtype=float)))
        )

    # Connected components (on undirected projection)
    U = G.to_undirected()
    # Some algorithms need simple Graph, not MultiGraph
    U_simple = nx.Graph(U) if isinstance(U, nx.MultiGraph) else U

    components = list(nx.connected_components(U_simple))
    result.num_connected_components = len(components)
    if components:
        largest = max(components, key=len)
        result.largest_component_size = len(largest)
        result.largest_component_fraction = len(largest) / n

        # Diameter and avg path length on largest component
        if len(largest) <= 10_000:  # skip for very large graphs
            lcc = U_simple.subgraph(largest)
            try:
                result.diameter = nx.diameter(lcc)
                result.avg_shortest_path = nx.average_shortest_path_length(lcc)
            except nx.NetworkXError:
                pass

    # Clustering (requires simple undirected graph)
    result.avg_clustering = nx.average_clustering(U_simple)
    result.transitivity = nx.transitivity(U_simple)
    result.reciprocity = nx.reciprocity(G)

    # Assortativity
    try:
        result.degree_assortativity = nx.degree_assortativity_coefficient(G)
    except (nx.NetworkXError, ValueError):
        result.degree_assortativity = None

    return result


# ---------------------------------------------------------------------------
# Bridge / Articulation analysis
# ---------------------------------------------------------------------------


def find_bridges_and_articulation(G: Any) -> tuple[list[tuple[str, str]], list[str]]:
    """Find bridge edges and articulation points (undirected projection)."""
    nx = _ensure_nx()
    U = G.to_undirected()
    # nx.bridges/articulation_points require simple Graph, not MultiGraph
    if isinstance(U, nx.MultiGraph):
        U = nx.Graph(U)
    bridges = list(nx.bridges(U))
    articulation = list(nx.articulation_points(U))
    return bridges, articulation


# ---------------------------------------------------------------------------
# Full Analysis
# ---------------------------------------------------------------------------


def run_structural_analysis(
    store: Any,
    centrality_measures: list[str] | None = None,
    community_algorithms: list[str] | None = None,
    top_k: int = 20,
) -> StructuralAnalysis:
    """Run complete structural analysis on a GraphStore.

    This is the main entry point. Converts the store to NetworkX,
    then runs topology, centrality, community detection, and
    bridge analysis.

    Args:
        store: Any GraphStore (InMemoryGraphStore, Neo4jGraphStore, etc.)
        centrality_measures: Which centralities to compute (default: all).
        community_algorithms: Which community algorithms to run (default: all).
        top_k: Number of top nodes per centrality metric.

    Returns:
        StructuralAnalysis bundle with all results.
    """
    logger.info("structural_analysis_starting")

    G = graph_store_to_networkx(store)
    logger.info("graph_converted_to_networkx", nodes=G.number_of_nodes(), edges=G.number_of_edges())

    analysis = StructuralAnalysis()

    # Topology
    analysis.topology = compute_topology(G)
    logger.info(
        "topology_computed",
        nodes=analysis.topology.num_nodes,
        edges=analysis.topology.num_edges,
        components=analysis.topology.num_connected_components,
    )

    # Centrality
    analysis.centralities = compute_centralities(
        G, measures=centrality_measures, top_k=top_k
    )
    logger.info("centralities_computed", measures=list(analysis.centralities.keys()))

    # Extract top hubs and authorities
    if "hits_hub" in analysis.centralities:
        analysis.hubs = [n for n, _ in analysis.centralities["hits_hub"].top_k[:10]]
    if "hits_authority" in analysis.centralities:
        analysis.authorities = [
            n for n, _ in analysis.centralities["hits_authority"].top_k[:10]
        ]

    # Communities
    if G.number_of_nodes() > 2:
        analysis.communities = detect_communities(G, algorithms=community_algorithms)
        logger.info(
            "communities_detected",
            algorithms={k: v.num_communities for k, v in analysis.communities.items()},
        )

    # Bridges
    if G.number_of_nodes() > 2:
        bridges, _articulation = find_bridges_and_articulation(G)
        analysis.bridges = bridges[:50]  # cap for serialization

    # --- Phase-1: statistical rigor metrics ---
    try:
        from kgbuilder.analytics.statistical import run_statistical_analysis

        # Gather community info for NMI and baseline modularity
        comm_mapping: dict[str, int] | None = None
        comm_partition: list[set[str]] | None = None
        if "louvain" in analysis.communities:
            comm = analysis.communities["louvain"]
            comm_mapping = comm.node_to_community
            # Reconstruct partition from mapping
            from collections import defaultdict
            comm_sets: dict[int, set[str]] = defaultdict(set)
            for node, cid in comm_mapping.items():
                comm_sets[cid].add(node)
            comm_partition = list(comm_sets.values())

        stat = run_statistical_analysis(
            G,
            community_mapping=comm_mapping,
            community_partition=comm_partition,
            n_modularity_trials=100,
            n_random_graphs=10,
            n_bootstrap=500,
        )
        analysis.statistical = stat

        # Back-fill topology fields from statistical results
        if stat.power_law is not None:
            analysis.topology.power_law_ks_p = stat.power_law.p_value
            analysis.topology.power_law_plausible = stat.power_law.plausible
            # Use the proper powerlaw-package alpha if available
            if stat.power_law.alpha > 0:
                analysis.topology.power_law_exponent = stat.power_law.alpha

        if stat.small_world is not None and stat.small_world.sigma > 0:
            analysis.topology.small_world_sigma = stat.small_world.sigma

        logger.info(
            "statistical_analysis_integrated",
            power_law_plausible=analysis.topology.power_law_plausible,
            small_world_sigma=analysis.topology.small_world_sigma,
        )
    except Exception as e:
        logger.warning("statistical_analysis_skipped", error=str(e))

    logger.info("structural_analysis_complete")
    return analysis
