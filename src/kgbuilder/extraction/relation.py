"""Relation extraction using LLM with ontology constraints.

Implementation of Issue #5.1, #5.3: Relation Extraction

Key features:
- Ontology-guided relation extraction
- Domain/range constraint validation
- Cardinality constraint enforcement
- Support for n-ary relations via reification
- Multi-pass extraction for complex dependencies
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import structlog

from kgbuilder.core.models import Evidence, ExtractedEntity, ExtractedRelation
from kgbuilder.extraction.schemas import RelationExtractionOutput

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)


@dataclass
class OntologyRelationDef:
    """Ontology relation/property definition for extraction guidance."""

    uri: str
    label: str
    description: str | None = None
    domain: list[str] = field(default_factory=list)  # Class URIs
    range: list[str] = field(default_factory=list)  # Class URIs or datatypes
    is_functional: bool = False  # At most one value
    is_inverse_functional: bool = False
    is_transitive: bool = False
    is_symmetric: bool = False
    examples: list[tuple[str, str]] = field(default_factory=list)


@runtime_checkable
class RelationExtractor(Protocol):
    """Protocol for relation extraction implementations."""

    def extract(
        self,
        text: str,
        entities: list[ExtractedEntity],
        ontology_relations: list[OntologyRelationDef],
    ) -> list[ExtractedRelation]:
        """Extract relations between entities.

        Args:
            text: Source text
            entities: Entities found in text
            ontology_relations: Valid relation types

        Returns:
            List of extracted relations
        """
        ...


class LLMRelationExtractor:
    """LLM-based relation extractor with ontology constraints.

    Implements structured extraction with:
    - Ontology-guided relation extraction with domain/range validation
    - Cardinality constraint enforcement (functional, inverse-functional)
    - Error recovery with configurable retries
    - Confidence threshold filtering
    - Comprehensive logging for debugging

    See Planning/ISSUES_BACKLOG.md Issue #5.3 for acceptance criteria.
    """

    def __init__(
        self,
        llm_provider: Any,  # LLMProvider
        confidence_threshold: float = 0.5,
        max_retries: int = 3,
    ) -> None:
        """Initialize relation extractor.

        Args:
            llm_provider: LLM provider instance
            confidence_threshold: Minimum confidence for relations
            max_retries: Max retries on extraction failure
        """
        self._llm = llm_provider
        self.confidence_threshold = confidence_threshold
        self.max_retries = max_retries
        self._logger = logger

    def extract(
        self,
        text: str,
        entities: list[ExtractedEntity],
        ontology_relations: list[OntologyRelationDef],
    ) -> list[ExtractedRelation]:
        """Extract relations between entities with ontology constraints.

        Args:
            text: Source text
            entities: Entities already extracted
            ontology_relations: Valid relation types

        Returns:
            List of extracted relations
        """
        from kgbuilder.extraction.chains import ExtractionChains

        if not entities or not ontology_relations:
            return []

        # 1. Format input for LLM
        entity_list = self._format_entities_for_prompt(entities)
        relations_section = ExtractionChains.format_relations_section(ontology_relations)
        ontology_dict = {r.uri: r for r in ontology_relations}

        # 2. Get LLM chain
        model = getattr(self._llm, "model", "qwen3:8b")
        base_url = getattr(self._llm, "base_url", None)

        chain = ExtractionChains.create_relation_extraction_chain(
            model=model,
            base_url=base_url,
            temperature=0.5
        )

        # 3. Call LLM with retry logic
        for attempt in range(self.max_retries):
            try:
                # Run chain
                output: RelationExtractionOutput = chain.invoke({
                    "text": text,
                    "entities_list": entity_list,
                    "relations_section": relations_section,
                })

                # 4. Validate each relation
                validated = []
                for rel_item in output.relations:
                    # Skip if low confidence
                    if rel_item.confidence < self.confidence_threshold:
                        continue

                    # Find source and target entities by ID
                    source_entity = self._find_entity_by_id(rel_item.source_id, entities)
                    target_entity = self._find_entity_by_id(rel_item.target_id, entities)

                    if not source_entity or not target_entity:
                        continue

                    # Get ontology definition
                    onto_def = ontology_dict.get(rel_item.relation_type)

                    # Validate domain/range
                    if not self._validate_domain_range(
                        source_entity=source_entity,
                        target_entity=target_entity,
                        ontology_def=onto_def
                    ):
                        continue

                    # Convert to ExtractedRelation with evidence
                    from kgbuilder.core.models import generate_relation_id

                    extracted = ExtractedRelation(
                        id=generate_relation_id(
                            source_entity.id,
                            target_entity.id,
                            rel_item.relation_type,
                        ),
                        source_entity_id=source_entity.id,
                        target_entity_id=target_entity.id,
                        predicate=rel_item.relation_type,
                        confidence=rel_item.confidence,
                        evidence=[
                            Evidence(
                                source_type="local_doc",
                                source_id="text",
                                text_span=text[:500], # Don't store huge text in every relation evidence
                                confidence=rel_item.confidence
                            )
                        ]
                    )
                    validated.append(extracted)

                # 5. Check cardinality constraints
                relations = self._check_cardinality_constraints(
                    validated,
                    ontology_dict
                )

                self._logger.info(
                    "relation_extraction_success",
                    extracted_count=len(relations),
                    confidence_avg=sum(r.confidence for r in relations) / len(relations) if relations else 0.0
                )

                return relations

            except Exception as e:
                attempt += 1
                self._logger.warning(
                    "relation_extraction_retry",
                    attempt=attempt,
                    error=str(e)
                )
                if attempt >= self.max_retries:
                    self._logger.error(
                        "relation_extraction_failed",
                        error=str(e)
                    )
                    return []

        return []

    def _build_extraction_prompt(
        self,
        text: str,
        entities: list[ExtractedEntity],
        ontology_relations: list[OntologyRelationDef],
    ) -> str:
        """Build structured extraction prompt with ontology guidance.

        Args:
            text: Source text
            entities: Entities for relation context
            ontology_relations: Valid relation types

        Returns:
            Formatted prompt string
        """
        from kgbuilder.extraction.chains import ExtractionChains

        entity_list = self._format_entities_for_prompt(entities)
        relations_section = ExtractionChains.format_relations_section(ontology_relations)

        return f"""Extract relationships between the following entities from the text.

ENTITIES MENTIONED:
{entity_list}

VALID RELATIONSHIPS:
{relations_section}

EXTRACTION GUIDELINES:
1. Assign unique IDs (rel_XXX format)
2. Identify source and target entity IDs from the list above
3. Determine relationship type from valid relationships
4. Estimate confidence (0.0-1.0) based on textual evidence
5. Ensure domain and range constraints are satisfied (critical!)

CONFIDENCE SCORING:
- 0.9-1.0: Explicit mention of relationship in text
- 0.7-0.9: Strong contextual evidence
- 0.5-0.7: Implied or inferred relationship with ambiguity
- <0.5: Skip (uncertain)

RESPONSE FORMAT:
Return ONLY valid JSON matching the RelationExtractionOutput schema.

EXAMPLE OUTPUT:
{{
  "relations": [
    {{
      "id": "rel_001",
      "source_entity_id": "ent_001",
      "target_entity_id": "ent_002",
      "predicate": "RelationTypeFromAbove",
      "confidence": 0.92,
      "evidence": "Text snippet supporting this relationship..."
    }}
  ]
}}

TEXT TO ANALYZE:
{text}

Extract all valid relationships between entities. Return ONLY JSON.
Only include relationships between entities in the provided list.
Respect domain/range constraints strictly."""

    @staticmethod
    def _format_entities_for_prompt(
        entities: list[ExtractedEntity]
    ) -> str:
        """Serialize entities into a human-readable list for prompting.

        Args:
            entities: Entities to include in the prompt

        Returns:
            A newline-separated string where each line describes one entity.

        This helper is used both in prompt construction and in tests to verify
        the formatting logic independently of any extractor instance.
        """
        lines: list[str] = []
        for entity in entities:
            lines.append(
                f"- {entity.id}: {entity.label} ({entity.entity_type}) "
                f"[Confidence: {entity.confidence:.2f}]"
            )
        return "\n".join(lines)

    @staticmethod
    def _find_entity_by_id(
        entity_id: str,
        entities: list[ExtractedEntity]
    ) -> ExtractedEntity | None:
        """Lookup an entity with the given ID within a list.

        Args:
            entity_id: Identifier to search for.
            entities: List of `ExtractedEntity` objects.

        Returns:
            The matching entity or ``None`` if not found.

        This is a simple linear search used during validation of LLM output.
        Making it static allows individual testing without creating a full
        `LLMRelationExtractor` instance.
        """
        for entity in entities:
            if entity.id == entity_id:
                return entity
        return None

    @staticmethod
    def _validate_domain_range(
        source_entity: ExtractedEntity,
        target_entity: ExtractedEntity,
        ontology_def: OntologyRelationDef | None,
    ) -> bool:
        """Check that a candidate relation satisfies ontological constraints.

        A relation is considered valid if:
        1. ``ontology_def`` is ``None`` (no constraints)
        2. ``source_entity.entity_type`` intersects ``ontology_def.domain`` (if
           domain list is non-empty)
        3. ``target_entity.entity_type`` intersects ``ontology_def.range`` (if
           range list is non-empty)

        Args:
            source_entity: The prospective source of the relation.
            target_entity: The prospective target of the relation.
            ontology_def: Relation definition containing domain/range lists.

        Returns:
            ``True`` if the constraint checks pass, ``False`` otherwise.
        """
        if not ontology_def:
            return True

        if ontology_def.domain:
            source_types = {t.strip() for t in source_entity.entity_type.split("|")}
            domain_types = set(ontology_def.domain)
            if not source_types.intersection(domain_types):
                logger.debug(
                    "domain_check_failed",
                    expected=ontology_def.domain,
                    actual=source_entity.entity_type,
                )
                return False

        if ontology_def.range:
            target_types = {t.strip() for t in target_entity.entity_type.split("|")}
            range_types = set(ontology_def.range)
            if not target_types.intersection(range_types):
                logger.debug(
                    "range_check_failed",
                    expected=ontology_def.range,
                    actual=target_entity.entity_type,
                )
                return False

        return True

    @staticmethod
    def _check_cardinality_constraints(
        relations: list[ExtractedRelation],
        ontology_defs: dict[str, OntologyRelationDef],
    ) -> list[ExtractedRelation]:
        """Filter a list of relations according to cardinality rules.

        The following constraints are supported:
        * **functional** – each (source, predicate) pair appears at most once.
        * **inverse_functional** – each (target, predicate) pair appears at most
          once.

        If a conflict is detected, the relation with higher confidence is
        retained.  If no ontology definition exists for a predicate the relation
        is kept unconditionally.

        This method is static so it can be exercised in isolation by unit tests.

        Args:
            relations: Candidate relations extracted from text.
            ontology_defs: Map from predicate URI to its ontology definition.

        Returns:
            A filtered list of relations honouring the specified constraints.
        """
        filtered: list[ExtractedRelation] = []

        for relation in relations:
            onto_def = ontology_defs.get(relation.predicate)

            if not onto_def:
                filtered.append(relation)
                continue

            # functional constraint
            if onto_def.is_functional:
                for i, r in enumerate(filtered):
                    if r.source_entity_id == relation.source_entity_id and r.predicate == relation.predicate:
                        logger.debug(
                            "functional_constraint_check",
                            source=relation.source_entity_id,
                            predicate=relation.predicate,
                            existing_confidence=r.confidence,
                            new_confidence=relation.confidence,
                        )
                        if relation.confidence > r.confidence:
                            filtered[i] = relation
                        break
                else:
                    filtered.append(relation)
                continue

            # inverse functional constraint
            if onto_def.is_inverse_functional:
                for i, r in enumerate(filtered):
                    if r.target_entity_id == relation.target_entity_id and r.predicate == relation.predicate:
                        logger.debug(
                            "inverse_functional_constraint_check",
                            target=relation.target_entity_id,
                            predicate=relation.predicate,
                            existing_confidence=r.confidence,
                            new_confidence=relation.confidence,
                        )
                        if relation.confidence > r.confidence:
                            filtered[i] = relation
                        break
                else:
                    filtered.append(relation)
                continue

            filtered.append(relation)

        return filtered
