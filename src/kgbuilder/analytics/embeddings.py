"""Embedding space analytics: clustering, dimensionality reduction, comparison.

Compares semantic embeddings (from LLM/Ollama) with graph-structural
communities discovered by topology-based algorithms.  Key questions:

- Do semantically similar entities end up in the same structural community?
- Are there entities that are semantically close but structurally distant
  (or vice-versa)? What does that tell us about KG quality?
- How well does the embedding space preserve the graph neighbourhood?

Analytics provided:
- Cluster semantic embeddings (KMeans, HDBSCAN)
- Reduce dimensions for visualisation (PCA, t-SNE, UMAP)
- Compute cluster-to-community alignment (ARI, NMI, V-measure)
- Identify mismatches (entities in different groups)
- Embedding coherence score (avg intra-community cosine similarity)
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
class EmbeddingCluster:
    """Result of clustering embedding vectors."""

    algorithm: str  # "kmeans", "hdbscan"
    num_clusters: int = 0
    node_to_cluster: dict[str, int] = field(default_factory=dict)
    cluster_sizes: list[int] = field(default_factory=list)
    silhouette_score: float | None = None
    inertia: float | None = None  # KMeans only


@dataclass
class DimensionReduction:
    """2D / 3D projection of embedding vectors."""

    method: str  # "pca", "tsne", "umap"
    components: int = 2
    node_ids: list[str] = field(default_factory=list)
    coords: np.ndarray = field(default_factory=lambda: np.empty((0, 2)))
    explained_variance_ratio: list[float] = field(default_factory=list)  # PCA only

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dict."""
        return {
            "method": self.method,
            "components": self.components,
            "node_ids": self.node_ids,
            "coords": self.coords.tolist(),
            "explained_variance_ratio": self.explained_variance_ratio,
        }


@dataclass
class AlignmentResult:
    """Alignment between two partitions (e.g. clusters vs communities)."""

    partition_a_name: str
    partition_b_name: str
    adjusted_rand_index: float = 0.0
    normalized_mutual_info: float = 0.0
    v_measure: float = 0.0
    n_nodes_compared: int = 0
    mismatched_nodes: list[str] = field(default_factory=list)


@dataclass
class CoherenceResult:
    """Intra-group embedding coherence."""

    group_name: str
    group_type: str  # "community", "cluster", "node_type"
    mean_cosine_similarity: float = 0.0
    per_group: dict[str, float] = field(default_factory=dict)


@dataclass
class EmbeddingAnalysis:
    """Full embedding analytics bundle."""

    clusters: dict[str, EmbeddingCluster] = field(default_factory=dict)
    reductions: dict[str, DimensionReduction] = field(default_factory=dict)
    alignments: list[AlignmentResult] = field(default_factory=list)
    coherence: list[CoherenceResult] = field(default_factory=list)
    # Embedding matrix (node_ids aligned with rows)
    node_ids: list[str] = field(default_factory=list)
    embedding_matrix: np.ndarray = field(default_factory=lambda: np.empty((0, 0)))


# ---------------------------------------------------------------------------
# Embedding retrieval
# ---------------------------------------------------------------------------


def collect_embeddings(
    store: Any,
    embedding_provider: Any | None = None,
    embedding_key: str = "embedding",
) -> tuple[list[str], np.ndarray]:
    """Collect node embeddings from the graph store or via an embedding provider.

    Strategy:
    1. If nodes already have an ``embedding`` property, use that.
    2. Otherwise, call ``embedding_provider.embed_batch()`` on node labels.

    Returns:
        (node_ids, embedding_matrix) where matrix is (N, D).
    """
    node_ids: list[str] = []
    embeddings: list[np.ndarray] = []
    texts_to_embed: list[tuple[int, str]] = []

    for node in store.get_all_nodes():
        node_ids.append(node.id)
        emb = node.properties.get(embedding_key)
        if emb is not None:
            embeddings.append(np.array(emb, dtype=np.float32))
        else:
            embeddings.append(None)  # type: ignore[arg-type]
            text = node.label or node.properties.get("description", node.id)
            texts_to_embed.append((len(node_ids) - 1, text))

    # Fill missing embeddings via provider
    if texts_to_embed and embedding_provider is not None:
        logger.info("embedding_missing_nodes", count=len(texts_to_embed))
        batch_texts = [t for _, t in texts_to_embed]
        try:
            new_embeds = embedding_provider.embed_batch(batch_texts)
            for (idx, _text), emb in zip(texts_to_embed, new_embeds):
                embeddings[idx] = np.array(emb, dtype=np.float32)
        except Exception as e:
            logger.error("embedding_provider_failed", error=str(e))

    # Filter out nodes without embeddings
    valid_ids: list[str] = []
    valid_embeds: list[np.ndarray] = []
    for nid, emb in zip(node_ids, embeddings):
        if emb is not None:
            valid_ids.append(nid)
            valid_embeds.append(emb)

    if not valid_embeds:
        return [], np.empty((0, 0))

    matrix = np.vstack(valid_embeds)
    logger.info("embeddings_collected", nodes=len(valid_ids), dim=matrix.shape[1])
    return valid_ids, matrix


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------


def cluster_embeddings(
    node_ids: list[str],
    matrix: np.ndarray,
    n_clusters: int | None = None,
    method: str = "kmeans",
) -> EmbeddingCluster:
    """Cluster embedding vectors.

    Args:
        node_ids: Node identifiers aligned with matrix rows.
        matrix: (N, D) embedding matrix.
        n_clusters: Number of clusters (auto-detected for hdbscan).
        method: "kmeans" or "hdbscan".

    Returns:
        EmbeddingCluster with assignments.
    """
    from sklearn.cluster import KMeans  # type: ignore[import-untyped]
    from sklearn.metrics import silhouette_score  # type: ignore[import-untyped]

    if method == "kmeans":
        if n_clusters is None:
            # Rule of thumb: √(N/2)
            n_clusters = max(2, int(np.sqrt(len(node_ids) / 2)))
        km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = km.fit_predict(matrix)
        node_to_cluster = {nid: int(l) for nid, l in zip(node_ids, labels)}
        sil = float(silhouette_score(matrix, labels)) if len(set(labels)) > 1 else 0.0
        sizes = _count_cluster_sizes(labels, n_clusters)
        return EmbeddingCluster(
            algorithm="kmeans",
            num_clusters=n_clusters,
            node_to_cluster=node_to_cluster,
            cluster_sizes=sizes,
            silhouette_score=sil,
            inertia=float(km.inertia_),
        )
    elif method == "hdbscan":
        try:
            from sklearn.cluster import HDBSCAN  # type: ignore[import-untyped]
        except ImportError:
            from hdbscan import HDBSCAN  # type: ignore[import-untyped]
        hdb = HDBSCAN(min_cluster_size=max(3, len(node_ids) // 20))
        labels = hdb.fit_predict(matrix)
        n_found = len(set(labels) - {-1})
        node_to_cluster = {nid: int(l) for nid, l in zip(node_ids, labels)}
        sil = None
        if n_found > 1:
            mask = labels >= 0
            if mask.sum() > n_found:
                sil = float(silhouette_score(matrix[mask], labels[mask]))
        sizes = _count_cluster_sizes(labels, n_found)
        return EmbeddingCluster(
            algorithm="hdbscan",
            num_clusters=n_found,
            node_to_cluster=node_to_cluster,
            cluster_sizes=sizes,
            silhouette_score=sil,
        )
    else:
        raise ValueError(f"Unknown clustering method: {method}")


def _count_cluster_sizes(labels: np.ndarray, k: int) -> list[int]:
    """Count members per cluster, sorted descending."""
    from collections import Counter
    counts = Counter(int(l) for l in labels if l >= 0)
    return sorted(counts.values(), reverse=True)


# ---------------------------------------------------------------------------
# Dimensionality Reduction
# ---------------------------------------------------------------------------


def reduce_dimensions(
    node_ids: list[str],
    matrix: np.ndarray,
    method: str = "pca",
    n_components: int = 2,
) -> DimensionReduction:
    """Project embedding vectors to low dimensions for visualisation.

    Args:
        node_ids: Node identifiers.
        matrix: (N, D) embedding matrix.
        method: "pca", "tsne", or "umap".
        n_components: Target dimensionality (2 or 3).

    Returns:
        DimensionReduction with coordinates.
    """
    if method == "pca":
        from sklearn.decomposition import PCA  # type: ignore[import-untyped]
        pca = PCA(n_components=n_components, random_state=42)
        coords = pca.fit_transform(matrix)
        return DimensionReduction(
            method="pca",
            components=n_components,
            node_ids=node_ids,
            coords=coords,
            explained_variance_ratio=pca.explained_variance_ratio_.tolist(),
        )
    elif method == "tsne":
        from sklearn.manifold import TSNE  # type: ignore[import-untyped]
        perplexity = min(30, max(2, len(node_ids) // 4))
        tsne = TSNE(
            n_components=n_components, random_state=42,
            perplexity=perplexity, n_iter=1000,
        )
        coords = tsne.fit_transform(matrix)
        return DimensionReduction(
            method="tsne", components=n_components,
            node_ids=node_ids, coords=coords,
        )
    elif method == "umap":
        import umap  # type: ignore[import-untyped]
        reducer = umap.UMAP(
            n_components=n_components, random_state=42,
            n_neighbors=min(15, max(2, len(node_ids) - 1)),
        )
        coords = reducer.fit_transform(matrix)
        return DimensionReduction(
            method="umap", components=n_components,
            node_ids=node_ids, coords=coords,
        )
    else:
        raise ValueError(f"Unknown reduction method: {method}")


# ---------------------------------------------------------------------------
# Alignment: clusters vs communities
# ---------------------------------------------------------------------------


def compare_partitions(
    partition_a: dict[str, int],
    partition_b: dict[str, int],
    name_a: str = "clusters",
    name_b: str = "communities",
    max_mismatches: int = 50,
) -> AlignmentResult:
    """Compare two node partitions using clustering quality metrics.

    Args:
        partition_a: node_id → group_id (e.g. from embedding clustering).
        partition_b: node_id → group_id (e.g. from graph communities).
        name_a: Label for partition A.
        name_b: Label for partition B.

    Returns:
        AlignmentResult with ARI, NMI, V-measure, mismatched list.
    """
    from sklearn.metrics import (  # type: ignore[import-untyped]
        adjusted_rand_score,
        normalized_mutual_info_score,
        v_measure_score,
    )

    # Align on common nodes
    common = sorted(set(partition_a.keys()) & set(partition_b.keys()))
    if len(common) < 2:
        return AlignmentResult(
            partition_a_name=name_a, partition_b_name=name_b,
            n_nodes_compared=len(common),
        )

    labels_a = [partition_a[n] for n in common]
    labels_b = [partition_b[n] for n in common]

    ari = adjusted_rand_score(labels_a, labels_b)
    nmi = normalized_mutual_info_score(labels_a, labels_b)
    vm = v_measure_score(labels_a, labels_b)

    # Find mismatched nodes (different groupings)
    mismatched: list[str] = []
    for node, la, lb in zip(common, labels_a, labels_b):
        if la != lb:
            mismatched.append(node)
    mismatched = mismatched[:max_mismatches]

    return AlignmentResult(
        partition_a_name=name_a,
        partition_b_name=name_b,
        adjusted_rand_index=float(ari),
        normalized_mutual_info=float(nmi),
        v_measure=float(vm),
        n_nodes_compared=len(common),
        mismatched_nodes=mismatched,
    )


# ---------------------------------------------------------------------------
# Coherence
# ---------------------------------------------------------------------------


def compute_coherence(
    node_ids: list[str],
    matrix: np.ndarray,
    partition: dict[str, int],
    partition_name: str = "community",
    partition_type: str = "community",
) -> CoherenceResult:
    """Compute intra-group embedding coherence (average cosine similarity).

    A high coherence means entities in the same structural community are
    also semantically close — evidence that the KG captures meaningful
    semantic relationships.

    Args:
        node_ids: Node identifiers aligned with matrix rows.
        matrix: (N, D) embedding matrix.
        partition: node_id → group_id mapping.
        partition_name: Human-readable name for the partition.
        partition_type: Type label (community, cluster, node_type).

    Returns:
        CoherenceResult with per-group and aggregate scores.
    """
    from sklearn.metrics.pairwise import cosine_similarity  # type: ignore[import-untyped]

    id_to_idx = {nid: i for i, nid in enumerate(node_ids)}
    groups: dict[int, list[int]] = {}
    for nid, gid in partition.items():
        if nid in id_to_idx:
            groups.setdefault(gid, []).append(id_to_idx[nid])

    per_group: dict[str, float] = {}
    all_sims: list[float] = []

    for gid, indices in groups.items():
        if len(indices) < 2:
            per_group[str(gid)] = 1.0
            continue
        sub = matrix[indices]
        sim_matrix = cosine_similarity(sub)
        # Upper triangle, excluding diagonal
        n = len(indices)
        mask = np.triu_indices(n, k=1)
        sims = sim_matrix[mask]
        avg = float(np.mean(sims))
        per_group[str(gid)] = avg
        all_sims.extend(sims.tolist())

    mean_coherence = float(np.mean(all_sims)) if all_sims else 0.0

    return CoherenceResult(
        group_name=partition_name,
        group_type=partition_type,
        mean_cosine_similarity=mean_coherence,
        per_group=per_group,
    )


# ---------------------------------------------------------------------------
# Full Embedding Analysis
# ---------------------------------------------------------------------------


def run_embedding_analysis(
    store: Any,
    communities: dict[str, int] | None = None,
    embedding_provider: Any | None = None,
    embedding_key: str = "embedding",
    n_clusters: int | None = None,
    reduction_methods: list[str] | None = None,
) -> EmbeddingAnalysis:
    """Run comprehensive embedding space analysis.

    Args:
        store: GraphStore with nodes (optionally having embedding properties).
        communities: node_id → community_id from structural analysis.
        embedding_provider: Optional provider to compute missing embeddings.
        embedding_key: Property key for stored embeddings.
        n_clusters: Explicit number of clusters (auto if None).
        reduction_methods: Dimensionality reduction methods (default: pca, tsne).

    Returns:
        EmbeddingAnalysis with clusters, reductions, alignments, coherence.
    """
    logger.info("embedding_analysis_starting")

    if reduction_methods is None:
        reduction_methods = ["pca", "tsne"]

    analysis = EmbeddingAnalysis()

    # Collect embeddings
    node_ids, matrix = collect_embeddings(
        store, embedding_provider=embedding_provider, embedding_key=embedding_key,
    )

    if len(node_ids) < 3:
        logger.warning("embedding_analysis_skipped", reason="too_few_embeddings")
        return analysis

    analysis.node_ids = node_ids
    analysis.embedding_matrix = matrix

    # Cluster embeddings
    for method in ["kmeans"]:
        try:
            cluster = cluster_embeddings(
                node_ids, matrix, n_clusters=n_clusters, method=method,
            )
            analysis.clusters[method] = cluster
            logger.info(
                "embeddings_clustered",
                method=method, k=cluster.num_clusters,
                silhouette=cluster.silhouette_score,
            )
        except Exception as e:
            logger.warning("clustering_failed", method=method, error=str(e))

    # Dimensionality reduction
    for method in reduction_methods:
        try:
            dr = reduce_dimensions(node_ids, matrix, method=method, n_components=2)
            analysis.reductions[method] = dr
        except Exception as e:
            logger.warning("reduction_failed", method=method, error=str(e))

    # Compare clusters vs communities
    if communities and "kmeans" in analysis.clusters:
        alignment = compare_partitions(
            analysis.clusters["kmeans"].node_to_cluster,
            communities,
            name_a="embedding_kmeans",
            name_b="graph_communities",
        )
        analysis.alignments.append(alignment)
        logger.info(
            "cluster_community_alignment",
            ari=alignment.adjusted_rand_index,
            nmi=alignment.normalized_mutual_info,
            v_measure=alignment.v_measure,
        )

        # Coherence of communities in embedding space
        coherence = compute_coherence(
            node_ids, matrix, communities,
            partition_name="graph_communities",
            partition_type="community",
        )
        analysis.coherence.append(coherence)

    # Coherence of embedding clusters
    if "kmeans" in analysis.clusters:
        coherence = compute_coherence(
            node_ids, matrix,
            analysis.clusters["kmeans"].node_to_cluster,
            partition_name="embedding_clusters",
            partition_type="cluster",
        )
        analysis.coherence.append(coherence)

    # Coherence by node type
    type_partition: dict[str, int] = {}
    type_labels: dict[str, int] = {}
    for node in store.get_all_nodes():
        if node.id in set(node_ids):
            if node.node_type not in type_labels:
                type_labels[node.node_type] = len(type_labels)
            type_partition[node.id] = type_labels[node.node_type]

    if len(type_labels) > 1:
        coherence = compute_coherence(
            node_ids, matrix, type_partition,
            partition_name="node_types",
            partition_type="node_type",
        )
        analysis.coherence.append(coherence)

    logger.info("embedding_analysis_complete")
    return analysis
