#!/usr/bin/env python3
"""Test IterativeDiscoveryLoop.

Tests:
1. Discovery loop initialization
2. Question processing
3. Coverage calculation
4. Provenance tracking
5. End-to-end discovery
"""

import sys
from pathlib import Path

# Setup paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import structlog
from unittest.mock import MagicMock, patch

from kgbuilder.agents.discovery_loop import (
    DiscoveryResult,
    IterativeDiscoveryLoop,
    IterationResult,
)
from kgbuilder.agents.question_generator import QuestionGenerationAgent, ResearchQuestion
from kgbuilder.core.models import ExtractedEntity
from kgbuilder.retrieval import RetrievalResult


structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger(__name__)


def create_mock_retriever():
    """Create a mock FusionRAGRetriever."""
    retriever = MagicMock()
    
    # Mock retrieve method to return sample documents
    def retrieve_side_effect(query: str, top_k: int):
        return [
            RetrievalResult(
                doc_id="doc1",
                content="The nuclear reactor facility requires emergency cooling systems. "
                        "Multiple reactors are present at the site.",
                score=0.9,
                metadata={"source": "safety_report.pdf"},
            ),
            RetrievalResult(
                doc_id="doc2",
                content="Facility operations include routine maintenance and inspections. "
                        "These are critical for safety.",
                score=0.8,
                metadata={"source": "operations_manual.pdf"},
            ),
        ]
    
    retriever.retrieve.side_effect = retrieve_side_effect
    return retriever


def create_mock_extractor():
    """Create a mock EnsembleExtractor."""
    extractor = MagicMock()
    
    # Mock extract to return entities
    def extract_side_effect(text: str):
        entities = []
        if "reactor" in text.lower():
            entities.append(
                ExtractedEntity(
                    id="ent1",
                    label="Nuclear Reactor",
                    entity_type="Facility",
                    confidence=0.95,
                    description="A nuclear reactor facility",
                )
            )
        if "facility" in text.lower():
            entities.append(
                ExtractedEntity(
                    id="ent2",
                    label="Cooling System",
                    entity_type="Facility",
                    confidence=0.90,
                    description="Emergency cooling system",
                )
            )
        if "operation" in text.lower():
            entities.append(
                ExtractedEntity(
                    id="ent3",
                    label="Maintenance",
                    entity_type="Operation",
                    confidence=0.85,
                    description="Routine maintenance operation",
                )
            )
        return entities
    
    extractor.extract.side_effect = extract_side_effect
    return extractor


def test_discovery_loop_initialization():
    """Test DiscoveryLoop initialization."""
    logger.info("test_start", test="discovery_loop_initialization")
    
    mock_retriever = create_mock_retriever()
    mock_extractor = create_mock_extractor()
    mock_question_gen = MagicMock(spec=QuestionGenerationAgent)
    
    loop = IterativeDiscoveryLoop(
        retriever=mock_retriever,
        extractor=mock_extractor,
        question_generator=mock_question_gen,
    )
    
    assert loop is not None
    assert loop._findings == {}
    assert loop._provenance == {}
    
    logger.info("test_pass", test="discovery_loop_initialization")


def test_run_discovery_basic():
    """Test basic discovery loop execution."""
    logger.info("test_start", test="run_discovery_basic")
    
    mock_retriever = create_mock_retriever()
    mock_extractor = create_mock_extractor()
    mock_question_gen = MagicMock(spec=QuestionGenerationAgent)
    mock_question_gen._ontology.get_all_classes.return_value = [
        "Facility", "Operation", "Document"
    ]
    
    loop = IterativeDiscoveryLoop(
        retriever=mock_retriever,
        extractor=mock_extractor,
        question_generator=mock_question_gen,
    )
    
    # Create test questions
    questions = [
        ResearchQuestion(
            question_id="q1",
            text="What are Facilities?",
            entity_class="Facility",
            priority=0.9,
            reason="test",
        ),
    ]
    
    # Mock question generator to return empty list after first iteration
    mock_question_gen.generate_follow_up_questions.return_value = []
    
    # Run discovery
    result = loop.run_discovery(
        initial_questions=questions,
        max_iterations=1,
        coverage_target=0.0,  # Run one iteration
        top_k_docs=2,
    )
    
    # Verify results
    assert result.success
    assert result.total_iterations == 1
    assert len(result.entities) > 0
    assert len(result.iterations) == 1
    
    logger.info(
        "test_pass",
        test="run_discovery_basic",
        entities=len(result.entities),
        coverage=f"{result.final_coverage:.2f}",
    )


def test_provenance_tracking():
    """Test provenance tracking during discovery."""
    logger.info("test_start", test="provenance_tracking")
    
    mock_retriever = create_mock_retriever()
    mock_extractor = create_mock_extractor()
    mock_question_gen = MagicMock(spec=QuestionGenerationAgent)
    mock_question_gen._ontology.get_all_classes.return_value = ["Facility", "Operation"]
    
    loop = IterativeDiscoveryLoop(
        retriever=mock_retriever,
        extractor=mock_extractor,
        question_generator=mock_question_gen,
    )
    
    questions = [
        ResearchQuestion(
            question_id="q1",
            text="What are Facilities?",
            entity_class="Facility",
            priority=0.9,
            reason="test",
        ),
    ]
    
    mock_question_gen.generate_follow_up_questions.return_value = []
    
    # Run discovery
    result = loop.run_discovery(
        initial_questions=questions,
        max_iterations=1,
        coverage_target=0.0,
        top_k_docs=2,
    )
    
    # Check provenance was tracked
    for entity in result.entities:
        provenance = loop.get_provenance(entity.id)
        assert len(provenance) > 0, f"Entity {entity.id} should have provenance"
        assert "doc1" in provenance or "doc2" in provenance
    
    logger.info(
        "test_pass",
        test="provenance_tracking",
        entities_with_provenance=len(result.entities),
    )


def test_coverage_calculation():
    """Test coverage calculation."""
    logger.info("test_start", test="coverage_calculation")
    
    mock_retriever = create_mock_retriever()
    mock_extractor = create_mock_extractor()
    mock_question_gen = MagicMock(spec=QuestionGenerationAgent)
    mock_question_gen._ontology.get_all_classes.return_value = [
        "Facility", "Operation", "Document", "Hazard"
    ]
    
    loop = IterativeDiscoveryLoop(
        retriever=mock_retriever,
        extractor=mock_extractor,
        question_generator=mock_question_gen,
    )
    
    questions = [
        ResearchQuestion(
            question_id="q1",
            text="What are Facilities?",
            entity_class="Facility",
            priority=0.9,
            reason="test",
        ),
    ]
    
    mock_question_gen.generate_follow_up_questions.return_value = []
    
    # Run discovery
    result = loop.run_discovery(
        initial_questions=questions,
        max_iterations=1,
        coverage_target=0.0,
        top_k_docs=2,
    )
    
    # Coverage should be > 0 (we found Facility and Operation)
    assert result.final_coverage > 0.0
    assert result.final_coverage <= 1.0
    
    logger.info(
        "test_pass",
        test="coverage_calculation",
        coverage=f"{result.final_coverage:.2f}",
    )


def test_get_findings_by_type():
    """Test filtering findings by type."""
    logger.info("test_start", test="get_findings_by_type")
    
    mock_retriever = create_mock_retriever()
    mock_extractor = create_mock_extractor()
    mock_question_gen = MagicMock(spec=QuestionGenerationAgent)
    mock_question_gen._ontology.get_all_classes.return_value = [
        "Facility", "Operation"
    ]
    
    loop = IterativeDiscoveryLoop(
        retriever=mock_retriever,
        extractor=mock_extractor,
        question_generator=mock_question_gen,
    )
    
    questions = [
        ResearchQuestion(
            question_id="q1",
            text="What are Facilities and Operations?",
            entity_class="Facility",
            priority=0.9,
            reason="test",
        ),
    ]
    
    mock_question_gen.generate_follow_up_questions.return_value = []
    
    # Run discovery
    result = loop.run_discovery(
        initial_questions=questions,
        max_iterations=1,
        coverage_target=0.0,
        top_k_docs=2,
    )
    
    # Get findings by type
    facilities = loop.get_findings_by_type("Facility")
    operations = loop.get_findings_by_type("Operation")
    
    assert len(facilities) > 0, "Should find some facilities"
    assert len(operations) > 0, "Should find some operations"
    assert all(e.entity_type == "Facility" for e in facilities)
    assert all(e.entity_type == "Operation" for e in operations)
    
    logger.info(
        "test_pass",
        test="get_findings_by_type",
        facilities=len(facilities),
        operations=len(operations),
    )


def main() -> None:
    """Run all tests."""
    logger.info("===== TEST SUITE: IterativeDiscoveryLoop =====")
    
    tests = [
        test_discovery_loop_initialization,
        test_run_discovery_basic,
        test_provenance_tracking,
        test_coverage_calculation,
        test_get_findings_by_type,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            logger.error(
                "test_failed",
                test=test_func.__name__,
                error=str(e),
            )
            failed += 1
        except Exception as e:
            logger.error(
                "test_error",
                test=test_func.__name__,
                error=str(e),
                exc_info=True,
            )
            failed += 1
    
    logger.info(
        "===== TEST SUMMARY =====",
        total=len(tests),
        passed=passed,
        failed=failed,
    )
    
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
