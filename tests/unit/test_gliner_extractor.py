from __future__ import annotations

from typing import Any

from kgbuilder.extraction.entity import OntologyClassDef
from kgbuilder.extraction.gliner import GLiNEREntityExtractor


class FakeGLiNER:
    def __init__(self) -> None:
        self.labels: list[str] = []

    def predict_entities(
        self,
        text: str,
        labels: list[str],
        threshold: float,
    ) -> list[dict[str, Any]]:
        self.labels = labels
        return [
            {"text": "Ada Lovelace", "label": "Person", "start": 0, "end": 12, "score": 0.92},
            {"text": "unknown", "label": "Unknown", "start": 13, "end": 20, "score": 0.99},
            {"text": "bad-offset", "label": "Person", "start": -1, "end": 2, "score": 0.99},
        ]


def test_gliner_maps_named_spans_to_ontology_and_records_evidence() -> None:
    model = FakeGLiNER()
    extractor = GLiNEREntityExtractor(model=model)
    ontology_classes = [
        OntologyClassDef(uri="urn:kg:Person", label="Person", description="Human individual")
    ]

    result = extractor.extract(
        "Ada Lovelace works.",
        ontology_classes,
    )

    assert model.labels == ["Person"]
    assert len(result) == 1
    assert result[0].label == "Ada Lovelace"
    assert result[0].entity_type == "Person"
    assert result[0].evidence[0].text_span == "Ada Lovelace"
