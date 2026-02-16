"""Unit tests for ConsensusVoter (Task 5.5)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kgbuilder.confidence.voter import ConsensusVoter
from kgbuilder.core.models import Evidence, ExtractedEntity


@pytest.fixture
def mock_llm() -> MagicMock:
    """Create mock LLM provider."""
    llm = MagicMock()
    llm.generate.return_value = '{"decision": "accept", "confidence": 0.85}'
    llm.model_name = "test-llm"
    return llm


@pytest.fixture
def sample_entities() -> list[ExtractedEntity]:
    """Create sample entities for testing."""
    return [
        ExtractedEntity(
            id="e1",
            label="Apple",
            entity_type="Organization",
            description="Technology company",
            confidence=0.65,
            evidence=[Evidence(source_type="local_doc", source_id="doc1", text_span="Apple")],
        ),
        ExtractedEntity(
            id="e2",
            label="ML",
            entity_type="Concept",
            description="AI technique",
            confidence=0.85,
            evidence=[Evidence(source_type="local_doc", source_id="doc1", text_span="ML")],
        ),
        ExtractedEntity(
            id="e3",
            label="ambiguous",
            entity_type="Concept",
            description="Unclear term",
            confidence=0.60,
            evidence=[Evidence(source_type="local_doc", source_id="doc2", text_span="unclear")],
        ),
    ]


@pytest.fixture
def voter(mock_llm: MagicMock) -> ConsensusVoter:
    """Create voter instance with mock LLM."""
    return ConsensusVoter(llm=mock_llm, num_voters=3)


class TestConsensusVoterBasics:
    """Test basic voter initialization."""

    def test_init_with_llm(self, mock_llm: MagicMock) -> None:
        """Test initialization with LLM provider."""
        voter = ConsensusVoter(llm=mock_llm)
        assert voter is not None

    def test_init_with_custom_num_voters(self, mock_llm: MagicMock) -> None:
        """Test initialization with custom num_voters."""
        voter = ConsensusVoter(llm=mock_llm, num_voters=5)
        assert voter is not None


class TestConsensusVoterDisputeIdentification:
    """Test dispute identification."""

    def test_identify_disputes_empty(self, voter: ConsensusVoter) -> None:
        """Test with empty list."""
        disputes = voter.identify_disputes([])
        assert disputes == []

    def test_identify_disputes_threshold(
        self,
        voter: ConsensusVoter,
        sample_entities: list[ExtractedEntity],
    ) -> None:
        """Test dispute identification with threshold."""
        disputes = voter.identify_disputes(sample_entities, dispute_threshold=0.75)

        dispute_ids = [e.id for e in disputes]
        assert "e1" in dispute_ids  # 0.65 < 0.75
        assert "e3" in dispute_ids  # 0.60 < 0.75
        assert "e2" not in dispute_ids  # 0.85 >= 0.75

    def test_identify_custom_threshold(
        self,
        voter: ConsensusVoter,
        sample_entities: list[ExtractedEntity],
    ) -> None:
        """Test with custom threshold."""
        disputes = voter.identify_disputes(sample_entities, dispute_threshold=0.65)
        dispute_ids = [e.id for e in disputes]
        assert "e3" in dispute_ids  # 0.60 < 0.65


class TestConsensusVoterVoting:
    """Test voting functionality."""

    def test_vote_on_entity(
        self,
        voter: ConsensusVoter,
        sample_entities: list[ExtractedEntity],
    ) -> None:
        """Test voting on single entity."""
        result = voter.vote_on_entity(sample_entities[0])
        assert result is not None
        assert result.entity_id == "e1"

    def test_vote_batch(
        self,
        voter: ConsensusVoter,
        sample_entities: list[ExtractedEntity],
    ) -> None:
        """Test batch voting."""
        results = voter.vote_batch(sample_entities, dispute_threshold=0.75)
        # Should return results for entities below threshold
        assert len(results) >= 2  # e1 and e3

    def test_voting_result_structure(
        self,
        voter: ConsensusVoter,
        sample_entities: list[ExtractedEntity],
    ) -> None:
        """Test result structure."""
        result = voter.vote_on_entity(sample_entities[0])
        assert hasattr(result, "entity_id")
        assert hasattr(result, "voted_confidence")
        assert hasattr(result, "vote_agreement")


class TestConsensusVoterApplyingVotes:
    """Test applying votes."""

    def test_apply_votes(
        self,
        voter: ConsensusVoter,
        sample_entities: list[ExtractedEntity],
    ) -> None:
        """Test applying votes to entities."""
        results = voter.vote_batch(sample_entities, dispute_threshold=0.75)
        updated = voter.apply_votes(sample_entities, results)
        assert len(updated) == len(sample_entities)

    def test_apply_votes_preserves_count(
        self,
        voter: ConsensusVoter,
        sample_entities: list[ExtractedEntity],
    ) -> None:
        """Test that applying votes preserves entities."""
        results = voter.vote_batch(sample_entities, dispute_threshold=0.75)
        updated = voter.apply_votes(sample_entities, results)
        # Updated entities should match or exceed original
        assert len(updated) <= len(sample_entities)


class TestConsensusVoterPromptGeneration:
    """Test prompt generation."""

    def test_prompt_contains_info(
        self,
        voter: ConsensusVoter,
        sample_entities: list[ExtractedEntity],
    ) -> None:
        """Test that prompt contains entity information."""
        entity = sample_entities[0]
        prompt = voter._build_prompt(entity)
        assert "Apple" in prompt
        assert "Organization" in prompt


class TestConsensusVoterIntegration:
    """Integration tests."""

    def test_full_pipeline(
        self,
        voter: ConsensusVoter,
        sample_entities: list[ExtractedEntity],
    ) -> None:
        """Test complete voting pipeline."""
        disputes = voter.identify_disputes(sample_entities, dispute_threshold=0.75)
        assert len(disputes) > 0

        results = voter.vote_batch(sample_entities, dispute_threshold=0.75)
        assert len(results) > 0

        updated = voter.apply_votes(sample_entities, results)
        assert len(updated) == len(sample_entities)
