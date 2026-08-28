"""Tests for per-module extraction subagents and the orchestrator agent."""

from __future__ import annotations

from unittest.mock import MagicMock

from kgbuilder.agents.module_extraction_agent import ModuleExtractionAgent
from kgbuilder.agents.orchestrator_agent import ModuleBinding, OrchestratorAgent
from kgbuilder.agents.question_generator import CQType, ResearchQuestion
from kgbuilder.agents.validation_agent import ValidationAgent
from kgbuilder.core.models import Evidence, ExtractedEntity


def _make_entity(label: str, entity_type: str, confidence: float, source_id: str) -> ExtractedEntity:
    return ExtractedEntity(
        id=f"ent_{label}",
        label=label,
        entity_type=entity_type,
        description="",
        confidence=confidence,
        evidence=[Evidence(source_type="doc", source_id=source_id)],
    )


def test_module_extraction_agent_retrieves_and_extracts_per_question() -> None:
    retriever = MagicMock()
    retriever.retrieve.return_value = [{"content": "chunk text", "doc_id": "doc1"}]

    extractor = MagicMock()
    extractor.extract.return_value = [_make_entity("Reactor A", "Facility", 0.9, "doc1")]

    agent = ModuleExtractionAgent(
        module_name="Assets and Locations",
        ontology_classes=["Facility"],
        retriever=retriever,
        extractor=extractor,
    )

    question = ResearchQuestion(
        question_id="q1",
        text="Which facilities are mentioned?",
        entity_class="Facility",
        priority=1.0,
        reason="not covered",
        cq_type=CQType.SCQ,
    )

    entities = agent.run_questions([question])

    assert len(entities) == 1
    assert entities[0].label == "Reactor A"
    retriever.retrieve.assert_called_once_with(query="Which facilities are mentioned?", top_k=10)


def test_module_extraction_agent_skips_non_extraction_cq_types() -> None:
    retriever = MagicMock()
    extractor = MagicMock()

    agent = ModuleExtractionAgent(
        module_name="Assets and Locations",
        ontology_classes=["Facility"],
        retriever=retriever,
        extractor=extractor,
    )

    vcq = ResearchQuestion(
        question_id="q2",
        text="Does the KG contain a Facility named Reactor A?",
        entity_class="Facility",
        priority=1.0,
        reason="validation",
        cq_type=CQType.VCQ,
    )

    entities = agent.run_questions([vcq])

    assert entities == []
    retriever.retrieve.assert_not_called()


def test_orchestrator_dispatches_one_subagent_per_module_and_dedupes() -> None:
    retriever_a = MagicMock()
    retriever_a.retrieve.return_value = [{"content": "chunk A", "doc_id": "docA"}]
    extractor_a = MagicMock()
    extractor_a.extract.return_value = [_make_entity("Reactor A", "Facility", 0.7, "docA")]

    retriever_b = MagicMock()
    retriever_b.retrieve.return_value = [{"content": "chunk B", "doc_id": "docB"}]
    extractor_b = MagicMock()
    # Same real-world entity found independently by another module, higher confidence.
    extractor_b.extract.return_value = [_make_entity("Reactor A", "Facility", 0.95, "docB")]

    question_a = ResearchQuestion(
        question_id="qa", text="Which facilities exist?", entity_class="Facility",
        priority=1.0, reason="r", cq_type=CQType.SCQ,
    )
    question_b = ResearchQuestion(
        question_id="qb", text="Which facilities are referenced elsewhere?", entity_class="Facility",
        priority=1.0, reason="r", cq_type=CQType.SCQ,
    )

    bindings = [
        ModuleBinding(
            module_name="Assets and Locations",
            ontology_classes=["Facility"],
            retriever=retriever_a,
            extractor=extractor_a,
            questions=[question_a],
        ),
        ModuleBinding(
            module_name="Radiological Characterization",
            ontology_classes=["Facility"],
            retriever=retriever_b,
            extractor=extractor_b,
            questions=[question_b],
        ),
    ]

    orchestrator = OrchestratorAgent()
    merged = orchestrator.run_modules(bindings, parallel=False)

    assert len(merged) == 1
    assert merged[0].label == "Reactor A"
    assert merged[0].confidence == 0.95
    source_ids = {e.source_id for e in merged[0].evidence}
    assert source_ids == {"docA", "docB"}


def test_orchestrator_builds_module_bindings_from_class_module_map() -> None:
    retriever = MagicMock()
    extractor = MagicMock()
    questions = [
        ResearchQuestion(
            question_id="qa",
            text="Which facilities exist?",
            entity_class="Facility",
            priority=1.0,
            reason="r",
            cq_type=CQType.SCQ,
        ),
        ResearchQuestion(
            question_id="qb",
            text="What documents exist?",
            entity_class="Document",
            priority=1.0,
            reason="r",
            cq_type=CQType.RCQ,
        ),
    ]

    bindings = OrchestratorAgent.build_module_bindings(
        module_map={
            "Assets and Locations": ["Facility"],
            "Document Structure and Evidence": ["Document"],
        },
        questions=questions,
        retriever=retriever,
        extractor=extractor,
    )

    assert {binding.module_name for binding in bindings} == {
        "Assets and Locations",
        "Document Structure and Evidence",
    }
    assert [q.question_id for q in bindings[0].questions] in (["qa"], ["qb"]) or set(
        q.question_id for q in bindings[0].questions
    ) == {"qa"}
    assert all(binding.ontology_classes for binding in bindings)


def test_validation_agent_runs_only_vcq_questions() -> None:
    retriever = MagicMock()
    retriever.retrieve.return_value = [{"content": "evidence text", "doc_id": "doc-1"}]

    validator = MagicMock()
    validator.validate_question.return_value = {"valid": True, "question_id": "q-vcq"}

    agent = ValidationAgent(retriever=retriever, validator=validator)

    vcq = ResearchQuestion(
        question_id="q-vcq",
        text="Does the KG contain the facility Reactor A?",
        entity_class="Facility",
        priority=1.0,
        reason="validation",
        cq_type=CQType.VCQ,
    )
    scq = ResearchQuestion(
        question_id="q-scq",
        text="Which facilities exist?",
        entity_class="Facility",
        priority=1.0,
        reason="extraction",
        cq_type=CQType.SCQ,
    )

    results = agent.run_questions([vcq, scq])

    assert results == [{"valid": True, "question_id": "q-vcq"}]
    retriever.retrieve.assert_called_once_with(query="Does the KG contain the facility Reactor A?", top_k=10)
    validator.validate_question.assert_called_once()
