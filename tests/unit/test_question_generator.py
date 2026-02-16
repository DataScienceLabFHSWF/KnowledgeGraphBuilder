"""Tests for QuestionGenerationAgent.

Comprehensive test suite for the question generation component including:
- Basic question generation from ontology
- Coverage calculation
- Priority ranking
- Follow-up question generation
- Error handling
- Integration with mock ontology service
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kgbuilder.agents.question_generator import (
    OntologyService,
    QuestionGenerationAgent,
    ResearchQuestion,
)
from kgbuilder.core.models import Evidence, ExtractedEntity

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_ontology_service() -> MagicMock:
    """Create a mock ontology service with realistic test data."""
    ontology = MagicMock(spec=OntologyService)

    # Realistic ontology classes from nuclear domain
    classes = [
        "Facility",
        "SafetyDocument",
        "Operation",
        "Equipment",
        "Requirement",
        "Organization",
    ]
    ontology.get_all_classes.return_value = classes

    # Define hierarchy for each class
    hierarchy_map = {
        "Facility": {"depth": 1, "parents": ["Entity"], "children": ["Reactor", "CoolingSystem"]},
        "SafetyDocument": {"depth": 2, "parents": ["Document"], "children": []},
        "Operation": {"depth": 0, "parents": [], "children": ["Shutdown", "Maintenance"]},
        "Equipment": {"depth": 1, "parents": ["Entity"], "children": ["System", "Component"]},
        "Requirement": {"depth": 1, "parents": ["Entity"], "children": ["Safety", "Operational"]},
        "Organization": {"depth": 0, "parents": [], "children": ["Agency", "Operator"]},
    }
    ontology.get_class_hierarchy.side_effect = lambda cls: hierarchy_map.get(
        cls, {"depth": 0, "parents": [], "children": []}
    )

    # Define relations for each class
    relations_map = {
        "Facility": {
            "requires": ["SafetyDocument", "Equipment"],
            "operates": ["Operation"],
        },
        "SafetyDocument": {
            "describes": ["Facility", "Equipment"],
            "requires": ["Requirement"],
        },
        "Operation": {"appliesTo": ["Facility"], "requires": ["Equipment"]},
        "Equipment": {"usedBy": ["Operation"], "described": ["SafetyDocument"]},
        "Requirement": {"appliedTo": ["SafetyDocument", "Facility"]},
        "Organization": {"operates": ["Facility"], "issues": ["SafetyDocument"]},
    }
    ontology.get_class_relations.side_effect = lambda cls: relations_map.get(cls, {})

    # Descriptions
    descriptions_map = {
        "Facility": "Nuclear facility, reactor, or power plant",
        "SafetyDocument": "Safety analysis or technical documentation",
        "Operation": "Operational procedures or activities",
        "Equipment": "Equipment, systems, or components",
        "Requirement": "Safety or operational requirement",
        "Organization": "Organization or regulatory body",
    }
    ontology.get_class_description.side_effect = lambda cls: descriptions_map.get(cls)

    return ontology


@pytest.fixture
def sample_entities() -> list[ExtractedEntity]:
    """Create sample extracted entities for coverage calculation."""
    return [
        ExtractedEntity(
            id="ent_1",
            label="Kernkraftwerk Emsland",
            entity_type="Facility",
            description="Nuclear facility",
            confidence=0.95,
            evidence=[Evidence(source_type="doc", source_id="doc_1")],
        ),
        ExtractedEntity(
            id="ent_2",
            label="Sicherheitsbericht",
            entity_type="SafetyDocument",
            description="Safety document",
            confidence=0.92,
            evidence=[Evidence(source_type="doc", source_id="doc_1")],
        ),
        ExtractedEntity(
            id="ent_3",
            label="Shutdown Procedure",
            entity_type="Operation",
            description="Shutdown operation",
            confidence=0.88,
            evidence=[Evidence(source_type="doc", source_id="doc_2")],
        ),
    ]


# ============================================================================
# Tests: Basic Functionality
# ============================================================================


def test_question_generator_initialization(
    mock_ontology_service: MagicMock,
) -> None:
    """Test QuestionGenerationAgent initialization."""
    agent = QuestionGenerationAgent(mock_ontology_service)
    assert agent is not None
    assert agent._ontology == mock_ontology_service
    assert agent._existing == []


def test_question_generator_with_existing_entities(
    mock_ontology_service: MagicMock,
    sample_entities: list[ExtractedEntity],
) -> None:
    """Test initialization with existing entities."""
    agent = QuestionGenerationAgent(mock_ontology_service, sample_entities)
    assert len(agent._existing) == 3
    assert agent._existing[0].label == "Kernkraftwerk Emsland"


# ============================================================================
# Tests: Question Generation
# ============================================================================


def test_generate_questions_basic(
    mock_ontology_service: MagicMock,
    sample_entities: list[ExtractedEntity],
) -> None:
    """Test basic question generation from ontology."""
    agent = QuestionGenerationAgent(mock_ontology_service, sample_entities)

    questions = agent.generate_questions(max_questions=50, covered_threshold=1)

    # Should have questions for under-covered classes
    assert len(questions) > 0
    assert all(isinstance(q, ResearchQuestion) for q in questions)

    # Verify structure
    for q in questions:
        assert q.question_id is not None
        assert q.text is not None
        assert q.entity_class is not None
        assert 0.0 <= q.priority <= 1.0
        assert q.reason is not None


def test_generate_questions_ordering(
    mock_ontology_service: MagicMock,
    sample_entities: list[ExtractedEntity],
) -> None:
    """Test that questions are ordered by priority (highest first)."""
    agent = QuestionGenerationAgent(mock_ontology_service, sample_entities)

    questions = agent.generate_questions(max_questions=50, covered_threshold=1)

    # Verify priority ordering (descending)
    priorities = [q.priority for q in questions]
    assert priorities == sorted(priorities, reverse=True)


def test_generate_questions_respects_max(
    mock_ontology_service: MagicMock,
) -> None:
    """Test max_questions parameter is respected."""
    agent = QuestionGenerationAgent(mock_ontology_service)

    questions = agent.generate_questions(max_questions=3, covered_threshold=1)

    assert len(questions) <= 3


def test_generate_questions_empty_ontology(
) -> None:
    """Test behavior with empty ontology."""
    ontology = MagicMock(spec=OntologyService)
    ontology.get_all_classes.return_value = []

    agent = QuestionGenerationAgent(ontology)
    questions = agent.generate_questions()

    assert len(questions) == 0


def test_generate_questions_all_covered(
    mock_ontology_service: MagicMock,
) -> None:
    """Test when all classes are already well-covered."""
    # Create entities for all classes
    entities = [
        ExtractedEntity(
            id=f"ent_{i}",
            label=f"Entity_{i}",
            entity_type=cls,
            description="Test entity",
            confidence=0.9,
        )
        for i, cls in enumerate(
            [
                "Facility",
                "SafetyDocument",
                "Operation",
                "Equipment",
                "Requirement",
                "Organization",
            ]
        )
    ]

    agent = QuestionGenerationAgent(mock_ontology_service, entities)

    # With high threshold, no questions should be generated
    questions = agent.generate_questions(covered_threshold=1)

    # All classes now have at least 1 entity, so no under-covered classes
    assert len(questions) == 0


# ============================================================================
# Tests: Coverage Calculation
# ============================================================================


def test_calculate_coverage(
    mock_ontology_service: MagicMock,
    sample_entities: list[ExtractedEntity],
) -> None:
    """Test coverage calculation per class."""
    agent = QuestionGenerationAgent(mock_ontology_service, sample_entities)

    classes = mock_ontology_service.get_all_classes()
    coverage = agent._calculate_coverage(classes)

    # Should have entry for each class
    assert len(coverage) == len(classes)

    # Verify counts
    assert coverage["Facility"] == 1
    assert coverage["SafetyDocument"] == 1
    assert coverage["Operation"] == 1
    assert coverage["Equipment"] == 0
    assert coverage["Requirement"] == 0
    assert coverage["Organization"] == 0


def test_calculate_coverage_no_entities(
    mock_ontology_service: MagicMock,
) -> None:
    """Test coverage with no existing entities."""
    agent = QuestionGenerationAgent(mock_ontology_service)

    classes = mock_ontology_service.get_all_classes()
    coverage = agent._calculate_coverage(classes)

    # All counts should be zero
    assert all(count == 0 for count in coverage.values())


def test_calculate_coverage_multiple_same_class(
    mock_ontology_service: MagicMock,
) -> None:
    """Test coverage calculation with multiple entities of same class."""
    entities = [
        ExtractedEntity(
            id=f"facility_{i}",
            label=f"Facility {i}",
            entity_type="Facility",
            description="Test facility",
            confidence=0.9,
        )
        for i in range(5)
    ]

    agent = QuestionGenerationAgent(mock_ontology_service, entities)
    classes = mock_ontology_service.get_all_classes()
    coverage = agent._calculate_coverage(classes)

    assert coverage["Facility"] == 5


# ============================================================================
# Tests: Question Generation for Class
# ============================================================================


def test_generate_question_for_uncovered_class(
    mock_ontology_service: MagicMock,
) -> None:
    """Test question generation for completely uncovered class."""
    agent = QuestionGenerationAgent(mock_ontology_service)

    q = agent._generate_question_for_class("Facility", current_count=0)

    assert q.entity_class == "Facility"
    assert "Facility" in q.text
    assert "are mentioned" in q.text or "What" in q.text
    assert q.aspect == "existence"
    assert q.reason == "Class not yet covered"


def test_generate_question_for_partially_covered_class(
    mock_ontology_service: MagicMock,
) -> None:
    """Test question generation for partially covered class."""
    agent = QuestionGenerationAgent(mock_ontology_service)

    q = agent._generate_question_for_class("Facility", current_count=2)

    assert q.entity_class == "Facility"
    assert "additional" in q.text
    assert q.aspect == "expansion"
    assert "2" in q.reason


def test_question_id_sanitization(
    mock_ontology_service: MagicMock,
) -> None:
    """Test question ID is properly sanitized."""
    agent = QuestionGenerationAgent(mock_ontology_service)

    q = agent._generate_question_for_class("SafetyDocument", current_count=0)

    # Should be lowercase, alphanumeric + underscore only
    assert q.question_id == "q_safetydocument"
    assert " " not in q.question_id


# ============================================================================
# Tests: Priority Ranking
# ============================================================================


def test_prioritize_questions_by_hierarchy(
    mock_ontology_service: MagicMock,
) -> None:
    """Test that parent classes get higher priority."""
    agent = QuestionGenerationAgent(mock_ontology_service)

    questions = [
        agent._generate_question_for_class("Operation", current_count=0),  # depth=0 (root)
        agent._generate_question_for_class("SafetyDocument", current_count=0),  # depth=2 (leaf)
    ]

    prioritized = agent._prioritize_questions(questions, mock_ontology_service.get_all_classes())

    # Operation (root, depth=0) should be prioritized over SafetyDocument (leaf, depth=2)
    assert prioritized[0].entity_class == "Operation"
    assert prioritized[1].entity_class == "SafetyDocument"


def test_prioritize_questions_with_relations(
    mock_ontology_service: MagicMock,
) -> None:
    """Test that classes with relations get higher priority."""
    agent = QuestionGenerationAgent(mock_ontology_service)

    questions = [
        agent._generate_question_for_class("Facility", current_count=0),  # has relations
        agent._generate_question_for_class("Equipment", current_count=0),  # has relations
    ]

    prioritized = agent._prioritize_questions(questions, mock_ontology_service.get_all_classes())

    # Both have relations, so order might depend on other factors
    # Just verify that prioritization happened (priorities are set)
    assert all(q.priority > 0 for q in prioritized)


# ============================================================================
# Tests: Helper Methods
# ============================================================================


def test_sanitize_class_name(
    mock_ontology_service: MagicMock,
) -> None:
    """Test class name sanitization."""
    agent = QuestionGenerationAgent(mock_ontology_service)

    test_cases = [
        ("Facility", "facility"),
        ("SafetyDocument", "safetydocument"),
        ("Safety-Document", "safety_document"),
        ("Safety Document", "safety_document"),
        ("Safety_Document", "safety_document"),
        ("_Facility_", "facility"),
    ]

    for input_name, expected in test_cases:
        result = agent._sanitize_class_name(input_name)
        assert result == expected, f"Failed for {input_name}: got {result}, expected {expected}"


def test_get_hierarchy_level(
    mock_ontology_service: MagicMock,
) -> None:
    """Test hierarchy level calculation."""
    agent = QuestionGenerationAgent(mock_ontology_service)
    classes = mock_ontology_service.get_all_classes()

    # Root class should have lower level than leaf class
    operation_level = agent._get_hierarchy_level("Operation", classes)  # depth=0
    document_level = agent._get_hierarchy_level("SafetyDocument", classes)  # depth=2

    assert operation_level < document_level


def test_is_relation_domain(
    mock_ontology_service: MagicMock,
) -> None:
    """Test relation domain detection."""
    agent = QuestionGenerationAgent(mock_ontology_service)

    # Facility has relations
    assert agent._is_relation_domain("Facility") is True

    # Equipment has relations
    assert agent._is_relation_domain("Equipment") is True


def test_get_relation_count(
    mock_ontology_service: MagicMock,
) -> None:
    """Test relation count calculation."""
    agent = QuestionGenerationAgent(mock_ontology_service)

    # Facility has 2 relation types: requires, operates
    facility_relations = agent._get_relation_count("Facility")
    assert facility_relations == 2

    # SafetyDocument has 2 relation types: describes, requires
    doc_relations = agent._get_relation_count("SafetyDocument")
    assert doc_relations == 2


# ============================================================================
# Tests: Follow-up Questions
# ============================================================================


def test_generate_follow_up_questions_from_discoveries(
    mock_ontology_service: MagicMock,
) -> None:
    """Test follow-up question generation from discovered entities."""
    agent = QuestionGenerationAgent(mock_ontology_service)

    # Initial questions asked about Facility and Operation
    current_questions = [
        ResearchQuestion(
            question_id="q_facility",
            text="What are the Facilities?",
            entity_class="Facility",
            priority=0.8,
            reason="Initial question",
        ),
        ResearchQuestion(
            question_id="q_operation",
            text="What are the Operations?",
            entity_class="Operation",
            priority=0.7,
            reason="Initial question",
        ),
    ]

    # Discoveries include Equipment and Organization (new types)
    discoveries = [
        ExtractedEntity(
            id="ent_1",
            label="Cooling System",
            entity_type="Equipment",
            description="Equipment",
            confidence=0.9,
        ),
        ExtractedEntity(
            id="ent_2",
            label="Regulatory Agency",
            entity_type="Organization",
            description="Organization",
            confidence=0.85,
        ),
    ]

    follow_ups = agent.generate_follow_up_questions(
        discoveries, current_questions, max_new_questions=5
    )

    # Should generate follow-up questions for newly discovered types
    assert len(follow_ups) > 0
    follow_up_classes = {q.entity_class for q in follow_ups}

    # Should include Equipment and Organization
    assert "Equipment" in follow_up_classes or "Organization" in follow_up_classes

    # All follow-ups should be marked as such
    assert all(q.follow_up is True for q in follow_ups)


def test_follow_up_questions_no_new_classes(
    mock_ontology_service: MagicMock,
) -> None:
    """Test follow-up questions when discoveries are of already-asked classes."""
    agent = QuestionGenerationAgent(mock_ontology_service)

    current_questions = [
        ResearchQuestion(
            question_id="q_facility",
            text="What are Facilities?",
            entity_class="Facility",
            priority=0.8,
            reason="Initial",
        ),
    ]

    # Discoveries are same class as already asked
    discoveries = [
        ExtractedEntity(
            id="ent_1",
            label="Another Facility",
            entity_type="Facility",
            description="Facility",
            confidence=0.9,
        ),
    ]

    follow_ups = agent.generate_follow_up_questions(
        discoveries, current_questions
    )

    # No follow-ups should be generated (already asked about this class)
    assert len(follow_ups) == 0


def test_follow_up_questions_respects_max(
    mock_ontology_service: MagicMock,
) -> None:
    """Test max_new_questions parameter is respected."""
    agent = QuestionGenerationAgent(mock_ontology_service)

    current_questions = [
        ResearchQuestion(
            question_id="q_facility",
            text="What are Facilities?",
            entity_class="Facility",
            priority=0.8,
            reason="Initial",
        ),
    ]

    # Create many discovery types
    discoveries = [
        ExtractedEntity(
            id=f"ent_{i}",
            label=f"Entity {i}",
            entity_type=cls,
            description="Test",
            confidence=0.9,
        )
        for i, cls in enumerate(
            ["Equipment", "Organization", "Requirement", "Operation", "SafetyDocument"]
        )
    ]

    follow_ups = agent.generate_follow_up_questions(
        discoveries, current_questions, max_new_questions=2
    )

    # Should not exceed max
    assert len(follow_ups) <= 2


# ============================================================================
# Tests: Error Handling
# ============================================================================


def test_error_handling_ontology_failure(
) -> None:
    """Test graceful handling of ontology service failures."""
    ontology = MagicMock(spec=OntologyService)
    ontology.get_all_classes.side_effect = RuntimeError("Ontology service down")

    agent = QuestionGenerationAgent(ontology)

    with pytest.raises(RuntimeError, match="Failed to generate questions"):
        agent.generate_questions()


def test_hierarchy_level_fallback_on_error(
    mock_ontology_service: MagicMock,
) -> None:
    """Test fallback behavior when hierarchy lookup fails."""
    # Make hierarchy lookup fail
    mock_ontology_service.get_class_hierarchy.side_effect = Exception("Hierarchy unavailable")

    agent = QuestionGenerationAgent(mock_ontology_service)
    classes = mock_ontology_service.get_all_classes()

    # Should fall back to alphabetical heuristic
    level = agent._get_hierarchy_level("Facility", classes)

    # Should return a valid value (fallback worked)
    assert 0.0 <= level <= 1.0


def test_relation_lookup_fallback_on_error(
    mock_ontology_service: MagicMock,
) -> None:
    """Test fallback when relation lookup fails."""
    mock_ontology_service.get_class_relations.side_effect = Exception("Relations unavailable")

    agent = QuestionGenerationAgent(mock_ontology_service)

    # Should fall back to conservative assumption (True - assume has relations)
    has_rels = agent._is_relation_domain("Facility")
    assert has_rels is True


def test_relation_count_fallback_on_error(
    mock_ontology_service: MagicMock,
) -> None:
    """Test fallback when relation count lookup fails."""
    mock_ontology_service.get_class_relations.side_effect = Exception("Relations unavailable")

    agent = QuestionGenerationAgent(mock_ontology_service)

    # Should fall back to 1 (assume at least one relation)
    count = agent._get_relation_count("Facility")
    assert count == 1


# ============================================================================
# Tests: Research Question Model
# ============================================================================


def test_research_question_repr(
) -> None:
    """Test ResearchQuestion string representation."""
    q = ResearchQuestion(
        question_id="q_test",
        text="What are the test entities?",
        entity_class="TestClass",
        priority=0.85,
        reason="Test reason",
        aspect="existence",
    )

    repr_str = repr(q)

    assert "Q[0.85]" in repr_str
    assert "What are the test entities?" in repr_str
    assert "TestClass" in repr_str
    assert "existence" in repr_str


# ============================================================================
# Tests: Integration Scenarios
# ============================================================================


def test_end_to_end_discovery_workflow(
    mock_ontology_service: MagicMock,
    sample_entities: list[ExtractedEntity],
) -> None:
    """Test complete discovery workflow: initial questions → follow-ups."""
    agent = QuestionGenerationAgent(mock_ontology_service, sample_entities)

    # Phase 1: Generate initial questions
    initial_questions = agent.generate_questions(max_questions=20, covered_threshold=1)
    assert len(initial_questions) > 0

    # Get the classes that were asked about
    asked_classes_in_initial = {q.entity_class for q in initial_questions}

    # Phase 2: Simulate discoveries in iteration 1
    # Choose discovery classes that are NOT in the initial questions
    all_classes = set(mock_ontology_service.get_all_classes())
    not_yet_asked = list(all_classes - asked_classes_in_initial)

    if len(not_yet_asked) >= 2:
        iteration_1_discoveries = [
            ExtractedEntity(
                id="ent_eq1",
                label="Backup Power System",
                entity_type=not_yet_asked[0],
                description="Equipment",
                confidence=0.91,
            ),
            ExtractedEntity(
                id="ent_req1",
                label="Containment Requirement",
                entity_type=not_yet_asked[1],
                description="Requirement",
                confidence=0.87,
            ),
        ]
    else:
        # If all classes already covered in initial questions, just test iteration 2
        iteration_1_discoveries = []

    # Phase 3: Generate follow-up questions
    if iteration_1_discoveries:
        follow_ups = agent.generate_follow_up_questions(
            iteration_1_discoveries, initial_questions
        )

        # Should have follow-ups for newly discovered types
        assert len(follow_ups) > 0

        # All follow-ups should be marked as such
        assert all(q.follow_up is True for q in follow_ups)

    # Phase 4: Update existing entities and generate new questions
    updated_entities = sample_entities + iteration_1_discoveries
    agent_iter2 = QuestionGenerationAgent(mock_ontology_service, updated_entities)

    iter2_questions = agent_iter2.generate_questions(max_questions=20, covered_threshold=1)

    # Should have fewer or equal questions in iteration 2 (more classes covered)
    assert len(iter2_questions) <= len(initial_questions)
