"""Embedding + string based Entity Resolver (lightweight).

Provides a deterministic, testable resolver used for Phase‑4 entity
resolution work. Combines cosine similarity of embeddings with a
string-similarity signal (difflib ratio) to cluster entity mentions
that likely refer to the same real-world object.

API:
- EntityResolver.cluster(entities, embeddings, threshold, edit_weight)

This is intentionally focused and does not write to Neo4j — it returns
clusters (sets of entity ids) so the caller can decide how to merge.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Set

import numpy as np
from difflib import SequenceMatcher


@dataclass
class ClusterResult:
    clusters: list[set[str]]


class EntityResolver:
    """Combine embedding cosine similarity + string similarity to cluster entities."""

    def __init__(self, edit_weight: float = 0.3, sim_threshold: float = 0.85) -> None:
        """Create resolver.

        Args:
            edit_weight: Weight assigned to string-similarity (0..1). Embedding weight = 1 - edit_weight.
            sim_threshold: Combined similarity threshold to link two entities.
        """
        if not 0.0 <= edit_weight <= 1.0:
            raise ValueError("edit_weight must be between 0 and 1")
        self.edit_weight = edit_weight
        self.embed_weight = 1.0 - edit_weight
        self.sim_threshold = sim_threshold

    @staticmethod
    def _cosine(a: np.ndarray, b: np.ndarray) -> float:
        na = np.linalg.norm(a)
        nb = np.linalg.norm(b)
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(a, b) / (na * nb))

    @staticmethod
    def _string_sim(a: str, b: str) -> float:
        return float(SequenceMatcher(None, a or "", b or "").ratio())

    def combined_similarity(self, text_a: str, text_b: str, emb_a: np.ndarray | None, emb_b: np.ndarray | None) -> float:
        """Compute weighted similarity score between two entity mentions."""
        s_text = self._string_sim(text_a, text_b)
        s_embed = 0.0
        if emb_a is not None and emb_b is not None:
            s_embed = self._cosine(np.asarray(emb_a, dtype=float), np.asarray(emb_b, dtype=float))
        return self.embed_weight * s_embed + self.edit_weight * s_text

    def cluster(
        self,
        entities: Iterable[dict[str, Any]],
        embeddings: Dict[str, Iterable[float]] | None = None,
    ) -> ClusterResult:
        """Cluster entity mentions.

        Args:
            entities: Iterable of dicts with keys `id` and `label` (string).
            embeddings: Optional mapping id -> vector (list/ndarray).

        Returns:
            ClusterResult with list of disjoint id-sets.
        """
        items = list(entities)
        n = len(items)
        id_to_idx = {items[i]["id"]: i for i in range(n)}

        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        for i in range(n):
            for j in range(i + 1, n):
                a = items[i]
                b = items[j]
                emb_a = None
                emb_b = None
                if embeddings is not None:
                    emb_a = np.asarray(embeddings.get(a["id"])) if a["id"] in embeddings else None
                    emb_b = np.asarray(embeddings.get(b["id"])) if b["id"] in embeddings else None

                score = self.combined_similarity(str(a.get("label", "")), str(b.get("label", "")), emb_a, emb_b)
                if score >= self.sim_threshold:
                    union(i, j)

        clusters_map: Dict[int, Set[str]] = {}
        for idx, it in enumerate(items):
            root = find(idx)
            clusters_map.setdefault(root, set()).add(it["id"])

        clusters = [s for s in clusters_map.values() if len(s) > 0]
        return ClusterResult(clusters=clusters)
