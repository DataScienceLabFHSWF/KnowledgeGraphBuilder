"""Gold-standard loader and evaluator for entity/relation extraction.

Provides a simple, testable scaffold for Phase‑3 (gold standard) work:
- JSON schema loader for annotated documents
- Exact-span entity matching and relation matching
- Precision / Recall / F1 computation utilities

This is intentionally small and deterministic so domain experts can
add annotated JSON files under `data/evaluation/gold_standard/` and
developers can run automated P/R/F1 evaluations.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import json
import math


@dataclass
class GoldEntity:
    id: str
    start: int
    end: int
    text: str
    label: str


@dataclass
class GoldRelation:
    subject_id: str
    predicate: str
    object_id: str


@dataclass
class GoldDocument:
    doc_id: str
    text: str
    entities: list[GoldEntity]
    relations: list[GoldRelation]


# -------------------------- Loading ----------------------------------------

def load_gold_documents(path: Path) -> list[GoldDocument]:
    """Load one or more gold-standard JSON documents from `path`.

    Expected JSON format (per file):
    {
      "doc_id": "doc1",
      "text": "...",
      "entities": [ {"id":"e1","start":0,"end":5,"text":"...","label":"Paragraf"} ],
      "relations": [ {"subject_id":"e1","predicate":"teilVon","object_id":"e2"} ]
    }
    """
    path = Path(path)
    docs: list[GoldDocument] = []

    if path.is_dir():
        files = sorted(path.glob("*.json"))
    else:
        files = [path]

    for f in files:
        data = json.loads(f.read_text(encoding="utf8"))
        ents = [GoldEntity(**e) for e in data.get("entities", [])]
        rels = [GoldRelation(**r) for r in data.get("relations", [])]
        docs.append(GoldDocument(doc_id=data["doc_id"], text=data.get("text", ""), entities=ents, relations=rels))
    return docs


# -------------------------- Evaluation -------------------------------------

def _prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    prec = tp / (tp + fp) if tp + fp > 0 else 0.0
    rec = tp / (tp + fn) if tp + fn > 0 else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec > 0 else 0.0
    return {"precision": prec, "recall": rec, "f1": f1}


def evaluate_entities(
    predicted: list[dict[str, Any]],
    gold: list[GoldEntity],
    *,
    match_label: bool = True,
) -> dict[str, Any]:
    """Evaluate predicted entities against gold entity spans.

    Args:
        predicted: list of dicts with keys: start, end, label (optional), text (optional)
        gold: list of GoldEntity
        match_label: whether to require label equality for a true positive

    Returns:
        dict with counts and precision/recall/f1
    """
    gold_map = {(g.start, g.end): g for g in gold}

    tp = 0
    fp = 0
    matched_gold = set()

    for p in predicted:
        key = (int(p["start"]), int(p["end"]))
        g = gold_map.get(key)
        if g and (not match_label or str(p.get("label", "")).lower() == g.label.lower()):
            tp += 1
            matched_gold.add(key)
        else:
            fp += 1

    fn = len(gold) - len(matched_gold)
    stats = _prf(tp, fp, fn)
    return {"tp": tp, "fp": fp, "fn": fn, **stats}


def evaluate_relations(
    predicted: list[dict[str, Any]],
    gold: list[GoldRelation],
    gold_entities: list[GoldEntity],
    *,
    match_predicate: bool = True,
) -> dict[str, Any]:
    """Evaluate predicted relations against gold relations.

    Predicted relations must refer to entity spans (start/end) or ids.
    For simplicity this evaluator accepts predicted subject/object as
    either entity ids (matching gold ids) or spans {start,end}.
    """
    # Build mapping from entity id -> GoldEntity and span -> id
    id_map = {g.id: g for g in gold_entities}
    span_map = {(g.start, g.end): g.id for g in gold_entities}

    normalized_pred: set[tuple[str, str, str]] = set()
    for p in predicted:
        subj = p.get("subject_id") or span_map.get((p.get("subject_start"), p.get("subject_end")))
        obj = p.get("object_id") or span_map.get((p.get("object_start"), p.get("object_end")))
        pred = p.get("predicate")
        if subj and obj and pred:
            normalized_pred.add((subj, pred, obj))

    gold_set = set((r.subject_id, r.predicate, r.object_id) for r in gold)

    tp = len(normalized_pred & gold_set)
    fp = len(normalized_pred - gold_set)
    fn = len(gold_set - normalized_pred)

    stats = _prf(tp, fp, fn)
    return {"tp": tp, "fp": fp, "fn": fn, **stats}
