"""Unit tests for ConfidenceBooster behaviour."""

from __future__ import annotations

from dataclasses import replace

from kgbuilder.confidence.booster import ConfidenceBooster
from kgbuilder.core.models import ExtractedEntity, Evidence


def make_entity(eid: str, etype: str, conf: float, sources: list[str] | None = None) -> ExtractedEntity:
    evs = [Evidence(source_type="doc", source_id=s) for s in (sources or [])]
    return ExtractedEntity(
        id=eid,
        label="lbl",
        entity_type=etype,
        description="",
        confidence=conf,
        evidence=evs,
    )


def test_boost_confidence_basic():
    booster = ConfidenceBooster()
    # no evidence, no boost
    e1 = make_entity("1", "X", 0.5)
    assert booster.boost_confidence(e1).confidence == 0.5

    # two unique sources -> boost
    e2 = make_entity("2", "X", 0.5, ["a", "b"])
    boosted = booster.boost_confidence(e2)
    assert boosted.confidence > 0.5
    assert boosted.confidence <= ConfidenceBooster.MAX_CONFIDENCE

    # type prior applies
    e3 = make_entity("3", "Action", 0.5)
    boosted3 = booster.boost_confidence(e3)
    assert boosted3.confidence > 0.5

    # multi-source + type prior
    e4 = make_entity("4", "Action", 0.5, ["a", "b", "c"])
    boosted4 = booster.boost_confidence(e4)
    assert boosted4.confidence > boosted3.confidence


def test_boost_batch_and_cap():
    booster = ConfidenceBooster()
    ents = [make_entity("1", "X", 0.9, ["a", "b"]), make_entity("2", "Action", 0.95)]
    result = booster.boost_batch(ents)
    assert len(result) == 2
    # ensure cap at MAX_CONFIDENCE
    assert all(r.confidence <= ConfidenceBooster.MAX_CONFIDENCE for r in result)
