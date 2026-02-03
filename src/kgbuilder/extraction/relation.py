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

import structlog
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable, TYPE_CHECKING

from kgbuilder.core.models import ExtractedEntity, ExtractedRelation, Evidence
from kgbuilder.extraction.schemas import RelationExtractionOutput

if TYPE_CHECKING:
    from kgbuilder.extraction.chains import ExtractionChains

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
        chain = ExtractionChains.create_relation_extraction_chain(
            model="qwen3",
            base_url="http://localhost:11434",
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
                    extracted = ExtractedRelation(
                        id=rel_item.id,
                        source_entity_id=source_entity.id,
                        target_entity_id=target_entity.id,
                        predicate=rel_item.relation_type,
                        confidence=rel_item.confidence,
                        evidence=[
                            Evidence(
                                source_text=text,
                                position=(0, len(text))
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

TEXT TO ANALYZE:
{text}

For each relationship found:
1. Assign a unique ID (rel_XXX format)
2. Identify source and target entity IDs from the list above
3. Determine the relationship type from valid relationships
4. Estimate confidence (0.0-1.0)
5. Ensure domain and range constraints are satisfied

Extract all valid relationships. Only include relationships between entities in the provided list.
Respect domain/range constraints from the relationship definitions."""

    def _format_entities_for_prompt(
        self,
        entities: list[ExtractedEntity]
    ) -> str:
        """Format entities for display in prompt.
        
        Args:
            entities: List of entities
            
        Returns:
            Formatted entity list string
        """
        lines = []
        for entity in entities:
            lines.append(f"- {entity.id}: {entity.label} ({entity.entity_type}) [Confidence: {entity.confidence:.2f}]")
        return "\n".join(lines)

    def _find_entity_by_id(
        self,
        entity_id: str,
        entities: list[ExtractedEntity]
    ) -> ExtractedEntity | None:
        """Find entity by ID in the list.
        
        Args:
            entity_id: Entity ID to find
            entities: List of entities
            
        Returns:
            Entity if found, None otherwise
        """
        for entity in entities:
            if entity.id == entity_id:
                return entity
        return None

    def _validate_domain_range(
        self,
        source_entity: ExtractedEntity,
        target_entity: ExtractedEntity,
        ontology_def: OntologyRelationDef | None,
    ) -> bool:
        """Validate domain/range constraints for a relation.

        Args:
            source_entity: Source entity
            target_entity: Target entity
            ontology_def: Ontology relation definition (None = no constraints)

        Returns:
            True if constraints satisfied
        """
        # If no ontology definition, assume valid (permissive)
        if not ontology_def:
            return True
        
        # Check domain (source must be in domain)
        if ontology_def.domain:
            source_types = {t.strip() for t in source_entity.entity_type.split("|")}
            domain_types = set(ontology_def.domain)
            
            if not source_types.intersection(domain_types):
                self._logger.debug(
                    "domain_check_failed",
                    expected=ontology_def.domain,
                    actual=source_entity.entity_type
                )
                return False
        
        # Check range (target must be in range)
        if ontology_def.range:
            target_types = {t.strip() for t in target_entity.entity_type.split("|")}
            range_types = set(ontology_def.range)
            
            if not target_types.intersection(range_types):
                self._logger.debug(
                    "range_check_failed",
                    expected=ontology_def.range,
                    actual=target_entity.entity_type
                )
                return False
        
        return True

    def _check_cardinality_constraints(
        self,
        relations: list[ExtractedRelation],
        ontology_defs: dict[str, OntologyRelationDef],
    ) -> list[ExtractedRelation]:
        """Filter relations by cardinality constraints.

        - is_functional: (source, predicate) can have at most 1 object
        - is_inverse_functional: (object, predicate) can have at most 1 subject

        Args:
            relations: Extracted relations
            ontology_defs: Ontology relation definitions by URI

        Returns:
            Filtered relations respecting cardinality
        """
        filtered = []
        
        for relation in relations:
            onto_def = ontology_defs.get(relation.predicate)
            
            if not onto_def:
                # No constraints, keep it
                filtered.append(relation)
                continue
            
            # Check functional constraint
            # (source, predicate) should not appear more than once
            if onto_def.is_functional:
                # Look for existing relation with same source and predicate
                existing = None
                existing_idx = None
                for i, r in enumerate(filtered):
                    if (r.source_entity_id == relation.source_entity_id and
                        r.predicate == relation.predicate):
                        existing = r
                        existing_idx = i
                        break
                
                if existing:
                    self._logger.debug(
                        "functional_constraint_check",
                        source=relation.source_entity_id,
                        predicate=relation.predicate,
                        existing_confidence=existing.confidence,
                        new_confidence=relation.confidence
                    )
                    # Keep the one with higher confidence
                    if relation.confidence > existing.confidence:
                        filtered[existing_idx] = relation
                    continue
            
            # Check inverse functional constraint
            # (target, predicate) should not appear more than once
            if onto_def.is_inverse_functional:
                # Look for existing relation with same target and predicate
                existing = None
                existing_idx = None
                for i, r in enumerate(filtered):
                    if (r.target_entity_id == relation.target_entity_id and
                        r.predicate == relation.predicate):
                        existing = r
                        existing_idx = i
                        break
                
                if existing:
                    self._logger.debug(
                        "inverse_functional_constraint_check",
                        target=relation.target_entity_id,
                        predicate=relation.predicate,
                        existing_confidence=existing.confidence,
                        new_confidence=relation.confidence
                    )
                    # Keep the one with higher confidence
                    if relation.confidence > existing.confidence:
                        filtered[existing_idx] = relation
                    continue
            
            # No constraint violation
            filtered.append(relation)
        
        return filtered
