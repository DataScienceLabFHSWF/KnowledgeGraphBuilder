#!/usr/bin/env python3
"""Test QuestionGenerationAgent.

Tests:
1. Question generation from ontology
2. Coverage calculation
3. Question prioritization
4. Follow-up question generation
"""

import sys
from pathlib import Path

# Setup paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from unittest.mock import MagicMock

import structlog

from kgbuilder.agents.question_generator import (
    QuestionGenerationAgent,
    ResearchQuestion,
)
from kgbuilder.core.models import ExtractedEntity

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger(__name__)


def test_question_generation_basic() -> None:
    """Test basic question generation from ontology."""
    logger.info("test_start", test="question_generation_basic")

    # Create mock ontology service
    mock_ontology = MagicMock()
    mock_ontology.get_all_classes.return_value = [
        "Facility",
        "SafetyDocument",
        "Operation",
        "Requirement",
        "Hazard",
        "Mitigation",
    ]

    # Create agent with no existing entities
    agent = QuestionGenerationAgent(mock_ontology, existing_entities=[])

    # Generate questions
    questions = agent.generate_questions(max_questions=10)

    # Verify
    assert len(questions) > 0, "Should generate questions for uncovered classes"
    assert all(isinstance(q, ResearchQuestion) for q in questions)
    assert all(q.entity_class in mock_ontology.get_all_classes() for q in questions)

    logger.info(
        "test_pass",
        test="question_generation_basic",
        questions_generated=len(questions),
        top_question=questions[0].text if questions else "none",
    )


def test_coverage_calculation() -> None:
    """Test coverage calculation from existing entities."""
    logger.info("test_start", test="coverage_calculation")

    mock_ontology = MagicMock()
    ontology_classes = ["Facility", "Operation", "Document"]
    mock_ontology.get_all_classes.return_value = ontology_classes

    # Create entities
    existing = [
        ExtractedEntity(
            id="fac1",
            label="Reactor",
            entity_type="Facility",
            confidence=0.9,
            description="Test facility",
        ),
        ExtractedEntity(
            id="fac2",
            label="Cooling System",
            entity_type="Facility",
            confidence=0.85,
            description="Test cooling",
        ),
        ExtractedEntity(
            id="doc1",
            label="Safety Report",
            entity_type="Document",
            confidence=0.95,
            description="Test doc",
        ),
    ]

    agent = QuestionGenerationAgent(mock_ontology, existing_entities=existing)
    coverage = agent._calculate_coverage(ontology_classes)

    # Verify
    assert coverage["Facility"] == 2, "Should count 2 Facility entities"
    assert coverage["Document"] == 1, "Should count 1 Document entity"
    assert coverage["Operation"] == 0, "Should count 0 Operation entities"

    logger.info(
        "test_pass",
        test="coverage_calculation",
        coverage=dict(coverage),
    )


def test_question_prioritization() -> None:
    """Test question prioritization by importance."""
    logger.info("test_start", test="question_prioritization")

    mock_ontology = MagicMock()
    classes = ["Facility", "Operation", "Hazard"]
    mock_ontology.get_all_classes.return_value = classes

    agent = QuestionGenerationAgent(mock_ontology, existing_entities=[])

    # Create sample questions with different priorities
    questions = [
        ResearchQuestion(
            question_id="q1",
            text="What are Hazards?",
            entity_class="Hazard",
            priority=0.5,
            reason="test",
        ),
        ResearchQuestion(
            question_id="q2",
            text="What are Facilities?",
            entity_class="Facility",
            priority=0.3,
            reason="test",
        ),
        ResearchQuestion(
            question_id="q3",
            text="What are Operations?",
            entity_class="Operation",
            priority=0.8,
            reason="test",
        ),
    ]

    # Prioritize
    prioritized = agent._prioritize_questions(questions, classes)

    # Verify ordering (should be sorted by priority, highest first)
    # Note: _prioritize_questions recalculates priorities, so we just verify it returns sorted
    assert len(prioritized) == 3
    assert prioritized[0].priority >= prioritized[1].priority >= prioritized[2].priority

    logger.info(
        "test_pass",
        test="question_prioritization",
        order=[q.entity_class for q in prioritized],
    )


def test_follow_up_question_generation() -> None:
    """Test follow-up question generation from discoveries."""
    logger.info("test_start", test="follow_up_question_generation")

    mock_ontology = MagicMock()
    mock_ontology.get_all_classes.return_value = [
        "Facility",
        "Operation",
        "Document",
    ]

    # Create agent
    agent = QuestionGenerationAgent(mock_ontology, existing_entities=[])

    # Create discovery (new entity types found)
    discoveries = [
        ExtractedEntity(
            id="op1",
            label="Decommissioning",
            entity_type="Operation",
            confidence=0.9,
            description="test",
        ),
        ExtractedEntity(
            id="op2",
            label="Inspection",
            entity_type="Operation",
            confidence=0.85,
            description="test",
        ),
    ]

    # Create current questions (already asked about Facility)
    current_questions = [
        ResearchQuestion(
            question_id="q1",
            text="What are Facilities?",
            entity_class="Facility",
            priority=0.9,
            reason="test",
        ),
    ]

    # Generate follow-ups
    follow_ups = agent.generate_follow_up_questions(
        discoveries=discoveries,
        current_questions=current_questions,
        max_new_questions=5,
    )

    # Verify
    assert len(follow_ups) > 0, "Should generate follow-up questions"
    assert all(q.follow_up for q in follow_ups), "All should be marked as follow-up"
    assert "Operation" in [q.entity_class for q in follow_ups]

    logger.info(
        "test_pass",
        test="follow_up_question_generation",
        follow_ups=len(follow_ups),
        classes_found=[q.entity_class for q in follow_ups],
    )


def test_sanitize_class_name() -> None:
    """Test class name sanitization for IDs."""
    logger.info("test_start", test="sanitize_class_name")

    mock_ontology = MagicMock()
    agent = QuestionGenerationAgent(mock_ontology, existing_entities=[])

    # Test various inputs
    tests = [
        ("Facility", "facility"),
        ("SafetyDocument", "safetydocument"),
        ("Emergency-Cooling", "emergency_cooling"),
        ("System v2.0", "system_v2_0"),
        ("_Private", "private"),
        ("AllCaps", "allcaps"),
    ]

    for input_name, expected in tests:
        result = agent._sanitize_class_name(input_name)
        assert result == expected, f"{input_name} -> {result} != {expected}"

    logger.info(
        "test_pass",
        test="sanitize_class_name",
        tests_passed=len(tests),
    )


def main() -> None:
    """Run all tests."""
    logger.info("===== TEST SUITE: QuestionGenerationAgent =====")

    tests = [
        test_question_generation_basic,
        test_coverage_calculation,
        test_question_prioritization,
        test_follow_up_question_generation,
        test_sanitize_class_name,
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
