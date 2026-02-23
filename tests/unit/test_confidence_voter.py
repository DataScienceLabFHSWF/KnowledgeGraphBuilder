"""Unit tests for ConsensusVoter behaviour."""

from __future__ import annotations

from dataclasses import replace

from kgbuilder.confidence.voter import ConsensusVoter, VotingResult
from kgbuilder.core.models import ExtractedEntity, Evidence


class DummyLLM:
    def __init__(self, response: str):
        self.response = response

    def generate(self, prompt: str, max_tokens: int = 500) -> str:
        # ignore prompt and return stored answer
        return self.response


def make_entity(eid: str, conf: float) -> ExtractedEntity:
    return ExtractedEntity(
        id=eid,
        label="lbl",
        entity_type="Type",
        description="",
        confidence=conf,
        evidence=[Evidence(source_type="doc", source_id="1")],
    )


def test_identify_disputes():
    v = ConsensusVoter()
    ents = [make_entity("e1", 0.5), make_entity("e2", 0.8)]
    disputes = v.identify_disputes(ents)
    assert len(disputes) == 1
    # custom threshold
    disputes2 = v.identify_disputes(ents, dispute_threshold=0.9)
    assert len(disputes2) == 2


def test_vote_without_llm_returns_abstain():
    v = ConsensusVoter(llm=None)
    ent = make_entity("e", 0.3)
    res = v.vote_on_entity(ent)
    assert res.vote_agreement == 0.0
    assert res.total_votes == 0
    assert "confidence unchanged" in res.reasoning.lower()


def test_vote_with_llm_accept_and_reject():
    # accept case
    v1 = ConsensusVoter(llm=DummyLLM("ACCEPT this entity"))
    ent = make_entity("x", 0.4)
    r1 = v1.vote_on_entity(ent)
    assert r1.vote_agreement == 1.0
    assert r1.voted_confidence > ent.confidence
    # reject case
    v2 = ConsensusVoter(llm=DummyLLM("REJECT because no evidence"))
    r2 = v2.vote_on_entity(ent)
    assert r2.vote_agreement == 0.0
    assert r2.voted_confidence < ent.confidence


def test_vote_batch_and_apply():
    llm = DummyLLM("ACCEPT yes")
    v = ConsensusVoter(llm=llm)
    ents = [make_entity("a", 0.2), make_entity("b", 0.95)]
    results = v.vote_batch(ents, dispute_threshold=0.9)
    assert len(results) == 2
    # first entity disputed -> boost
    assert results[0].voted_confidence > ents[0].confidence
    # second not disputed -> no votes
    assert results[1].total_votes == 0

    updated = v.apply_votes(ents, results)
    assert updated[0].confidence == results[0].voted_confidence
    assert updated[1].confidence == ents[1].confidence


def test_prompt_and_parse_logic():
    v = ConsensusVoter()
    ent = make_entity("z", 0.1)
    prompt = v._build_prompt(ent)
    assert "Assess the following entity" in prompt
    # parse acceptance
    assert v._parse_acceptance("ACCEPT definitely")
    assert not v._parse_acceptance("I think reject")
    assert v._parse_acceptance("whatever")  # ambiguous defaults to True
