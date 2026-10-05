"""Experimental decision-model scoring for ontology-constrained triples."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Protocol

import requests  # type: ignore[import-untyped]
import structlog

from kgbuilder.core.exceptions import LLMError
from kgbuilder.core.models import Evidence, ExtractedEntity, ExtractedRelation
from kgbuilder.extraction.relation import OntologyRelationDef

logger = structlog.get_logger(__name__)


class TripleDecisionClient(Protocol):
    """Client protocol for scoring a batch of candidate triple questions."""

    def decide(
        self,
        state: dict[str, Any],
        questions: dict[str, dict[str, Any]],
    ) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
        """Return named decision answers and provider token usage."""
        ...


class OllamaDecisionClient:
    """Call Ollama's TypeSafe-compatible `/v1/systemone` decision endpoint."""

    def __init__(
        self,
        model: str,
        base_url: str,
        timeout: int = 120,
        session: requests.Session | None = None,
    ) -> None:
        if not model.strip():
            raise ValueError("Decision model name must not be empty")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = session or requests.Session()
        self.usage_history: list[dict[str, Any]] = []

    def decide(
        self,
        state: dict[str, Any],
        questions: dict[str, dict[str, Any]],
    ) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
        """Score one to 64 named yes/no questions in a single request."""
        if not 1 <= len(questions) <= 64:
            raise ValueError("Ollama decision requests require between 1 and 64 questions")

        try:
            response = self._session.post(
                f"{self.base_url}/v1/systemone",
                json={
                    "model": self.model,
                    "state": state,
                    "questions": questions,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
            answers = result["answers"]
            if not isinstance(answers, dict):
                raise TypeError("Decision response 'answers' must be an object")
            usage = result.get("usage", {})
            usage_record = {
                "prompt_tokens": usage.get("input_tokens"),
                "completion_tokens": usage.get("output_tokens"),
                "total_tokens": (
                    usage.get("input_tokens", 0) + usage.get("output_tokens", 0) if usage else None
                ),
                "source": "server" if usage else "unavailable",
            }
            self.usage_history.append(usage_record)
            return answers, usage_record
        except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
            raise LLMError(f"Ollama decision request failed: {exc}") from exc


@dataclass(frozen=True)
class _TripleCandidate:
    """A directed entity pair constrained by one ontology relation."""

    subject: ExtractedEntity
    relation: OntologyRelationDef
    object: ExtractedEntity


class DecisionModelRelationExtractor:
    """Score bounded subject-predicate-object candidates with a decision model.

    This does not generate entity spans or relation candidates. It enumerates
    ontology-valid directed triples over the supplied entities and uses the
    decision model to select candidates supported by the source text.
    """

    def __init__(
        self,
        client: TripleDecisionClient,
        confidence_threshold: float = 0.5,
        max_candidates: int = 1024,
        questions_per_request: int = 64,
    ) -> None:
        if not 0 <= confidence_threshold <= 1:
            raise ValueError("confidence_threshold must be between zero and one")
        if max_candidates < 1:
            raise ValueError("max_candidates must be at least one")
        if not 1 <= questions_per_request <= 64:
            raise ValueError("questions_per_request must be between one and 64")
        self.client = client
        self.confidence_threshold = confidence_threshold
        self.max_candidates = max_candidates
        self.questions_per_request = questions_per_request
        self.last_candidate_count = 0
        self.last_scored_count = 0
        self.last_candidate_triples: list[tuple[str, str, str]] = []
        self.usage_history: list[dict[str, Any]] = []

    def extract(
        self,
        text: str,
        entities: list[ExtractedEntity],
        ontology_relations: list[OntologyRelationDef],
    ) -> list[ExtractedRelation]:
        """Return ontology-valid candidate triples supported by the text."""
        candidates = self._make_candidates(entities, ontology_relations)
        return self._score(text, entities, candidates)

    def judge(
        self,
        text: str,
        entities: list[ExtractedEntity],
        ontology_relations: list[OntologyRelationDef],
        proposals: list[ExtractedRelation],
    ) -> list[ExtractedRelation]:
        """Filter proposed triples by source support, preserving their evidence.

        Unknown endpoints and ontology-invalid proposals raise an error. Scores
        are model support probabilities, not calibrated accuracy estimates.
        """
        valid = {
            (candidate.subject.id, candidate.relation.uri, candidate.object.id): candidate
            for candidate in self._make_candidates(entities, ontology_relations)
        }
        candidates = []
        for proposal in proposals:
            key = (proposal.source_entity_id, proposal.predicate, proposal.target_entity_id)
            if key not in valid:
                raise ValueError(f"Cannot judge ontology-invalid triple: {key}")
            candidates.append(valid[key])
        scored = self._score(text, entities, candidates)
        probabilities = {
            (
                relation.source_entity_id,
                relation.predicate,
                relation.target_entity_id,
            ): relation.confidence
            for relation in scored
        }
        from dataclasses import replace

        return [
            replace(proposal, confidence=probabilities[key])
            for proposal in proposals
            if (key := (proposal.source_entity_id, proposal.predicate, proposal.target_entity_id))
            in probabilities
        ]

    def _score(
        self,
        text: str,
        entities: list[ExtractedEntity],
        candidates: list[_TripleCandidate],
    ) -> list[ExtractedRelation]:
        self.last_candidate_count = len(candidates)
        self.last_scored_count = 0
        self.last_candidate_triples = [
            (candidate.subject.label, candidate.relation.uri, candidate.object.label)
            for candidate in candidates
        ]
        if not candidates:
            return []
        if len(candidates) > self.max_candidates:
            raise ValueError(
                f"Candidate set has {len(candidates)} triples, exceeding configured "
                f"max_candidates={self.max_candidates}; narrow the ontology/entities "
                "or raise the explicit limit."
            )

        state = {
            "text": text,
            "entities": [
                {"id": entity.id, "text": entity.label, "type": entity.entity_type}
                for entity in entities
            ],
        }
        accepted: list[ExtractedRelation] = []
        for start in range(0, len(candidates), self.questions_per_request):
            batch = candidates[start : start + self.questions_per_request]
            questions = {
                f"triple_{start + index:05d}": {
                    "type": "noul",
                    "instructions": self._question(candidate),
                }
                for index, candidate in enumerate(batch)
            }
            answers, usage = self.client.decide(state=state, questions=questions)
            self.usage_history.append(usage)
            self.last_scored_count += len(batch)
            for index, candidate in enumerate(batch):
                answer_key = f"triple_{start + index:05d}"
                if answer_key not in answers:
                    raise LLMError(f"Decision response omitted answer '{answer_key}'")
                probability = answers[answer_key].get("noul")
                if (
                    isinstance(probability, bool)
                    or not isinstance(probability, (int, float))
                    or not isfinite(probability)
                    or not 0 <= probability <= 1
                ):
                    raise LLMError(
                        f"Decision response for '{answer_key}' has invalid 'noul' probability"
                    )
                if probability < self.confidence_threshold:
                    continue
                accepted.append(
                    self._to_relation(candidate, text, float(probability), start + index)
                )
        return accepted

    def _make_candidates(
        self,
        entities: list[ExtractedEntity],
        ontology_relations: list[OntologyRelationDef],
    ) -> list[_TripleCandidate]:
        candidates: list[_TripleCandidate] = []
        for relation in ontology_relations:
            for subject in entities:
                if relation.domain and not self._matches_class(
                    subject.entity_type, relation.domain
                ):
                    continue
                for target in entities:
                    if subject.id == target.id:
                        continue
                    if relation.range and not self._matches_class(
                        target.entity_type, relation.range
                    ):
                        continue
                    candidates.append(_TripleCandidate(subject, relation, target))
        return candidates

    @staticmethod
    def _matches_class(entity_type: str, class_names: list[str]) -> bool:
        normalized_type = DecisionModelRelationExtractor._local_name(entity_type).casefold()
        return any(
            normalized_type == DecisionModelRelationExtractor._local_name(class_name).casefold()
            for class_name in class_names
        )

    @staticmethod
    def _local_name(value: str) -> str:
        if value.casefold().startswith("urn:"):
            return value.rsplit(":", maxsplit=1)[-1]
        return value.rstrip("/#").rsplit("/", maxsplit=1)[-1].rsplit("#", maxsplit=1)[-1]

    @staticmethod
    def _question(candidate: _TripleCandidate) -> str:
        relation_name = candidate.relation.label or candidate.relation.uri
        return (
            f"Does the source text explicitly support the directed triple "
            f"'{candidate.subject.label}' ({candidate.subject.entity_type}) "
            f"--[{relation_name}]--> '{candidate.object.label}' "
            f"({candidate.object.entity_type})? Answer true only when this "
            "relationship and direction are supported by the text."
        )

    @staticmethod
    def _to_relation(
        candidate: _TripleCandidate,
        text: str,
        confidence: float,
        candidate_index: int,
    ) -> ExtractedRelation:
        from kgbuilder.core.models import generate_relation_id

        return ExtractedRelation(
            id=generate_relation_id(
                candidate.subject.id,
                candidate.object.id,
                candidate.relation.uri,
            ),
            source_entity_id=candidate.subject.id,
            target_entity_id=candidate.object.id,
            predicate=candidate.relation.uri,
            confidence=confidence,
            evidence=[
                Evidence(
                    source_type="decision_model",
                    source_id=f"candidate_{candidate_index}",
                    text_span=text,
                    confidence=confidence,
                )
            ],
        )


class RelationProposalExtractor(Protocol):
    """Capability needed to produce relations for evidence judging."""

    def extract(
        self,
        text: str,
        entities: list[ExtractedEntity],
        ontology_relations: list[OntologyRelationDef],
    ) -> list[ExtractedRelation]: ...


class DecisionJudgedRelationExtractor:
    """Apply TEV source-support judging after another relation extractor."""

    def __init__(
        self,
        extractor: RelationProposalExtractor,
        judge: DecisionModelRelationExtractor,
    ) -> None:
        self.extractor = extractor
        self.judge = judge
        self.usage_history = judge.usage_history

    @property
    def last_candidate_triples(self) -> list[tuple[str, str, str]]:
        """Return the proposals presented to the judge."""
        return self.judge.last_candidate_triples

    def extract(
        self,
        text: str,
        entities: list[ExtractedEntity],
        ontology_relations: list[OntologyRelationDef],
    ) -> list[ExtractedRelation]:
        """Generate proposals, then keep only those supported by TEV."""
        proposals = self.extractor.extract(text, entities, ontology_relations)
        return self.judge.judge(text, entities, ontology_relations, proposals)
