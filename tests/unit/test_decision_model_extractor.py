from __future__ import annotations

from typing import Any

import pytest

from kgbuilder.core.exceptions import LLMError
from kgbuilder.core.models import ExtractedEntity
from kgbuilder.extraction.decision_model import (
    DecisionJudgedRelationExtractor,
    DecisionModelRelationExtractor,
    OllamaDecisionClient,
)
from kgbuilder.extraction.relation import OntologyRelationDef


class FakeDecisionClient:
    def __init__(self, positive: set[str]) -> None:
        self.positive = positive
        self.calls: list[dict[str, Any]] = []

    def decide(
        self,
        state: dict[str, Any],
        questions: dict[str, dict[str, Any]],
    ) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
        self.calls.append({"state": state, "questions": questions})
        answers = {name: {"noul": 0.95 if name in self.positive else 0.02} for name in questions}
        return answers, {
            "prompt_tokens": len(questions) * 3,
            "completion_tokens": len(questions),
            "total_tokens": len(questions) * 4,
            "source": "server",
        }


def make_entity(entity_id: str, label: str, entity_type: str) -> ExtractedEntity:
    return ExtractedEntity(
        id=entity_id,
        label=label,
        entity_type=entity_type,
        description="",
        confidence=0.9,
    )


def test_decision_relation_extractor_generates_domain_range_constrained_triples() -> None:
    client = FakeDecisionClient({"triple_00000"})
    extractor = DecisionModelRelationExtractor(client)
    entities = [
        make_entity("p1", "Ada Lovelace", "http://example.org/Person"),
        make_entity("o1", "Analytical Engines Ltd.", "Organization"),
    ]
    relation = OntologyRelationDef(
        uri="http://example.org/works-for",
        label="works for",
        domain=["Person"],
        range=["http://example.org/Organization"],
    )

    result = extractor.extract(
        "Ada Lovelace works for Analytical Engines Ltd.",
        entities,
        [relation],
    )

    assert len(result) == 1
    assert result[0].source_entity_id == "p1"
    assert result[0].target_entity_id == "o1"
    assert result[0].predicate == relation.uri
    assert result[0].confidence == pytest.approx(0.95)
    assert extractor.last_candidate_count == 1
    assert extractor.last_scored_count == 1
    assert client.calls[0]["questions"]["triple_00000"]["type"] == "noul"


def test_decision_extractor_batches_at_endpoint_limit() -> None:
    relation_defs = [
        OntologyRelationDef(uri=f"rel-{index}", label=f"relation {index}") for index in range(65)
    ]
    client = FakeDecisionClient({"triple_00064", "triple_00065"})
    extractor = DecisionModelRelationExtractor(client)

    result = extractor.extract(
        "Ada works for the company.",
        [make_entity("a", "Ada", "Person"), make_entity("b", "Company", "Organization")],
        relation_defs,
    )

    assert [len(call["questions"]) for call in client.calls] == [64, 64, 2]
    assert extractor.last_candidate_count == 130
    assert extractor.last_scored_count == 130
    assert len(result) == 2


def test_decision_extractor_rejects_oversized_candidate_set() -> None:
    extractor = DecisionModelRelationExtractor(FakeDecisionClient(set()), max_candidates=1)
    entities = [
        make_entity("a", "A", "Class"),
        make_entity("b", "B", "Class"),
        make_entity("c", "C", "Class"),
    ]

    with pytest.raises(ValueError, match="exceeding configured max_candidates"):
        extractor.extract("A relates to B and C.", entities, [OntologyRelationDef("r", "rel")])


def test_decision_extractor_surfaces_missing_model_answers() -> None:
    class MissingAnswerClient:
        def decide(self, state: dict[str, Any], questions: dict[str, Any]):
            return {}, {}

    extractor = DecisionModelRelationExtractor(MissingAnswerClient())

    with pytest.raises(LLMError, match="omitted answer"):
        extractor.extract(
            "Ada works for Acme.",
            [make_entity("a", "Ada", "Person"), make_entity("b", "Acme", "Organization")],
            [OntologyRelationDef("r", "works-for")],
        )


def test_ollama_decision_client_calls_systemone_and_records_tokens() -> None:
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {
                "answers": {"triple": {"noul": 0.8}},
                "usage": {"input_tokens": 90, "output_tokens": 2},
            }

    class Session:
        def post(self, url: str, **kwargs: Any) -> Response:
            assert url == "http://ollama:11434/v1/systemone"
            assert kwargs["json"]["model"] == "tev1:0.8b"
            return Response()

    client = OllamaDecisionClient(
        model="tev1:0.8b",
        base_url="http://ollama:11434/",
        session=Session(),  # type: ignore[arg-type]
    )

    answers, usage = client.decide({"text": "passage"}, {"triple": {"type": "noul"}})

    assert answers["triple"]["noul"] == 0.8
    assert usage["total_tokens"] == 92
    assert client.usage_history == [usage]


def test_decision_judge_preserves_proposal_evidence_and_filters_rejections() -> None:
    entities = [make_entity("a", "Ada", "Person"), make_entity("b", "Acme", "Organization")]
    definitions = [
        OntologyRelationDef("urn:kg:works_for", "works for", domain=["urn:kg:Person"]),
        OntologyRelationDef("urn:kg:owns", "owns"),
    ]
    proposer = DecisionModelRelationExtractor(FakeDecisionClient({"triple_00000", "triple_00002"}))
    proposals = proposer.extract("Ada works for Acme.", entities, definitions)
    judge = DecisionModelRelationExtractor(FakeDecisionClient({"triple_00000"}))
    accepted = judge.judge("Ada works for Acme.", entities, definitions, proposals)

    assert len(accepted) == 1
    assert accepted[0].id == proposals[0].id
    assert accepted[0].evidence == proposals[0].evidence
    assert judge.last_candidate_count == len(proposals)
    assert judge.last_candidate_triples[0] == ("Ada", "urn:kg:works_for", "Acme")


def test_decision_judge_rejects_unknown_endpoints() -> None:
    from kgbuilder.core.models import ExtractedRelation

    judge = DecisionModelRelationExtractor(FakeDecisionClient(set()))
    proposal = ExtractedRelation(
        id="r", source_entity_id="missing", target_entity_id="b", predicate="r", confidence=0.9
    )
    with pytest.raises(ValueError, match="ontology-invalid"):
        judge.judge("text", [], [OntologyRelationDef("r", "relation")], [proposal])


def test_decision_judge_empty_proposals_clear_candidate_state_without_calls() -> None:
    client = FakeDecisionClient(set())
    judge = DecisionModelRelationExtractor(client)
    wrapper = DecisionJudgedRelationExtractor(judge, judge)
    assert wrapper.extract("text", [], []) == []
    assert wrapper.last_candidate_triples == []
    assert wrapper.usage_history == []
    assert client.calls == []


@pytest.mark.parametrize("probability", [True, float("nan"), -0.1, 1.1])
def test_decision_extractor_rejects_invalid_probabilities(probability: float) -> None:
    class InvalidProbabilityClient(FakeDecisionClient):
        def decide(
            self, state: dict[str, Any], questions: dict[str, dict[str, Any]]
        ) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
            return {name: {"noul": probability} for name in questions}, {}

    extractor = DecisionModelRelationExtractor(InvalidProbabilityClient(set()))
    with pytest.raises(LLMError, match="invalid 'noul'"):
        extractor.extract(
            "A relates to B.",
            [make_entity("a", "A", "Class"), make_entity("b", "B", "Class")],
            [OntologyRelationDef("r", "relation")],
        )
