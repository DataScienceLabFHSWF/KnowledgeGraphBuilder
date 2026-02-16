"""Tests for the embedding+string EntityResolver."""
from __future__ import annotations

import numpy as np

from kgbuilder.analytics.entity_resolver import EntityResolver


def _make_embeddings(labels):
    # map labels to simple 2-d vectors for deterministic similarity
    out = {}
    for idx, lab in enumerate(labels):
        if lab.lower().startswith("kern"):
            out[f"id{idx}"] = [1.0, 0.0]
        elif lab.lower().startswith("nuk"):
            out[f"id{idx}"] = [0.99, 0.1]
        else:
            out[f"id{idx}"] = [0.0, 1.0]
    return out


def test_resolver_clusters_by_embedding_and_text():
    entities = [
        {"id": "id0", "label": "Kernbrennstoff"},
        {"id": "id1", "label": "nuklearer Brennstoff"},
        {"id": "id2", "label": "Andere"},
    ]
    embeddings = _make_embeddings([e["label"] for e in entities])

    r = EntityResolver(edit_weight=0.3, sim_threshold=0.75)
    res = r.cluster(entities, embeddings)
    # Expect id0 and id1 to be clustered together, id2 separate
    assert any({"id0", "id1"}.issubset(c) for c in res.clusters)
    assert any({"id2"}.issubset(c) for c in res.clusters)


def test_resolver_falls_back_to_string_if_no_embeddings():
    entities = [
        {"id": "a", "label": "Kernbrennstoff"},
        {"id": "b", "label": "Kernbrennstoff"},
        {"id": "c", "label": "Facility"},
    ]
    r = EntityResolver(edit_weight=1.0, sim_threshold=0.9)
    res = r.cluster(entities, embeddings=None)
    # a and b identical strings -> cluster
    assert any({"a", "b"}.issubset(c) for c in res.clusters)
