"""Tests for ConfidenceBooster."""

from __future__ import annotations

import pytest

from kgbuilder.core.models import ExtractedEntity, Evidence
from kgbuilder.confidence.booster import ConfidenceBooster


@pytest.fixture
def booster() -> ConfidenceBooster:
    """Create a ConfidenceBooster instance."""
    return ConfidenceBooster()


def test_boost_single_source(booster: ConfidenceBooster) -> None:
    """Test boosting for single-source entity."""
    entity = ExtractedEntity(
        id="e1",
        label="Test",
        entity_type="Action",
        description="Test",
        confidence=0.7,
        evidence=[Evidence(source_type="local_doc", source_id="doc1", text_span="Test entity")],
    )
    boosted = booster.boost_confidence(entity)
    # Single source gets type boost only
    assert boosted.confidence > entity.confidence


def test_boost_multi_source(booster: ConfidenceBooster) -> None:
    """Test boosting for multi-source entity."""
    entity = ExtractedEntity(
        id="e1",
        label="Test",
        entity_type="Action",
        description="Test",
        confidence=0.7,
        evidence=[
            Evidence(source_type="local_doc", source_id="doc1", text_span="Test entity"),
            Evidence(source_type="local_doc", source_id="doc2", text_span="Test entity"),
        ],
    )
    boosted = booster.boost_confidence(entity)
    # Multi-source gets both type boost and multi-source boost
    assert boosted.confidence > entity.confidence


def test_boost_high_confidence_type(booster: ConfidenceBooster) -> None:
    """Test that high-confidence types get boosted."""
    action_entity = ExtractedEntity(
        id="e1",
        label="Act",
        entity_type="Action",
        description="Act",
        confidence=0.7,
    )
    state_entity = ExtractedEntity(
        id="e2",
        label="State",
        entity_type="State",
        description="State",
        confidence=0.7,
    )
    boosted_action = booster.boost_confidence(action_entity)
    boosted_state = booster.boost_confidence(state_entity)
    # Action should get boost, State should not
    assert boosted_action.confidence > boosted_state.confidence


def test_boost_caps_at_max(booster: ConfidenceBooster) -> None:
    """Test that boost caps at MAX_CONFIDENCE."""
    entity = ExtractedEntity(
        id="e1",
        label="Test",
        entity_type="Action",
        description="Test",
        confidence=0.95,
        evidence=[
            Evidence(source_type="local_doc", source_id="doc1", text_span="Test"),
            Evidence(source_type="local_doc", source_id="doc2", text_span="Test"),
        ],
    )
    boosted = booster.boost_confidence(entity)
    assert boosted.confidence <= ConfidenceBooster.MAX_CONFIDENCE


def test_boost_batch(booster: ConfidenceBooster) -> None:
    """Test batch boosting."""
    entities = [
        ExtractedEntity(
            id=f"e{i}",
            label=f"Entity {i}",
            entity_type="Action",
            description=f"Entity {i}",
            confidence=0.7,
        )
        for i in range(5)
    ]
    boosted = booster.boost_batch(entities)
    assert len(boosted) == 5
    assert all(b.confidence >= 0.7 for b in boosted)


def test_no_evidence_boost(booster: ConfidenceBooster) -> None:
    """Test that entity with no evidence gets type prior boost."""
    entity = ExtractedEntity(
        id="e1",
        label="Test",
        entity_type="Parameter",
        description="Test",
        confidence=0.6,
        evidence=[],
    )
    boosted = booster.boost_confidence(entity)
    # Parameter gets type prior boost (+5%)
    assert boosted.confidence == 0.65
