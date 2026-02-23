"""Unit tests for confidence tuning pipeline."""

from __future__ import annotations

from typing import List

import pytest

from kgbuilder.pipeline.confidence_tuning import ConfidenceTuningPipeline, ConfidenceTuningResult
from kgbuilder.core.models import ExtractedEntity, ExtractedRelation


class StubReport:
    def __init__(self):
        self.mean = 0
        self.percentiles = {50: 0}
        self.std = 0
        self.anomalies = []


class StubAnalyzer:
    def analyze(self, entities: List[ExtractedEntity]) -> StubReport:
        return StubReport()


class StubBooster:
    def boost_batch(self, entities: List[ExtractedEntity]) -> List[ExtractedEntity]:
        # increase confidence by 0.1 each
        for e in entities:
            e.confidence += 0.1
        return entities


class StubCoref:
    def find_clusters(self, entities, similarity_threshold=0):
        # return empty list to skip merging
        return []

    def merge_cluster(self, cluster, entities_map):
        return entities_map[cluster.entities[0]]


class StubCalibrator:
    def calibrate_batch(self, entities):
        # lower confidence by 0.05
        for e in entities:
            e.confidence -= 0.05
        return entities


class StubVoter:
    def request_votes_batch(self, entities):
        # mark all unanimous
        return [(e.id, True) for e in entities]


class StubFilter:
    def __init__(self, confidence_threshold):
        self.confidence_threshold = confidence_threshold

    def filter_batch(self, entities):
        # remove anything below threshold
        return [e for e in entities if e.confidence >= self.confidence_threshold]

    # pipeline expects a method named `filter`
    def filter(self, entities):
        return self.filter_batch(entities)


@pytest.fixture
def sample_entity() -> ExtractedEntity:
    return ExtractedEntity(
        id="e1",
        label="X",
        entity_type="T",
        confidence=0.5,
        description="",
    )


def make_pipeline():
    pip = ConfidenceTuningPipeline()
    # monkeypatch internal components with stubs
    pip.analyzer = StubAnalyzer()
    pip.booster = StubBooster()
    pip.coreference_resolver = StubCoref()
    pip.calibrator = StubCalibrator()
    pip.voter = StubVoter()
    pip.filter = StubFilter(confidence_threshold=0.4)
    return pip


def test_tune_empty_list():
    pip = make_pipeline()
    ents, rels, res = pip.tune([])
    assert ents == []
    assert rels == []
    assert isinstance(res, ConfidenceTuningResult)
    assert res.total_entities_input == 0
    assert res.entities_filtered == 0


def test_tune_simple_flow(sample_entity):
    pip = make_pipeline()
    ent = sample_entity
    ents, rels, res = pip.tune([ent], relations=None)
    assert isinstance(ents, list) and len(ents) >= 0
    # metrics should reflect at least initial count
    assert res.total_entities_input == 1
    assert res.total_entities_output >= 0
    assert res.calibration_applied is True
    assert res.consensus_votes_requested >= 0


def test_tune_with_relations(sample_entity):
    pip = make_pipeline()
    ent = sample_entity
    rel = ExtractedRelation(id="r1", source_entity_id="e1", target_entity_id="e1", predicate="p")
    ents, rels, res = pip.tune([ent], relations=[rel])
    assert rels == [rel]
    assert res.total_entities_input == 1
