"""Unit tests for gold-standard loader and evaluator."""
from __future__ import annotations

from pathlib import Path

from kgbuilder.evaluation.gold_standard import (
    GoldEntity,
    GoldRelation,
    GoldDocument,
    evaluate_entities,
    evaluate_relations,
    load_gold_documents,
)


def test_load_gold_documents_example(tmp_path: Path) -> None:
    # Use the bundled example file
    p = Path("data/evaluation/gold_standard/example_01.json")
    docs = load_gold_documents(p)
    assert len(docs) == 1
    doc = docs[0]
    assert doc.doc_id == "doc_001"
    assert any(e.label == "Paragraf" for e in doc.entities)


def test_evaluate_entities_exact_match() -> None:
    gold = [GoldEntity(id="e1", start=0, end=3, text="§ 1", label="Paragraf")]
    preds = [{"start": 0, "end": 3, "label": "Paragraf"}]
    res = evaluate_entities(preds, gold)
    assert res["tp"] == 1
    assert res["precision"] == 1.0
    assert res["recall"] == 1.0


def test_evaluate_entities_label_mismatch() -> None:
    gold = [GoldEntity(id="e1", start=0, end=3, text="§ 1", label="Paragraf")]
    preds = [{"start": 0, "end": 3, "label": "Behoerde"}]
    res = evaluate_entities(preds, gold, match_label=True)
    assert res["tp"] == 0
    assert res["fp"] == 1


def test_evaluate_relations_by_span_and_id() -> None:
    gold_entities = [GoldEntity(id="e1", start=0, end=3, text="§ 1", label="Paragraf"), GoldEntity(id="e2", start=10, end=19, text="Behörde X", label="Behoerde")]
    gold_rels = [GoldRelation(subject_id="e1", predicate="referenziert", object_id="e2")]

    # predicted uses spans
    preds = [{"subject_start": 0, "subject_end": 3, "predicate": "referenziert", "object_start": 10, "object_end": 19}]
    res = evaluate_relations(preds, gold_rels, gold_entities)
    assert res["tp"] == 1
    assert res["precision"] == 1.0

    # predicted uses ids
    preds2 = [{"subject_id": "e1", "predicate": "referenziert", "object_id": "e2"}]
    res2 = evaluate_relations(preds2, gold_rels, gold_entities)
    assert res2["tp"] == 1
