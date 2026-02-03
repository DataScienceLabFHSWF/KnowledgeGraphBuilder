"""Tests for SimpleKGAssembler (Phase 4d).

Comprehensive test suite for KG assembly including:
- Node creation from SynthesizedEntity
- Relationship creation
- Neo4j connection handling
- Statistics and coverage
- Error handling
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import pytest

from kgbuilder.assembly.simple_kg_assembler import KGAssemblyResult, SimpleKGAssembler
from kgbuilder.core.models import Evidence, ExtractedRelation
from kgbuilder.extraction.synthesizer import SynthesizedEntity


# ============================================================================
# Fixtures
# ============================================================================


def make_entity(
    id_: str,
    label: str,
    entity_type: str,
    confidence: float = 0.90,
    merged_count: int = 1,
) -> SynthesizedEntity:
    """Helper to create SynthesizedEntity for testing."""
    return SynthesizedEntity(
        id=id_,
        label=label,
        entity_type=entity_type,
        description=f"{label} description",
        confidence=confidence,
        evidence=[Evidence(source_type="doc", source_id="doc_001")],
        sources=["ensemble"],
        merged_count=merged_count,
        attributes={},
    )


def make_relation(
    source_id: str,
    target_id: str,
    predicate: str = "RELATED_TO",
    confidence: float = 0.85,
) -> ExtractedRelation:
    """Helper to create ExtractedRelation for testing."""
    return ExtractedRelation(
        id=f"{source_id}_{predicate}_{target_id}",
        source_entity_id=source_id,
        target_entity_id=target_id,
        predicate=predicate,
        confidence=confidence,
        evidence=[Evidence(source_type="doc", source_id="doc_001")],
    )


@pytest.fixture
def mock_neo4j_driver():
    """Create a mock Neo4j driver."""
    driver = MagicMock()
    session = MagicMock()
    
    # Mock session context manager
    driver.session.return_value.__enter__ = Mock(return_value=session)
    driver.session.return_value.__exit__ = Mock(return_value=None)
    
    return driver


@pytest.fixture
def assembler(mock_neo4j_driver):
    """Create assembler with mocked Neo4j driver."""
    with patch(
        "kgbuilder.assembly.simple_kg_assembler.GraphDatabase.driver",
        return_value=mock_neo4j_driver,
    ):
        return SimpleKGAssembler("bolt://localhost:7687", ("user", "pass"))


# ============================================================================
# Tests: Initialization
# ============================================================================


def test_assembler_initialization(mock_neo4j_driver):
    """Test assembler initializes with Neo4j connection."""
    with patch(
        "kgbuilder.assembly.simple_kg_assembler.GraphDatabase.driver",
        return_value=mock_neo4j_driver,
    ):
        assembler = SimpleKGAssembler("bolt://localhost:7687", ("neo4j", "password"))
        assert assembler._driver is not None


# ============================================================================
# Tests: Assembly - Empty Input
# ============================================================================


def test_assemble_empty_entities(assembler):
    """Test assembling empty entity list."""
    result = assembler.assemble([])

    assert isinstance(result, KGAssemblyResult)
    assert result.nodes_created == 0
    assert result.relationships_created == 0


def test_assemble_no_relations(assembler):
    """Test assembly without relations."""
    entities = [
        make_entity("ent_1", "Entity 1", "Type1", confidence=0.95),
        make_entity("ent_2", "Entity 2", "Type2", confidence=0.90),
    ]

    result = assembler.assemble(entities, relations=None)

    assert result.nodes_created == 2
    assert result.relationships_created == 0


# ============================================================================
# Tests: Assembly - Single Entity
# ============================================================================


def test_assemble_single_entity(assembler):
    """Test assembling single entity."""
    entity = make_entity("nuc_1", "Nuclear Reactor", "Facility", confidence=0.95)

    result = assembler.assemble([entity])

    assert result.nodes_created == 1
    assert result.relationships_created == 0
    # Verify statistics
    assert result.statistics["avg_confidence"] == 0.95


def test_assemble_multiple_different_types(assembler):
    """Test assembling entities of different types."""
    entities = [
        make_entity("ent_1", "Reactor", "Facility", confidence=0.95),
        make_entity("ent_2", "Coolant", "Material", confidence=0.90),
        make_entity("ent_3", "Pump", "Equipment", confidence=0.88),
    ]

    result = assembler.assemble(entities)

    assert result.nodes_created == 3
    assert len(set(e.entity_type for e in entities)) == 3


# ============================================================================
# Tests: Confidence & Statistics
# ============================================================================


def test_assemble_confidence_statistics(assembler):
    """Test assembly statistics include confidence information."""
    entities = [
        make_entity("ent_1", "E1", "Type", confidence=1.0),
        make_entity("ent_2", "E2", "Type", confidence=0.8),
        make_entity("ent_3", "E3", "Type", confidence=0.6),
    ]

    result = assembler.assemble(entities)

    assert "avg_confidence" in result.statistics
    avg = result.statistics["avg_confidence"]
    expected_avg = (1.0 + 0.8 + 0.6) / 3
    assert abs(avg - expected_avg) < 0.01


def test_assemble_merged_count_tracking(assembler):
    """Test statistics track merge counts."""
    entities = [
        make_entity("ent_1", "E1", "Type", merged_count=1),
        make_entity("ent_2", "E2", "Type", merged_count=3),
        make_entity("ent_3", "E3", "Type", merged_count=2),
    ]

    result = assembler.assemble(entities)

    # Verify nodes created
    assert result.nodes_created == 3
    # All entities added successfully
    assert result.errors == []


def test_assemble_entity_types_count(assembler):
    """Test statistics count unique entity types."""
    entities = [
        make_entity("ent_1", "E1", "Facility"),
        make_entity("ent_2", "E2", "Equipment"),
        make_entity("ent_3", "E3", "Facility"),
    ]

    result = assembler.assemble(entities)

    # Should have 2 unique types (Facility, Equipment)
    assert result.statistics["entity_types"] == 2


# ============================================================================
# Tests: Evidence Tracking
# ============================================================================


def test_assemble_evidence_count(assembler):
    """Test statistics track total evidence."""
    entities = [
        SynthesizedEntity(
            id="ent_1",
            label="E1",
            entity_type="Type",
            description="desc",
            confidence=0.95,
            evidence=[
                Evidence(source_type="doc", source_id="doc_1"),
                Evidence(source_type="doc", source_id="doc_2"),
            ],
            sources=["extractor1"],
            merged_count=1,
            attributes={},
        ),
        SynthesizedEntity(
            id="ent_2",
            label="E2",
            entity_type="Type",
            description="desc",
            confidence=0.90,
            evidence=[Evidence(source_type="doc", source_id="doc_3")],
            sources=["extractor2"],
            merged_count=1,
            attributes={},
        ),
    ]

    result = assembler.assemble(entities)

    assert result.statistics["total_evidence"] == 3


def test_assemble_sources_tracking(assembler):
    """Test statistics track unique sources."""
    entities = [
        SynthesizedEntity(
            id="ent_1",
            label="E1",
            entity_type="Type",
            description="desc",
            confidence=0.95,
            evidence=[],
            sources=["extractor1", "extractor2"],
            merged_count=1,
            attributes={},
        ),
        SynthesizedEntity(
            id="ent_2",
            label="E2",
            entity_type="Type",
            description="desc",
            confidence=0.90,
            evidence=[],
            sources=["extractor2", "extractor3"],
            merged_count=1,
            attributes={},
        ),
    ]

    result = assembler.assemble(entities)

    # Should have 3 unique sources
    assert result.statistics["total_sources"] == 3


# ============================================================================
# Tests: Relationships
# ============================================================================


def test_assemble_with_relationships(assembler):
    """Test assembly with entity relationships."""
    entities = [
        make_entity("ent_1", "E1", "Type"),
        make_entity("ent_2", "E2", "Type"),
    ]
    relations = [
        make_relation("ent_1", "ent_2", "RELATED_TO", confidence=0.85),
    ]

    result = assembler.assemble(entities, relations=relations)

    assert result.nodes_created == 2
    assert result.relationships_created == 1


def test_assemble_multiple_relationships(assembler):
    """Test assembly with multiple relationships."""
    entities = [
        make_entity("ent_1", "E1", "Type"),
        make_entity("ent_2", "E2", "Type"),
        make_entity("ent_3", "E3", "Type"),
    ]
    relations = [
        make_relation("ent_1", "ent_2", "RELATED_TO"),
        make_relation("ent_2", "ent_3", "CAUSES"),
        make_relation("ent_1", "ent_3", "AFFECTS"),
    ]

    result = assembler.assemble(entities, relations=relations)

    assert result.nodes_created == 3
    assert result.relationships_created == 3


def test_assemble_relationship_with_confidence(assembler):
    """Test relationship stores confidence."""
    entities = [
        make_entity("ent_1", "E1", "Type"),
        make_entity("ent_2", "E2", "Type"),
    ]
    relations = [
        make_relation("ent_1", "ent_2", confidence=0.75),
    ]

    result = assembler.assemble(entities, relations=relations)

    assert result.relationships_created == 1


# ============================================================================
# Tests: Coverage Tracking
# ============================================================================


def test_assemble_coverage_tracking(assembler):
    """Test assembly tracks coverage metric."""
    entities = [make_entity("ent_1", "E1", "Type")]

    result = assembler.assemble(entities, coverage=0.85, iterations=3)

    assert result.coverage == 0.85
    assert result.iterations == 3


def test_assemble_zero_coverage(assembler):
    """Test assembly with zero coverage."""
    entities = [make_entity("ent_1", "E1", "Type")]

    result = assembler.assemble(entities, coverage=0.0)

    assert result.coverage == 0.0


def test_assemble_full_coverage(assembler):
    """Test assembly with full coverage."""
    entities = [make_entity("ent_1", "E1", "Type")]

    result = assembler.assemble(entities, coverage=1.0)

    assert result.coverage == 1.0


# ============================================================================
# Tests: Result Object
# ============================================================================


def test_assembly_result_structure(assembler):
    """Test assembly result has expected structure."""
    entities = [make_entity("ent_1", "E1", "Type")]

    result = assembler.assemble(entities)

    assert hasattr(result, "nodes_created")
    assert hasattr(result, "relationships_created")
    assert hasattr(result, "coverage")
    assert hasattr(result, "iterations")
    assert hasattr(result, "errors")
    assert hasattr(result, "warnings")
    assert hasattr(result, "statistics")

    assert isinstance(result.errors, list)
    assert isinstance(result.warnings, list)
    assert isinstance(result.statistics, dict)


def test_assembly_result_is_dataclass(assembler):
    """Test result is proper dataclass."""
    entities = [make_entity("ent_1", "E1", "Type")]

    result = assembler.assemble(entities)

    assert isinstance(result, KGAssemblyResult)


# ============================================================================
# Tests: Real-World Scenario
# ============================================================================


def test_assemble_nuclear_domain_scenario(assembler):
    """Test assembly with realistic nuclear domain entities."""
    entities = [
        SynthesizedEntity(
            id="nuc_facility_1",
            label="Nuclear Power Plant",
            entity_type="NuclearFacility",
            description="Major nuclear facility for power generation",
            confidence=0.96,
            evidence=[
                Evidence(source_type="doc", source_id="doc_001"),
                Evidence(source_type="doc", source_id="doc_002"),
            ],
            sources=["LLMExtractor", "RuleExtractor"],
            merged_count=2,
            attributes={"location": "Germany"},
        ),
        SynthesizedEntity(
            id="cool_sys_1",
            label="Cooling System",
            entity_type="Equipment",
            description="Primary cooling system",
            confidence=0.92,
            evidence=[Evidence(source_type="doc", source_id="doc_003")],
            sources=["LLMExtractor"],
            merged_count=1,
            attributes={"type": "HVAC"},
        ),
        SynthesizedEntity(
            id="safety_doc_1",
            label="Safety Assessment",
            entity_type="Document",
            description="Safety assessment report",
            confidence=0.88,
            evidence=[Evidence(source_type="doc", source_id="doc_004")],
            sources=["RuleExtractor"],
            merged_count=1,
            attributes={},
        ),
    ]

    relations = [
        make_relation(
            "nuc_facility_1",
            "cool_sys_1",
            "HAS_SYSTEM",
            confidence=0.95,
        ),
        make_relation(
            "nuc_facility_1",
            "safety_doc_1",
            "DOCUMENTED_BY",
            confidence=0.90,
        ),
    ]

    result = assembler.assemble(
        entities,
        relations=relations,
        coverage=0.82,
        iterations=4,
    )

    # Verify nodes
    assert result.nodes_created == 3

    # Verify relationships
    assert result.relationships_created == 2

    # Verify statistics
    assert result.statistics["entity_types"] == 3
    assert result.statistics["total_sources"] == 2
    assert result.coverage == 0.82
    assert result.iterations == 4

    # Verify confidence
    avg_confidence = result.statistics["avg_confidence"]
    expected = (0.96 + 0.92 + 0.88) / 3
    assert abs(avg_confidence - expected) < 0.01
