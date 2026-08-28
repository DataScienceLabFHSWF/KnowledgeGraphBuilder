"""Tests for tool/skill facades wrapping enrichment, retrieval, evaluation, and linking."""

from __future__ import annotations

from unittest.mock import MagicMock

from kgbuilder.agents.pipeline_agent import PipelineAgent, PipelineStep
from kgbuilder.agents.registry import SKILL_REGISTRY, TOOL_REGISTRY, get_skill, get_tool
from kgbuilder.tools.enrichment_tool import EnrichmentTool
from kgbuilder.tools.evaluation_tool import EvaluationTool
from kgbuilder.tools.law_linking_tool import LawContextTool, LawLinkingTool
from kgbuilder.tools.retrieval_tool import RetrievalTool


def test_registry_contains_expected_skills_and_tools() -> None:
    for name in [
        "ontology_gap_analysis",
        "follow_up_gap_analysis",
        "semantic_enrichment",
        "document_retrieval",
        "retrieval_evaluation",
        "law_linking",
        "law_context_lookup",
    ]:
        assert name in SKILL_REGISTRY

    for name in [
        "ontology_query",
        "coverage_snapshot",
        "semantic_enrichment",
        "document_retrieval",
        "retrieval_evaluation",
        "law_linking",
        "law_context_lookup",
    ]:
        assert name in TOOL_REGISTRY


def test_get_skill_and_get_tool_raise_for_unknown_name() -> None:
    import pytest

    with pytest.raises(ValueError, match="Unknown skill"):
        get_skill("does_not_exist")
    with pytest.raises(ValueError, match="Unknown tool"):
        get_tool("does_not_exist")


def test_enrichment_tool_delegates_to_pipeline() -> None:
    pipeline = MagicMock()
    pipeline.enrich.return_value = ("entities", "relations", "metrics")

    result = EnrichmentTool.execute(pipeline=pipeline, entities=["e1"], relations=["r1"])

    pipeline.enrich.assert_called_once_with(entities=["e1"], relations=["r1"])
    assert result == ("entities", "relations", "metrics")


def test_retrieval_tool_delegates_to_retriever() -> None:
    retriever = MagicMock()
    retriever.retrieve.return_value = ["doc1", "doc2"]

    result = RetrievalTool.execute(retriever=retriever, query="what is X?", top_k=5)

    retriever.retrieve.assert_called_once_with(query="what is X?", top_k=5)
    assert result == ["doc1", "doc2"]


def test_evaluation_tool_computes_metrics() -> None:
    result = EvaluationTool.execute(
        retrieved_ids=["a", "b", "c"],
        relevant_ids=["b", "c"],
    )
    assert result.recall_at_5 == 1.0


def test_law_linking_tool_delegates_to_linker() -> None:
    linker = MagicMock()
    linker.create_links.return_value = {"created": 3}

    result = LawLinkingTool.execute(linker=linker, dry_run=True)

    linker.create_links.assert_called_once_with(dry_run=True)
    assert result == {"created": 3}


def test_law_context_tool_delegates_to_provider() -> None:
    provider = MagicMock()
    provider.get_context.return_value = "context text"

    result = LawContextTool.execute(provider=provider, text="chunk text")

    provider.get_context.assert_called_once_with("chunk text")
    assert result == "context text"


def test_pipeline_agent_runs_declarative_plan_with_bindings() -> None:
    retriever = MagicMock()
    retriever.retrieve.return_value = ["doc1"]

    agent = PipelineAgent(bindings={"retriever": retriever})
    results = agent.run_plan(
        [
            PipelineStep(
                skill="document_retrieval",
                kwargs={"query": "what is X?"},
                bind={"retriever": "retriever"},
            )
        ]
    )

    assert results == [["doc1"]]
    retriever.retrieve.assert_called_once_with(query="what is X?", top_k=10)


def test_pipeline_agent_missing_binding_raises() -> None:
    import pytest

    agent = PipelineAgent(bindings={})
    with pytest.raises(ValueError, match="Missing binding"):
        agent.run_plan(
            [
                PipelineStep(
                    skill="document_retrieval",
                    kwargs={"query": "x"},
                    bind={"retriever": "retriever"},
                )
            ]
        )
