"""Internal Entity Resolution runner and utilities.

Provides a lightweight runner that identifies clustering/merge candidates
from any GraphStore by using the `EntityResolver` (embedding + string).
The runner is non-destructive: it only returns candidate clusters and
confidence scores so the caller can inspect or apply merges later.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List

import numpy as np

from kgbuilder.analytics.entity_resolver import EntityResolver


@dataclass
class MergeCandidate:
    ids: set[str]
    size: int
    score: float


def find_merge_candidates(
    store: Any,
    *,
    node_types: list[str] | None = None,
    min_cluster_size: int = 2,
    edit_weight: float = 0.3,
    sim_threshold: float = 0.85,
    sample_limit: int | None = None,
) -> list[MergeCandidate]:
    """Find candidate clusters of nodes that likely refer to the same entity.

    Args:
        store: GraphStore implementing `get_all_nodes()` / `get_nodes_by_type()`.
        node_types: Optional list of node_type strings to restrict search.
        min_cluster_size: Minimum cluster size to return.
        edit_weight: Weight for string-similarity in EntityResolver.
        sim_threshold: Combined similarity threshold.
        sample_limit: If set, limit the number of candidate nodes sampled.

    Returns:
        Sorted list of MergeCandidate (largest / highest-score first).
    """
    # Collect nodes
    nodes = []
    if node_types:
        for t in node_types:
            nodes.extend(store.get_nodes_by_type(t))
    else:
        nodes = list(store.get_all_nodes())

    if sample_limit is not None and len(nodes) > sample_limit:
        nodes = nodes[: sample_limit]

    # Build entities and embeddings dict
    entities = []
    embeddings: dict[str, list[float]] = {}
    for n in nodes:
        if not n.label:
            continue
        entities.append({"id": n.id, "label": n.label})
        emb = n.properties.get("embedding") or n.properties.get("vector")
        if emb is not None:
            embeddings[n.id] = np.asarray(emb, dtype=float)

    if not entities:
        return []

    resolver = EntityResolver(edit_weight=edit_weight, sim_threshold=sim_threshold)
    clusters = resolver.cluster(entities, embeddings)

    # Score clusters by average pairwise similarity
    def cluster_score(cluster: set[str]) -> float:
        ids = list(cluster)
        scores: list[float] = []
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a = next(e for e in entities if e["id"] == ids[i])
                b = next(e for e in entities if e["id"] == ids[j])
                emb_a = embeddings.get(ids[i])
                emb_b = embeddings.get(ids[j])
                scores.append(resolver.combined_similarity(a["label"], b["label"], emb_a, emb_b))
        return float(np.mean(scores)) if scores else 0.0

    results: list[MergeCandidate] = []
    for c in clusters.clusters:
        if len(c) >= min_cluster_size:
            results.append(MergeCandidate(ids=set(c), size=len(c), score=cluster_score(set(c))))

    # Sort by size desc, then score desc
    results.sort(key=lambda x: (x.size, x.score), reverse=True)
    return results
