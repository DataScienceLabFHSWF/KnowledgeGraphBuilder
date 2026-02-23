"""Tests for the confidence quality filter and reporting."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import json
import pytest

from kgbuilder.confidence.filter import EntityQualityFilter, QualityReport
from kgbuilder.core.models import ExtractedEntity, Evidence


def make_entity(
    eid: str,
    etype: str,
    conf: float,
    desc: str = "",
    evidence_count: int = 0,
) -> ExtractedEntity:
    evs = [Evidence(source_type="doc", source_id=str(i)) for i in range(evidence_count)]
    return ExtractedEntity(
        id=eid,
        label="lbl",
        entity_type=etype,
        description=desc,
        confidence=conf,
        evidence=evs,
    )


def test_passes_filter_conditions():
    f = EntityQualityFilter(confidence_threshold=0.5, require_evidence=True, require_description=True)
    good = make_entity("1", "A", 0.9, "descr", 1)
    assert f.filter([good]) == [good]

    # low confidence
    bad1 = make_entity("2", "A", 0.1, "descr", 1)
    assert f.filter([bad1]) == []

    # missing evidence
    bad2 = make_entity("3", "A", 0.9, "descr", 0)
    assert f.filter([bad2]) == []

    # missing description
    bad3 = make_entity("4", "A", 0.9, "", 1)
    assert f.filter([bad3]) == []


def test_generate_report_and_quality_issues(tmp_path: Path):
    f = EntityQualityFilter(confidence_threshold=0.5)
    entities = [make_entity(str(i), "A", conf, "d", 1) for i, conf in enumerate([0.6, 0.4, 0.7])]
    filtered = f.filter(entities)
    report = f.generate_report(entities, filtered)
    assert isinstance(report, QualityReport)
    assert report.total_entities == 3
    assert report.filtered_entities == len(filtered)
    assert 0.0 <= report.removal_rate <= 1.0
    # some quality issues should be reported (e.g. low confidence or single type)
    assert report.quality_issues

    # markdown export produces expected sections
    md = f.export_markdown(report)
    assert "Entity Quality Report" in md
    # export to file
    path = tmp_path / "report.md"
    md2 = f.export_markdown(report, filepath=path)
    assert path.read_text() == md2

    # JSON export
    js = f.export_json(report, filtered)
    obj = json.loads(js)
    assert "report" in obj and "entities" in obj
    path2 = tmp_path / "report.json"
    f.export_json(report, filtered, filepath=path2)
    assert json.loads(path2.read_text())["report"]["total_entities"] == 3


def test_identify_quality_issues_various():
    f = EntityQualityFilter(confidence_threshold=0.8)
    orig = [make_entity("1", "A", 0.9, "d", 1), make_entity("2", "B", 0.5, "d", 1)]
    filt = [orig[0]]
    issues = f._identify_quality_issues(orig, filt)
    assert any("Single entity of type" in i for i in issues)
    # low mean confidence issue also triggers if mean < 0.75
    f2 = EntityQualityFilter(confidence_threshold=0.0)
    # create filtered set with low confidence values so mean drops
    orig2 = [make_entity("a", "X", 0.6, "d", 1), make_entity("b", "X", 0.7, "d", 1)]
    issues2 = f2._identify_quality_issues(orig2, orig2)
    assert any("Low average confidence" in i for i in issues2)


def test_quality_report_timestamp_and_types():
    r = QualityReport(
        total_entities=1,
        filtered_entities=1,
        removal_rate=0.0,
        confidence_stats={"min": 0, "max": 1, "mean": 0.5, "threshold": 0.7},
        type_breakdown={"A": 1},
        quality_issues=["foo"],
        timestamp=datetime.now(timezone.utc).isoformat(),
        filter_threshold=0.7,
    )
    d = r.__dict__
    assert d["total_entities"] == 1
    assert isinstance(d["timestamp"], str)
