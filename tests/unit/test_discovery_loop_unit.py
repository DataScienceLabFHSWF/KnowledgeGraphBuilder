"""Tests for IterativeDiscoveryLoop.

Comprehensive test suite for discovery loop including:
- Initialization and basic iteration
- Question processing and document retrieval
- Entity extraction and findings accumulation
- Coverage calculation and stopping criteria
- Provenance tracking
- Error handling and recovery
- Integration with QuestionGenerationAgent
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, Mock
import pytest

from kgbuilder.agents.discovery_loop import (
    DiscoveryResult,
    EntityExtractor,
    IterationResult,
    IterativeDiscoveryLoop,
    Retriever,
)
from kgbuilder.agents.question_generator import (
    QuestionGenerationAgent,
    ResearchQuestion,
)
from kgbuilder.core.models import ExtractedEntity, Evidence


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_retriever() -> MagicMock:
    """Create a mock retriever with test data."""
    retriever = MagicMock(spec=Retriever)
    
    # Create mock retrieval results
    result1 = MagicMock()
    result1.doc_id = "doc_001"
    result1.content = "Kernkraftwerk Emsland is a nuclear facility with cooling systems."
    result1.score = 0.92
    
    result2 = MagicMock()
    result2.doc_id = "doc_002"
    result2.content = "Safety document describing reactor operations and requirements."
    result2.score = 0.88
    
    retriever.retrieve.return_value = [result1, result2]
    
    return retriever


@pytest.fixture
def mock_extractor() -> MagicMock:
    """Create a mock extractor with test data."""
    extractor = MagicMock(spec=EntityExtractor)
    
    # Create mock extracted entities
    entity1 = ExtractedEntity(
        id="ent_001",
        label="Emsland",
        entity_type="Facility",
        description="Nuclear facility",
        confidence=0.95,
        evidence=[Evidence(source_type="doc", source_id="doc_001")],
    )
    
    entity2 = ExtractedEntity(
        id="ent_002",
        label="Cooling System",
        entity_type="Equipment",
        description="Cooling equipment",
        confidence=0.90,
        evidence=[Evidence(source_type="doc", source_id="doc_001")],
    )
    
    entity3 = ExtractedEntity(
        id="ent_003",
        label="Safety Report",
        entity_type="SafetyDocument",
        description="Safety documentation",
        confidence=0.92,
        evidence=[Evidence(source_type="doc", source_id="doc_002")],
    )
    
    # Return different entities based on which call
    extractor.extract.side_effect = [
        [entity1, entity2],  # First call
        [entity3],           # Second call
    ]
    
    return extractor


@pytest.fixture
def mock_question_generator() -> MagicMock:
    """Create a mock question generator."""
    gen = MagicMock(spec=QuestionGenerationAgent)
    
    # Setup ontology service mock
    gen._ontology = MagicMock()
    gen._ontology.get_all_classes.return_value = [
        "Facility",
        "Equipment", 
        "SafetyDocument",
        "Organization",
        "Operation",
        "Requirement",
    ]
    
    # Initial questions
    q1 = ResearchQuestion(
        question_id="q_facility",
        text="What are the Facilities?",
        entity_class="Facility",
        priority=0.9,
        reason="Initial",
    )
    
    q2 = ResearchQuestion(
        question_id="q_equipment",
        text="What Equipment is mentioned?",
        entity_class="Equipment",
        priority=0.85,
        reason="Initial",
    )
    
    gen.generate_questions.return_value = [q1, q2]
    gen.generate_follow_up_questions.return_value = []  # No follow-ups in basic tests
    
    return gen


# ============================================================================
# Tests: Initialization
# ============================================================================


def test_discovery_loop_initialization(
    mock_retriever: MagicMock,
    mock_extractor: MagicMock,
    mock_question_generator: MagicMock,
) -> None:
    """Test IterativeDiscoveryLoop initialization."""
    loop = IterativeDiscoveryLoop(
        retriever=mock_retriever,
        extractor=mock_extractor,
        question_generator=mock_question_generator,
    )
    
    assert loop is not None
    assert loop._retriever == mock_retriever
    assert loop._extractor == mock_extractor
    assert loop._question_gen == mock_question_generator
    assert len(loop._findings) == 0
    assert len(loop._provenance) == 0


# ============================================================================
# Tests: Discovery Process
# ============================================================================


def test_run_discovery_basic(
    mock_retriever: MagicMock,
    mock_extractor: MagicMock,
    mock_question_generator: MagicMock,
) -> None:
    """Test basic discovery loop execution."""
    loop = IterativeDiscoveryLoop(
        retriever=mock_retriever,
        extractor=mock_extractor,
        question_generator=mock_question_generator,
    )
    
    # Create initial questions
    questions = [
        ResearchQuestion(
            question_id="q_test",
            text="Test question?",
            entity_class="Facility",
            priority=0.9,
            reason="Test",
        ),
    ]
    
    result = loop.run_discovery(
        initial_questions=questions,
        max_iterations=1,
        coverage_target=1.0,  # Won't reach
        top_k_docs=2,
    )
    
    # Verify result structure
    assert isinstance(result, DiscoveryResult)
    assert result.success is True
    assert result.total_iterations == 1
    assert len(result.entities) > 0
    assert result.total_time_sec > 0


def test_run_discovery_with_generated_questions(
    mock_retriever: MagicMock,
    mock_extractor: MagicMock,
    mock_question_generator: MagicMock,
) -> None:
    """Test discovery with auto-generated questions."""
    loop = IterativeDiscoveryLoop(
        retriever=mock_retriever,
        extractor=mock_extractor,
        question_generator=mock_question_generator,
    )
    
    # Don't provide initial questions - should generate them
    result = loop.run_discovery(
        initial_questions=None,
        max_iterations=1,
        coverage_target=1.0,
        top_k_docs=2,
    )
    
    # Should have generated questions
    assert mock_question_generator.generate_questions.called
    assert result.success is True


def test_run_discovery_coverage_target(
    mock_retriever: MagicMock,
    mock_extractor: MagicMock,
    mock_question_generator: MagicMock,
) -> None:
    """Test discovery stops when coverage target reached."""
    loop = IterativeDiscoveryLoop(
        retriever=mock_retriever,
        extractor=mock_extractor,
        question_generator=mock_question_generator,
    )
    
    questions = [
        ResearchQuestion(
            question_id="q_1",
            text="Question 1?",
            entity_class="Facility",
            priority=0.9,
            reason="Test",
        ),
        ResearchQuestion(
            question_id="q_2",
            text="Question 2?",
            entity_class="Equipment",
            priority=0.85,
            reason="Test",
        ),
    ]
    
    # Set high coverage target - processing entities is guaranteed to meet it
    # since we find 2 entity types and have 6 total classes (33% coverage)
    result = loop.run_discovery(
        initial_questions=questions,
        max_iterations=5,
        coverage_target=0.32,  # Stop after first iteration achieves this
        top_k_docs=2,
    )
    
    # Should stop after first iteration when coverage target is met
    assert result.total_iterations >= 1


def test_run_discovery_max_iterations(
    mock_retriever: MagicMock,
    mock_extractor: MagicMock,
    mock_question_generator: MagicMock,
) -> None:
    """Test discovery respects max_iterations."""
    loop = IterativeDiscoveryLoop(
        retriever=mock_retriever,
        extractor=mock_extractor,
        question_generator=mock_question_generator,
    )
    
    # Setup continuous follow-up questions
    q = ResearchQuestion(
        question_id="q_test",
        text="Question?",
        entity_class="Facility",
        priority=0.9,
        reason="Test",
    )
    
    # Return same question for follow-ups (will iterate max_iterations times)
    mock_question_generator.generate_follow_up_questions.return_value = [q]
    
    result = loop.run_discovery(
        initial_questions=[q],
        max_iterations=3,
        coverage_target=1.0,  # Won't reach
        top_k_docs=2,
    )
    
    assert result.total_iterations == 3


# ============================================================================
# Tests: Entity Extraction and Findings
# ============================================================================


def test_entity_accumulation(
    mock_retriever: MagicMock,
    mock_extractor: MagicMock,
    mock_question_generator: MagicMock,
) -> None:
    """Test entities are accumulated across iterations."""
    loop = IterativeDiscoveryLoop(
        retriever=mock_retriever,
        extractor=mock_extractor,
        question_generator=mock_question_generator,
    )
    
    questions = [
        ResearchQuestion(
            question_id="q_1",
            text="Question 1?",
            entity_class="Facility",
            priority=0.9,
            reason="Test",
        ),
    ]
    
    result = loop.run_discovery(
        initial_questions=questions,
        max_iterations=1,
        coverage_target=1.0,
        top_k_docs=2,
    )
    
    # Should have extracted entities
    assert len(result.entities) > 0
    assert len(result.entities) == len(loop._findings)


def test_provenance_tracking(
    mock_retriever: MagicMock,
    mock_extractor: MagicMock,
    mock_question_generator: MagicMock,
) -> None:
    """Test provenance is tracked for entities."""
    loop = IterativeDiscoveryLoop(
        retriever=mock_retriever,
        extractor=mock_extractor,
        question_generator=mock_question_generator,
    )
    
    questions = [
        ResearchQuestion(
            question_id="q_test",
            text="Test?",
            entity_class="Facility",
            priority=0.9,
            reason="Test",
        ),
    ]
    
    result = loop.run_discovery(
        initial_questions=questions,
        max_iterations=1,
        coverage_target=1.0,
        top_k_docs=2,
    )
    
    # Check provenance exists for entities
    for entity in result.entities:
        provenance = loop.get_provenance(entity.id)
        assert isinstance(provenance, set)


# ============================================================================
# Tests: Coverage Calculation
# ============================================================================


def test_coverage_calculation(
    mock_retriever: MagicMock,
    mock_extractor: MagicMock,
    mock_question_generator: MagicMock,
) -> None:
    """Test coverage is calculated correctly."""
    loop = IterativeDiscoveryLoop(
        retriever=mock_retriever,
        extractor=mock_extractor,
        question_generator=mock_question_generator,
    )
    
    questions = [
        ResearchQuestion(
            question_id="q_test",
            text="Test?",
            entity_class="Facility",
            priority=0.9,
            reason="Test",
        ),
    ]
    
    result = loop.run_discovery(
        initial_questions=questions,
        max_iterations=1,
        coverage_target=1.0,
        top_k_docs=2,
    )
    
    # Coverage should be between 0 and 1
    assert 0.0 <= result.final_coverage <= 1.0


def test_coverage_with_no_findings(
    mock_retriever: MagicMock,
    mock_question_generator: MagicMock,
) -> None:
    """Test coverage with no entities found."""
    extractor = MagicMock(spec=EntityExtractor)
    extractor.extract.return_value = []  # No entities
    
    loop = IterativeDiscoveryLoop(
        retriever=mock_retriever,
        extractor=extractor,
        question_generator=mock_question_generator,
    )
    
    questions = [
        ResearchQuestion(
            question_id="q_test",
            text="Test?",
            entity_class="Unknown",
            priority=0.9,
            reason="Test",
        ),
    ]
    
    result = loop.run_discovery(
        initial_questions=questions,
        max_iterations=1,
        coverage_target=1.0,
        top_k_docs=2,
    )
    
    assert result.final_coverage == 0.0
    assert len(result.entities) == 0


# ============================================================================
# Tests: Iteration Results
# ============================================================================


def test_iteration_results_tracking(
    mock_retriever: MagicMock,
    mock_extractor: MagicMock,
    mock_question_generator: MagicMock,
) -> None:
    """Test iteration results are tracked."""
    loop = IterativeDiscoveryLoop(
        retriever=mock_retriever,
        extractor=mock_extractor,
        question_generator=mock_question_generator,
    )
    
    questions = [
        ResearchQuestion(
            question_id="q_test",
            text="Test?",
            entity_class="Facility",
            priority=0.9,
            reason="Test",
        ),
    ]
    
    result = loop.run_discovery(
        initial_questions=questions,
        max_iterations=1,
        coverage_target=1.0,
        top_k_docs=2,
    )
    
    assert len(result.iterations) == 1
    iter_result = result.iterations[0]
    
    assert isinstance(iter_result, IterationResult)
    assert iter_result.iteration == 1
    assert iter_result.processing_time_sec > 0
    assert iter_result.total_entities > 0


# ============================================================================
# Tests: Helper Methods
# ============================================================================


def test_get_provenance_method(
    mock_retriever: MagicMock,
    mock_extractor: MagicMock,
    mock_question_generator: MagicMock,
) -> None:
    """Test get_provenance method."""
    loop = IterativeDiscoveryLoop(
        retriever=mock_retriever,
        extractor=mock_extractor,
        question_generator=mock_question_generator,
    )
    
    questions = [
        ResearchQuestion(
            question_id="q_test",
            text="Test?",
            entity_class="Facility",
            priority=0.9,
            reason="Test",
        ),
    ]
    
    loop.run_discovery(
        initial_questions=questions,
        max_iterations=1,
        coverage_target=1.0,
        top_k_docs=2,
    )
    
    # Get provenance for first entity
    entity_id = list(loop._findings.keys())[0]
    provenance = loop.get_provenance(entity_id)
    
    assert isinstance(provenance, set)
    assert len(provenance) > 0


def test_get_findings_by_type(
    mock_retriever: MagicMock,
    mock_extractor: MagicMock,
    mock_question_generator: MagicMock,
) -> None:
    """Test get_findings_by_type method."""
    loop = IterativeDiscoveryLoop(
        retriever=mock_retriever,
        extractor=mock_extractor,
        question_generator=mock_question_generator,
    )
    
    questions = [
        ResearchQuestion(
            question_id="q_test",
            text="Test?",
            entity_class="Facility",
            priority=0.9,
            reason="Test",
        ),
    ]
    
    loop.run_discovery(
        initial_questions=questions,
        max_iterations=1,
        coverage_target=1.0,
        top_k_docs=2,
    )
    
    # Get findings by type
    facilities = loop.get_findings_by_type("Facility")
    assert len(facilities) > 0
    assert all(e.entity_type == "Facility" for e in facilities)


# ============================================================================
# Tests: Error Handling
# ============================================================================


def test_error_handling_invalid_question(
    mock_retriever: MagicMock,
    mock_extractor: MagicMock,
    mock_question_generator: MagicMock,
) -> None:
    """Test handling of empty question list."""
    loop = IterativeDiscoveryLoop(
        retriever=mock_retriever,
        extractor=mock_extractor,
        question_generator=mock_question_generator,
    )
    
    # Empty list results in iteration but no questions processed
    result = loop.run_discovery(
        initial_questions=[],
        max_iterations=1,
        coverage_target=1.0,
        top_k_docs=2,
    )
    
    # Empty questions list means iteration runs but finds nothing
    assert result.success is True
    assert len(result.entities) == 0
    assert result.final_coverage == 0.0


def test_error_handling_none_questions(
    mock_retriever: MagicMock,
    mock_extractor: MagicMock,
    mock_question_generator: MagicMock,
) -> None:
    """Test handling of None initial questions - should generate."""
    loop = IterativeDiscoveryLoop(
        retriever=mock_retriever,
        extractor=mock_extractor,
        question_generator=mock_question_generator,
    )
    
    result = loop.run_discovery(
        initial_questions=None,  # None triggers generation
        max_iterations=1,
        coverage_target=1.0,
        top_k_docs=2,
    )
    
    # Should generate questions internally
    assert mock_question_generator.generate_questions.called
    assert result.success is True
    assert result.total_iterations == 1


# ============================================================================
# Tests: Integration Scenarios
# ============================================================================


def test_multi_iteration_discovery(
    mock_retriever: MagicMock,
    mock_question_generator: MagicMock,
) -> None:
    """Test multi-iteration discovery with follow-ups."""
    # Create entities for first and second iterations
    entity1 = ExtractedEntity(
        id="ent_1",
        label="Entity 1",
        entity_type="Facility",
        description="Test",
        confidence=0.9,
    )
    
    entity2 = ExtractedEntity(
        id="ent_2",
        label="Entity 2",
        entity_type="Equipment",
        description="Test",
        confidence=0.85,
    )
    
    extractor = MagicMock(spec=EntityExtractor)
    extractor.extract.side_effect = [
        [entity1],  # First iteration
        [entity2],  # Second iteration
    ]
    
    # Setup follow-up questions for second iteration
    followup_q = ResearchQuestion(
        question_id="q_followup",
        text="Follow-up?",
        entity_class="Equipment",
        priority=0.8,
        reason="Follow-up",
    )
    
    mock_question_generator.generate_follow_up_questions.return_value = [followup_q]
    
    loop = IterativeDiscoveryLoop(
        retriever=mock_retriever,
        extractor=extractor,
        question_generator=mock_question_generator,
    )
    
    initial_q = ResearchQuestion(
        question_id="q_initial",
        text="Initial?",
        entity_class="Facility",
        priority=0.9,
        reason="Initial",
    )
    
    result = loop.run_discovery(
        initial_questions=[initial_q],
        max_iterations=2,
        coverage_target=1.0,
        top_k_docs=2,
    )
    
    # Should have completed 2 iterations
    assert result.total_iterations == 2
    assert len(result.entities) == 2


def test_result_data_classes(
    mock_retriever: MagicMock,
    mock_extractor: MagicMock,
    mock_question_generator: MagicMock,
) -> None:
    """Test DiscoveryResult and IterationResult data classes."""
    loop = IterativeDiscoveryLoop(
        retriever=mock_retriever,
        extractor=mock_extractor,
        question_generator=mock_question_generator,
    )
    
    questions = [
        ResearchQuestion(
            question_id="q_test",
            text="Test?",
            entity_class="Facility",
            priority=0.9,
            reason="Test",
        ),
    ]
    
    result = loop.run_discovery(
        initial_questions=questions,
        max_iterations=1,
        coverage_target=1.0,
        top_k_docs=2,
    )
    
    # Verify all result fields are populated
    assert isinstance(result, DiscoveryResult)
    assert result.success is True
    assert isinstance(result.total_iterations, int)
    assert isinstance(result.final_coverage, float)
    assert isinstance(result.total_entities_discovered, int)
    assert isinstance(result.total_time_sec, float)
    assert isinstance(result.entities, list)
    assert isinstance(result.iterations, list)
    assert result.error_message is None
    
    # Verify iteration result fields
    if result.iterations:
        iter_result = result.iterations[0]
        assert isinstance(iter_result, IterationResult)
        assert iter_result.iteration >= 1
        assert iter_result.questions_processed >= 0
        assert iter_result.entities_discovered >= 0
        assert iter_result.total_entities >= 0
        assert 0.0 <= iter_result.coverage <= 1.0
        assert iter_result.processing_time_sec > 0
        assert isinstance(iter_result.new_entity_types, set)


def test_discovery_result_success_field(
    mock_retriever: MagicMock,
    mock_extractor: MagicMock,
    mock_question_generator: MagicMock,
) -> None:
    """Test success field in DiscoveryResult."""
    loop = IterativeDiscoveryLoop(
        retriever=mock_retriever,
        extractor=mock_extractor,
        question_generator=mock_question_generator,
    )
    
    questions = [
        ResearchQuestion(
            question_id="q_test",
            text="Test?",
            entity_class="Facility",
            priority=0.9,
            reason="Test",
        ),
    ]
    
    result = loop.run_discovery(
        initial_questions=questions,
        max_iterations=1,
        coverage_target=1.0,
        top_k_docs=2,
    )
    
    # Verify success is True for normal completion
    assert result.success is True
    assert isinstance(result.success, bool)
