"""Consensus voting for dispute resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from kgbuilder.core.models import ExtractedEntity


class LLMProvider(Protocol):
    """Protocol for LLM providers."""

    def generate(self, prompt: str, max_tokens: int = 500) -> str:
        """Generate text from prompt."""
        ...


@dataclass
class VotingResult:
    """Result from consensus voting."""

    entity_id: str
    entity_label: str
    entity_type: str
    voted_confidence: float
    vote_agreement: float  # 0.0-1.0: how much voters agreed
    agreeing_votes: int
    total_votes: int
    reasoning: str  # Why we chose this confidence


class ConsensusVoter:
    """Resolve disputed entities via multi-LLM voting.

    For entities with high calibration uncertainty or ambiguous labels,
    query multiple LLMs to vote on the entity's correctness. Combine votes
    to update confidence with consensus agreement boost.

    Voting Strategy:
    1. Identify disputed entities (high uncertainty or type/label conflicts)
    2. Query multiple LLMs for entity assessment
    3. Each LLM votes: Accept/Reject/Uncertain
    4. Aggregate votes:
       - Accept rate = votes_accept / total_votes
       - Confidence boost = 0.05 * vote_agreement (if consensus)
    5. Update entity confidence based on agreement level

    Attributes:
        _llm: LLM provider for querying
        _num_voters: Number of LLM instances to query
    """

    CONFIDENCE_BOOST_FOR_CONSENSUS = 0.05
    DISPUTE_THRESHOLD = 0.75  # Confidence below this triggers voting

    def __init__(self, llm: LLMProvider | None = None, num_voters: int = 3) -> None:
        """Initialize voter.

        Args:
            llm: LLM provider for voting queries
            num_voters: Number of LLMs to query for consensus
        """
        self._llm = llm
        self._num_voters = num_voters

    def identify_disputes(
        self,
        entities: list[ExtractedEntity],
        dispute_threshold: float | None = None,
    ) -> list[ExtractedEntity]:
        """Identify entities that should be voted on.

        Args:
            entities: Entities to check
            dispute_threshold: Confidence below this triggers voting

        Returns:
            List of disputed entities
        """
        threshold = dispute_threshold or self.DISPUTE_THRESHOLD

        disputes = [e for e in entities if e.confidence < threshold]
        return disputes

    def vote_on_entity(
        self,
        entity: ExtractedEntity,
    ) -> VotingResult:
        """Get consensus vote on single entity.

        Args:
            entity: Entity to vote on

        Returns:
            Voting result with consensus confidence
        """
        if self._llm is None:
            # No LLM: return abstain
            return VotingResult(
                entity_id=entity.id,
                entity_label=entity.label,
                entity_type=entity.entity_type,
                voted_confidence=entity.confidence,
                vote_agreement=0.0,
                agreeing_votes=0,
                total_votes=0,
                reasoning="No LLM provided; confidence unchanged",
            )

        # Query LLM for entity assessment
        prompt = self._build_prompt(entity)

        # For simplicity: query single LLM and parse response
        # In production: multiple independent LLMs
        response = self._llm.generate(prompt, max_tokens=100)

        # Parse voting response
        accept_vote = self._parse_acceptance(response)
        vote_agreement = 1.0 if accept_vote else 0.0

        # Boost confidence if accepted
        if accept_vote:
            boosted_confidence = min(
                entity.confidence + self.CONFIDENCE_BOOST_FOR_CONSENSUS,
                0.99,
            )
        else:
            # Reduce confidence if rejected
            boosted_confidence = max(entity.confidence - 0.1, 0.1)

        return VotingResult(
            entity_id=entity.id,
            entity_label=entity.label,
            entity_type=entity.entity_type,
            voted_confidence=boosted_confidence,
            vote_agreement=vote_agreement,
            agreeing_votes=1 if accept_vote else 0,
            total_votes=1,
            reasoning=f"LLM voting: {'ACCEPT' if accept_vote else 'REJECT'}",
        )

    def vote_batch(
        self,
        entities: list[ExtractedEntity],
        dispute_threshold: float | None = None,
    ) -> list[VotingResult]:
        """Vote on multiple entities.

        Args:
            entities: Entities to vote on
            dispute_threshold: Only vote on entities below this confidence

        Returns:
            List of voting results
        """
        # Identify disputed entities
        disputes = self.identify_disputes(entities, dispute_threshold)

        # Vote on each
        results = []
        for entity in entities:
            if entity in disputes:
                result = self.vote_on_entity(entity)
            else:
                # No dispute: return abstain
                result = VotingResult(
                    entity_id=entity.id,
                    entity_label=entity.label,
                    entity_type=entity.entity_type,
                    voted_confidence=entity.confidence,
                    vote_agreement=0.0,
                    agreeing_votes=0,
                    total_votes=0,
                    reasoning="No dispute; confidence unchanged",
                )
            results.append(result)

        return results

    def apply_votes(
        self,
        entities: list[ExtractedEntity],
        voting_results: list[VotingResult],
    ) -> list[ExtractedEntity]:
        """Apply voting results to entities.

        Args:
            entities: Original entities
            voting_results: Voting results

        Returns:
            Entities with updated confidence from voting
        """
        from dataclasses import replace

        voted_entities = []
        for entity, result in zip(entities, voting_results):
            # Update confidence from voting
            updated = replace(entity, confidence=result.voted_confidence)
            voted_entities.append(updated)

        return voted_entities

    def _build_prompt(self, entity: ExtractedEntity) -> str:
        """Build LLM prompt for entity assessment.

        Args:
            entity: Entity to assess

        Returns:
            Prompt for LLM
        """
        return f"""Assess the following entity:

Label: {entity.label}
Type: {entity.entity_type}
Description: {entity.description}
Evidence count: {len(entity.evidence)}

Is this a valid entity in the context of nuclear decommissioning planning?
Answer with ACCEPT or REJECT and brief reason."""

    def _parse_acceptance(self, response: str) -> bool:
        """Parse LLM response to determine acceptance.

        Args:
            response: LLM response text

        Returns:
            True if accepted, False if rejected
        """
        response_upper = response.upper()

        if "ACCEPT" in response_upper or "VALID" in response_upper:
            return True
        elif "REJECT" in response_upper or "INVALID" in response_upper:
            return False
        else:
            # Default to accepting if ambiguous
            return True
