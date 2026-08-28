"""Tests for the markdown-driven skill/pipeline loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from kgbuilder.agents.markdown_pipeline import (
    MarkdownPipelineError,
    load_pipeline,
    load_skill_doc,
    load_skill_docs,
)
from kgbuilder.agents.pipeline_agent import PipelineAgent

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTIC_PIPELINE_DIR = REPO_ROOT / "agentic_pipeline"


def test_repo_skill_docs_parse_and_match_registry() -> None:
    docs = load_skill_docs(AGENTIC_PIPELINE_DIR / "skills")
    assert "ontology_gap_analysis" in docs
    assert "document_retrieval" in docs
    doc = docs["document_retrieval"]
    assert doc.requires_binding == ["retriever"]
    assert doc.default_kwargs == {"top_k": 10}
    assert "Retrieve the top-k documents" in doc.description


def test_repo_pipeline_md_parses_into_steps() -> None:
    steps = load_pipeline(AGENTIC_PIPELINE_DIR / "pipeline.md")
    step_names = [step.skill for step in steps]
    assert step_names == [
        "ontology_gap_analysis",
        "document_retrieval",
        "law_context_lookup",
        "semantic_enrichment",
        "law_linking",
        "retrieval_evaluation",
    ]

    retrieval_step = next(step for step in steps if step.skill == "document_retrieval")
    assert retrieval_step.bind == {"retriever": "retriever"}
    assert retrieval_step.kwargs == {"top_k": 10}


def test_pipeline_agent_can_execute_repo_pipeline_plan() -> None:
    """The markdown-defined plan should be directly runnable by PipelineAgent."""
    from unittest.mock import MagicMock

    steps = load_pipeline(AGENTIC_PIPELINE_DIR / "pipeline.md")
    question_agent = MagicMock()
    question_agent.generate_questions.return_value = []

    agent = PipelineAgent(bindings={"question_generation_agent": question_agent})
    first_step = next(step for step in steps if step.skill == "ontology_gap_analysis")

    result = agent.run_plan([first_step])

    assert result == [[]]
    question_agent.generate_questions.assert_called_once_with(max_questions=20, covered_threshold=1)


def test_load_skill_doc_missing_front_matter_raises(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.md"
    bad_file.write_text("# No front matter here\n")

    with pytest.raises(MarkdownPipelineError, match="missing YAML front matter"):
        load_skill_doc(bad_file)


def test_load_skill_doc_unterminated_front_matter_raises(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.md"
    bad_file.write_text("---\nname: foo\n")

    with pytest.raises(MarkdownPipelineError, match="unterminated YAML front matter"):
        load_skill_doc(bad_file)


def test_load_skill_doc_unknown_skill_raises(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.md"
    bad_file.write_text("---\nname: does_not_exist\n---\nBody text\n")

    with pytest.raises(MarkdownPipelineError, match="is not registered"):
        load_skill_doc(bad_file)


def test_load_pipeline_missing_steps_raises(tmp_path: Path) -> None:
    bad_file = tmp_path / "pipeline.md"
    bad_file.write_text("---\nfoo: bar\n---\nBody\n")

    with pytest.raises(MarkdownPipelineError, match="non-empty 'steps' list"):
        load_pipeline(bad_file)


def test_load_pipeline_unknown_skill_reference_raises(tmp_path: Path) -> None:
    bad_file = tmp_path / "pipeline.md"
    bad_file.write_text("---\nsteps:\n  - skill: does_not_exist\n---\nBody\n")

    with pytest.raises(MarkdownPipelineError, match="unknown skill"):
        load_pipeline(bad_file)


def test_load_pipeline_step_without_skill_key_raises(tmp_path: Path) -> None:
    bad_file = tmp_path / "pipeline.md"
    bad_file.write_text("---\nsteps:\n  - kwargs: {}\n---\nBody\n")

    with pytest.raises(MarkdownPipelineError, match="must be a mapping with a 'skill' key"):
        load_pipeline(bad_file)
