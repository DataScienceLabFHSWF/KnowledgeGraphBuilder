"""Tests for FindingsSynthesizer.

Comprehensive test suite for findings synthesis including:
- Entity deduplication by similarity
- Confidence score aggregation
- Evidence consolidation
- Conflict detection
"""

from __future__ import annotations

import pytest

from kgbuilder.core.models import Evidence, ExtractedEntity
from kgbuilder.extraction.synthesizer import FindingsSynthesizer

# ============================================================================
# Fixtures
# ============================================================================


def make_entity(
    id_: str,
    label: str,
    entity_type: str,
    confidence: float = 0.90,
    description: str | None = None,
) -> ExtractedEntity:
    """Helper to create ExtractedEntity with required fields."""
    return ExtractedEntity(
        id=id_,
        label=label,
        entity_type=entity_type,
        description=description or f"{label} description",
        confidence=confidence,
    )


@pytest.fixture
def synthesizer() -> FindingsSynthesizer:
    """Create a synthesizer with default settings."""
    return FindingsSynthesizer(similarity_threshold=0.90)


@pytest.fixture
def synthesizer_lenient() -> FindingsSynthesizer:
    """Create a synthesizer with lenient threshold."""
    return FindingsSynthesizer(similarity_threshold=0.80)


@pytest.fixture
def synthesizer_strict() -> FindingsSynthesizer:
    """Create a synthesizer with strict threshold."""
    return FindingsSynthesizer(similarity_threshold=0.95)


# ============================================================================
# Tests: Initialization
# ============================================================================


def test_synthesizer_initialization() -> None:
    """Test synthesizer initializes with threshold."""
    synth = FindingsSynthesizer(similarity_threshold=0.88)
    assert synth._similarity_threshold == 0.88


def test_synthesizer_default_threshold() -> None:
    """Test default similarity threshold."""
    synth = FindingsSynthesizer()
    assert synth._similarity_threshold == 0.90


# ============================================================================
# Tests: Empty Input
# ============================================================================


def test_synthesize_empty_list(synthesizer: FindingsSynthesizer) -> None:
    """Test synthesizing empty entity list."""
    result = synthesizer.synthesize([])
    assert result == []
    assert len(result) == 0


# ============================================================================
# Tests: Single Entity (No Deduplication)
# ============================================================================


def test_synthesize_single_entity(synthesizer: FindingsSynthesizer) -> None:
    """Test synthesizing single entity (no duplicates)."""
    entity = make_entity("ent_1", "Nuclear Reactor", "Facility", confidence=0.95)
    result = synthesizer.synthesize([entity])

    assert len(result) == 1
    assert result[0].id == "ent_1"
    assert result[0].label == "Nuclear Reactor"
    assert result[0].merged_count == 1
    assert result[0].confidence == 0.95


def test_synthesize_multiple_different_entities(
    synthesizer: FindingsSynthesizer,
) -> None:
    """Test synthesizing multiple distinct entities."""
    entities = [
        make_entity("ent_1", "Nuclear Reactor", "Facility", confidence=0.95),
        make_entity("ent_2", "Control Room", "Facility", confidence=0.90),
        make_entity("ent_3", "Safety System", "Equipment", confidence=0.88),
    ]

    result = synthesizer.synthesize(entities)

    assert len(result) == 3
    assert all(s.merged_count == 1 for s in result)


# ============================================================================
# Tests: Exact Duplicates
# ============================================================================


def test_synthesize_exact_duplicates(synthesizer: FindingsSynthesizer) -> None:
    """Test deduplicating exact duplicate entities."""
    entities = [
        make_entity("ent_1", "Nuclear Reactor", "Facility", confidence=0.95),
        make_entity("ent_2", "Nuclear Reactor", "Facility", confidence=0.85),
    ]

    result = synthesizer.synthesize(entities)

    # Should merge into one
    assert len(result) == 1
    assert result[0].label == "Nuclear Reactor"
    assert result[0].merged_count == 2
    # Confidence should be boosted: (0.95 + 0.85) / 2 + 0.05 = 0.95
    assert result[0].confidence >= 0.90


def test_synthesize_three_way_duplicate(synthesizer: FindingsSynthesizer) -> None:
    """Test deduplicating three identical entities."""
    entities = [
        make_entity("ent_1", "Cooling System", "Equipment", confidence=0.92),
        make_entity("ent_2", "Cooling System", "Equipment", confidence=0.88),
        make_entity("ent_3", "Cooling System", "Equipment", confidence=0.90),
    ]

    result = synthesizer.synthesize(entities)

    assert len(result) == 1
    assert result[0].merged_count == 3
    # Confidence boosting: (0.92 + 0.88 + 0.90) / 3 + 0.1 (max boost)
    assert result[0].confidence >= 0.90


# ============================================================================
# Tests: Near-Duplicates (Edit Distance)
# ============================================================================


def test_synthesize_near_duplicates_high_similarity(
    synthesizer: FindingsSynthesizer,
) -> None:
    """Test deduplicating near-identical entities (small variations)."""
    entities = [
        make_entity("ent_1", "Nuclear Reactor A", "Facility", confidence=0.94),
        make_entity("ent_2", "Nuclear Reactor", "Facility", confidence=0.92),
    ]

    result = synthesizer.synthesize(entities)

    # Should merge - labels are very similar
    assert len(result) == 1
    assert result[0].merged_count == 2


def test_synthesize_near_duplicates_low_similarity(
    synthesizer_strict: FindingsSynthesizer,
) -> None:
    """Test that strict threshold doesn't merge dissimilar entities."""
    entities = [
        make_entity("ent_1", "Control", "Equipment", confidence=0.90),
        make_entity("ent_2", "Cooling", "Equipment", confidence=0.88),
    ]

    result = synthesizer_strict.synthesize(entities)

    # Should NOT merge - too dissimilar
    assert len(result) == 2
    assert all(s.merged_count == 1 for s in result)


# ============================================================================
# Tests: Type Matching
# ============================================================================


def test_synthesize_same_label_different_types(
    synthesizer: FindingsSynthesizer,
) -> None:
    """Test that same label with different types doesn't merge."""
    entities = [
        make_entity("ent_1", "Reactor", "Facility", confidence=0.95),
        make_entity("ent_2", "Reactor", "Equipment", confidence=0.90),
    ]

    result = synthesizer.synthesize(entities)

    # Should NOT merge - different types
    assert len(result) == 2


def test_synthesize_type_grouping(synthesizer: FindingsSynthesizer) -> None:
    """Test that synthesis groups entities by type first."""
    entities = [
        make_entity("ent_1", "Reactor", "Facility", confidence=0.95),
        make_entity("ent_2", "Reactor", "Facility", confidence=0.90),
        make_entity("ent_3", "Coolant", "Material", confidence=0.88),
    ]

    result = synthesizer.synthesize(entities)

    # Should have 2 entities (2 Facilities merged, 1 Material kept)
    assert len(result) == 2
    facilities = [s for s in result if s.entity_type == "Facility"]
    materials = [s for s in result if s.entity_type == "Material"]
    assert len(facilities) == 1
    assert facilities[0].merged_count == 2
    assert len(materials) == 1


# ============================================================================
# Tests: Confidence Aggregation
# ============================================================================


def test_confidence_averaging(synthesizer: FindingsSynthesizer) -> None:
    """Test confidence is averaged across merged entities."""
    entities = [
        make_entity("ent_1", "Entity", "Type", confidence=1.0),
        make_entity("ent_2", "Entity", "Type", confidence=0.6),
    ]

    result = synthesizer.synthesize(entities)

    assert len(result) == 1
    # Average: (1.0 + 0.6) / 2 = 0.8, then boost by 0.05 = 0.85
    assert result[0].confidence >= 0.80


def test_confidence_boost_single_merge(synthesizer: FindingsSynthesizer) -> None:
    """Test confidence boost for 2-way merge."""
    entities = [
        make_entity("ent_1", "E", "T", confidence=0.90),
        make_entity("ent_2", "E", "T", confidence=0.90),
    ]

    result = synthesizer.synthesize(entities)

    # Average: 0.90, boost: 0.05 * (2-1) = 0.05, total = 0.95
    assert result[0].confidence == pytest.approx(0.95, abs=1e-6)


def test_confidence_boost_capped_at_one(synthesizer: FindingsSynthesizer) -> None:
    """Test confidence boost is capped at 1.0."""
    entities = [
        make_entity("ent_1", "E", "T", confidence=0.98),
        make_entity("ent_2", "E", "T", confidence=0.97),
    ]

    result = synthesizer.synthesize(entities)

    # Would be 0.975 + 0.05 = 1.025, but capped at 1.0
    assert result[0].confidence <= 1.0


def test_confidence_boost_max_10_percent(
    synthesizer: FindingsSynthesizer,
) -> None:
    """Test confidence boost is capped at 10% (0.1)."""
    entities = [
        make_entity(f"ent_{i}", "E", "T", confidence=0.80)
        for i in range(12)  # 12 entities
    ]

    result = synthesizer.synthesize(entities)

    # Average: 0.80, boost capped at 0.1, so max = 0.90 (with floating point tolerance)
    assert result[0].confidence <= 0.9001  # Allow for floating point precision
    assert result[0].merged_count == 12


# ============================================================================
# Tests: Evidence Consolidation
# ============================================================================


def test_evidence_merging(synthesizer: FindingsSynthesizer) -> None:
    """Test evidence is merged from all entities."""
    entities = [
        ExtractedEntity(
            id="ent_1",
            label="Entity",
            entity_type="Type",
            description="desc",
            confidence=0.95,
            evidence=[Evidence(source_type="doc", source_id="doc_1")],
        ),
        ExtractedEntity(
            id="ent_2",
            label="Entity",
            entity_type="Type",
            description="desc",
            confidence=0.90,
            evidence=[Evidence(source_type="doc", source_id="doc_2")],
        ),
    ]

    result = synthesizer.synthesize(entities)

    assert len(result) == 1
    # Should have evidence from both
    assert len(result[0].evidence) == 2


# ============================================================================
# Tests: Similarity Calculation
# ============================================================================


def test_similarity_identical_labels() -> None:
    """Test similarity of identical labels."""
    synth = FindingsSynthesizer()
    e1 = make_entity("1", "Nuclear Reactor", "Facility", confidence=0.9)
    e2 = make_entity("2", "Nuclear Reactor", "Facility", confidence=0.9)

    sim = synth._calculate_similarity(e1, e2)

    # 0.7 * 1.0 (identical) + 0.3 * 1.0 (same type) = 1.0
    assert sim == 1.0


def test_similarity_different_labels() -> None:
    """Test similarity of completely different labels."""
    synth = FindingsSynthesizer()
    e1 = make_entity("1", "Reactor", "Facility", confidence=0.9)
    e2 = make_entity("2", "Building", "Facility", confidence=0.9)

    sim = synth._calculate_similarity(e1, e2)

    # Should be low but not 0
    assert 0.0 < sim < 0.5


def test_similarity_case_insensitive() -> None:
    """Test similarity is case-insensitive."""
    synth = FindingsSynthesizer()
    e1 = make_entity("1", "NUCLEAR REACTOR", "Facility", confidence=0.9)
    e2 = make_entity("2", "nuclear reactor", "Facility", confidence=0.9)

    sim = synth._calculate_similarity(e1, e2)

    assert sim == 1.0


def test_similarity_high_overlap() -> None:
    """Test similarity with high label overlap."""
    synth = FindingsSynthesizer()
    e1 = make_entity("1", "Nuclear Reactor", "Facility", confidence=0.9)
    e2 = make_entity("2", "Nuclear Reactor A", "Facility", confidence=0.9)

    sim = synth._calculate_similarity(e1, e2)

    # Labels are very similar
    assert sim > 0.90


# ============================================================================
# Tests: Deduplication Groups
# ============================================================================


def test_deduplicate_entities_groups(synthesizer: FindingsSynthesizer) -> None:
    """Test deduplicate_entities groups duplicates."""
    entities = [
        make_entity("ent_1", "Entity", "Type", confidence=0.95),
        make_entity("ent_2", "Entity", "Type", confidence=0.90),
    ]

    result = synthesizer.deduplicate_entities(entities)

    # Should return dict with canonical ID as key
    assert len(result) == 1


def test_deduplicate_no_matches(synthesizer: FindingsSynthesizer) -> None:
    """Test deduplicate with no duplicates."""
    entities = [
        make_entity("ent_1", "EntityA", "Type", confidence=0.95),
        make_entity("ent_2", "EntityB", "Type", confidence=0.90),
    ]

    result = synthesizer.deduplicate_entities(entities)

    # Should return 2 groups (no merging)
    assert len(result) == 2


# ============================================================================
# Tests: Conflict Detection
# ============================================================================


def test_detect_no_conflicts(synthesizer: FindingsSynthesizer) -> None:
    """Test conflict detection with no conflicts."""
    entities = [
        ExtractedEntity(
            id="ent_1",
            label="Entity",
            entity_type="Type",
            description="Description A",
            confidence=0.95,
        ),
        ExtractedEntity(
            id="ent_1",
            label="Entity",
            entity_type="Type",
            description="Description A",
            confidence=0.90,
        ),
    ]

    result = synthesizer.detect_conflicts(entities)

    assert len(result) == 0


def test_detect_description_conflict(synthesizer: FindingsSynthesizer) -> None:
    """Test detecting conflicting descriptions."""
    entities = [
        ExtractedEntity(
            id="ent_1",
            label="Entity",
            entity_type="Type",
            description="Description A",
            confidence=0.95,
        ),
        ExtractedEntity(
            id="ent_1",
            label="Entity",
            entity_type="Type",
            description="Description B",
            confidence=0.90,
        ),
    ]

    result = synthesizer.detect_conflicts(entities)

    assert "ent_1" in result
    assert len(result["ent_1"]) > 0


# ============================================================================
# Tests: Real-World Scenario
# ============================================================================


def test_real_world_nuclear_domain(
    synthesizer_lenient: FindingsSynthesizer,
) -> None:
    """Test deduplication in nuclear domain with real-like data."""
    entities = [
        ExtractedEntity(
            id="nuc_1",
            label="Emsland Nuclear Facility",
            entity_type="NuclearFacility",
            description="German nuclear power plant",
            confidence=0.96,
            evidence=[Evidence(source_type="doc", source_id="doc_001")],
        ),
        ExtractedEntity(
            id="nuc_2",
            label="Emsland Nuclear Plant",
            entity_type="NuclearFacility",
            description="Nuclear power facility",
            confidence=0.92,
            evidence=[Evidence(source_type="doc", source_id="doc_002")],
        ),
        ExtractedEntity(
            id="cool_1",
            label="Cooling System",
            entity_type="Equipment",
            description="Reactor cooling",
            confidence=0.88,
            evidence=[Evidence(source_type="doc", source_id="doc_003")],
        ),
    ]

    result = synthesizer_lenient.synthesize(entities)

    # Should merge first two (same facility, slightly different names) with lenient threshold
    # Should keep cooling system separate
    assert len(result) == 2

    # Check merged facility
    facilities = [e for e in result if e.entity_type == "NuclearFacility"]
    assert len(facilities) == 1
    assert facilities[0].merged_count == 2
    assert len(facilities[0].evidence) == 2

    # Check equipment
    equipment = [e for e in result if e.entity_type == "Equipment"]
    assert len(equipment) == 1
    assert equipment[0].merged_count == 1
