"""Unit tests for EntityQualityFilter (Task 5.6)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kgbuilder.confidence.filter import EntityQualityFilter
from kgbuilder.core.models import Evidence, ExtractedEntity


@pytest.fixture
def sample_entities() -> list[ExtractedEntity]:
    """Create sample entities for testing."""
    return [
        ExtractedEntity(
            id="e1",
            label="Apple Inc.",
            entity_type="Organization",
            description="Technology company",
            confidence=0.92,
            evidence=[
                Evidence(source_type="local_doc", source_id="doc1", text_span="Apple Inc."),
                Evidence(source_type="local_doc", source_id="doc2", text_span="Apple"),
            ],
        ),
        ExtractedEntity(
            id="e2",
            label="ML",
            entity_type="Concept",
            description="AI technique",
            confidence=0.78,
            evidence=[Evidence(source_type="local_doc", source_id="doc1", text_span="ML")],
        ),
        ExtractedEntity(
            id="e3",
            label="uncertain",
            entity_type="Concept",
            description="Unclear",
            confidence=0.55,
            evidence=[Evidence(source_type="local_doc", source_id="doc3", text_span="unclear")],
        ),
        ExtractedEntity(
            id="e4",
            label="no evidence",
            entity_type="Person",
            description="Person without sources",
            confidence=0.65,
            evidence=[],
        ),
        ExtractedEntity(
            id="e5",
            label="no desc",
            entity_type="Location",
            description="",
            confidence=0.75,
            evidence=[Evidence(source_type="local_doc", source_id="doc4", text_span="place")],
        ),
    ]


@pytest.fixture
def filter_default() -> EntityQualityFilter:
    """Create filter with default settings."""
    return EntityQualityFilter()


@pytest.fixture
def filter_lenient() -> EntityQualityFilter:
    """Create lenient filter."""
    return EntityQualityFilter(
        confidence_threshold=0.50,
        require_evidence=False,
        require_description=False,
    )


class TestEntityQualityFilterBasics:
    """Test basic filter initialization."""

    def test_init_default(self) -> None:
        """Test default initialization."""
        f = EntityQualityFilter()
        assert f is not None

    def test_init_custom_threshold(self) -> None:
        """Test with custom threshold."""
        f = EntityQualityFilter(confidence_threshold=0.80)
        assert f is not None


class TestEntityQualityFilterFiltering:
    """Test entity filtering."""

    def test_filter_empty(self, filter_default: EntityQualityFilter) -> None:
        """Test filtering empty list."""
        result = filter_default.filter([])
        assert result == []

    def test_filter_by_confidence(
        self,
        sample_entities: list[ExtractedEntity],
    ) -> None:
        """Test filtering by confidence."""
        f = EntityQualityFilter(confidence_threshold=0.70)
        filtered = f.filter(sample_entities)

        filtered_ids = [e.id for e in filtered]
        assert "e1" in filtered_ids  # 0.92
        assert "e2" in filtered_ids  # 0.78
        assert "e3" not in filtered_ids  # 0.55

    def test_filter_requires_evidence(
        self,
        sample_entities: list[ExtractedEntity],
    ) -> None:
        """Test evidence requirement."""
        f = EntityQualityFilter(require_evidence=True)
        filtered = f.filter(sample_entities)

        filtered_ids = [e.id for e in filtered]
        assert "e4" not in filtered_ids  # no evidence

    def test_filter_requires_description(
        self,
        sample_entities: list[ExtractedEntity],
    ) -> None:
        """Test description requirement."""
        f = EntityQualityFilter(require_description=True)
        filtered = f.filter(sample_entities)

        filtered_ids = [e.id for e in filtered]
        assert "e5" not in filtered_ids  # empty description


class TestEntityQualityFilterReporting:
    """Test report generation."""

    def test_generate_report(
        self,
        sample_entities: list[ExtractedEntity],
        filter_default: EntityQualityFilter,
    ) -> None:
        """Test basic report generation."""
        filtered = filter_default.filter(sample_entities)
        report = filter_default.generate_report(sample_entities, filtered)

        assert report.total_entities == 5
        assert report.filtered_entities == len(filtered)

    def test_report_contains_stats(
        self,
        sample_entities: list[ExtractedEntity],
        filter_default: EntityQualityFilter,
    ) -> None:
        """Test report has statistics."""
        filtered = filter_default.filter(sample_entities)
        report = filter_default.generate_report(sample_entities, filtered)

        assert "min" in report.confidence_stats
        assert "max" in report.confidence_stats
        assert "mean" in report.confidence_stats

    def test_report_type_breakdown(
        self,
        sample_entities: list[ExtractedEntity],
        filter_default: EntityQualityFilter,
    ) -> None:
        """Test type breakdown in report."""
        filtered = filter_default.filter(sample_entities)
        report = filter_default.generate_report(sample_entities, filtered)

        assert len(report.type_breakdown) > 0


class TestEntityQualityFilterMarkdownExport:
    """Test Markdown export."""

    def test_export_markdown(
        self,
        sample_entities: list[ExtractedEntity],
        filter_default: EntityQualityFilter,
    ) -> None:
        """Test Markdown export."""
        filtered = filter_default.filter(sample_entities)
        report = filter_default.generate_report(sample_entities, filtered)
        md = filter_default.export_markdown(report)

        assert "Entity Quality Report" in md
        assert "Total Entities" in md

    def test_export_markdown_file(
        self,
        sample_entities: list[ExtractedEntity],
        filter_default: EntityQualityFilter,
        tmp_path: Path,
    ) -> None:
        """Test Markdown export to file."""
        filtered = filter_default.filter(sample_entities)
        report = filter_default.generate_report(sample_entities, filtered)
        filepath = tmp_path / "report.md"

        filter_default.export_markdown(report, str(filepath))

        assert filepath.exists()
        content = filepath.read_text()
        assert "Entity Quality Report" in content


class TestEntityQualityFilterJsonExport:
    """Test JSON export."""

    def test_export_json(
        self,
        sample_entities: list[ExtractedEntity],
        filter_default: EntityQualityFilter,
    ) -> None:
        """Test JSON export."""
        filtered = filter_default.filter(sample_entities)
        report = filter_default.generate_report(sample_entities, filtered)
        json_str = filter_default.export_json(report, filtered)

        data = json.loads(json_str)
        assert "report" in data
        assert "entities" in data

    def test_export_json_file(
        self,
        sample_entities: list[ExtractedEntity],
        filter_default: EntityQualityFilter,
        tmp_path: Path,
    ) -> None:
        """Test JSON export to file."""
        filtered = filter_default.filter(sample_entities)
        report = filter_default.generate_report(sample_entities, filtered)
        filepath = tmp_path / "report.json"

        filter_default.export_json(report, filtered, str(filepath))

        assert filepath.exists()
        with open(filepath) as f:
            data = json.load(f)
        assert "report" in data


class TestEntityQualityFilterEdgeCases:
    """Test edge cases."""

    def test_filter_single(self, filter_default: EntityQualityFilter) -> None:
        """Test single entity."""
        entity = ExtractedEntity(
            id="single",
            label="Test",
            entity_type="Thing",
            description="Test",
            confidence=0.80,
            evidence=[Evidence(source_type="local_doc", source_id="d1", text_span="test")],
        )
        filtered = filter_default.filter([entity])
        assert len(filtered) == 1

    def test_filter_all_high(self, filter_default: EntityQualityFilter) -> None:
        """Test all high confidence."""
        entities = [
            ExtractedEntity(
                id=f"e{i}",
                label=f"Entity {i}",
                entity_type="Thing",
                description="High",
                confidence=0.95,
                evidence=[Evidence(source_type="local_doc", source_id="d1", text_span=f"e{i}")],
            )
            for i in range(3)
        ]
        filtered = filter_default.filter(entities)
        assert len(filtered) == 3

    def test_filter_all_low(self, filter_default: EntityQualityFilter) -> None:
        """Test all low confidence."""
        entities = [
            ExtractedEntity(
                id=f"e{i}",
                label=f"Entity {i}",
                entity_type="Thing",
                description="Low",
                confidence=0.3 + (i * 0.05),
                evidence=[Evidence(source_type="local_doc", source_id="d1", text_span=f"e{i}")],
            )
            for i in range(3)
        ]
        filtered = filter_default.filter(entities)
        assert len(filtered) == 0


class TestEntityQualityFilterIntegration:
    """Integration tests."""

    def test_full_pipeline(
        self,
        sample_entities: list[ExtractedEntity],
    ) -> None:
        """Test complete filtering pipeline."""
        f = EntityQualityFilter(confidence_threshold=0.70)

        filtered = f.filter(sample_entities)
        report = f.generate_report(sample_entities, filtered)

        md = f.export_markdown(report)
        assert len(md) > 0

        json_str = f.export_json(report, filtered)
        data = json.loads(json_str)
        assert len(data["entities"]) == len(filtered)
