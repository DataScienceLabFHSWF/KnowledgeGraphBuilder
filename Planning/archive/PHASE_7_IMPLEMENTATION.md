# Phase 7: Relation Extraction - Implementation Guide

**Date**: February 3, 2026  
**Status**: Ready to implement  
**Estimated Time**: 6-8 hours

---

## Architecture Context

### Full KG Building Pipeline (Phases 1-5)

```
Phase 1: Load Ontology
    ↓
Phase 2: Generate Questions
    ↓
Phase 3: Iterative Discovery Loop ← **VERIFIED WORKING (3+ iterations)**
    │
    ├─ Question → Retrieve Docs → Extract Entities
    ├─ Question → Retrieve Docs → Extract Entities
    ├─ Question → Retrieve Docs → Extract Entities
    │
Phase 4: Extract Relations ← **THIS PHASE (Phase 7 in roadmap)**
    │
    ├─ Take entities from Phase 3
    ├─ Extract relationships between them
    ├─ Validate against ontology constraints
    │
Phase 5: Assemble to Neo4j
    ├─ Create nodes (from Phase 3)
    ├─ Create edges (from Phase 4) ← **BLOCKED WITHOUT PHASE 7**
    ↓
Complete KG with entities + relationships
```

### Key Insight: Phase 8 (Validation) Per Iteration

**Important**: The architecture shows that **validation happens at EACH iteration**, not just at the end:

```
Iteration 1:
  ├─ Extract entities from Question 1
  ├─ Extract entities from Question 2
  ├─ Extract entities from Question 3
  ├─ [VALIDATION: Check extracted entities against ontology constraints]
  ├─ Record metrics (node count, confidence, CQ coverage)
  │
Iteration 2:
  ├─ Extract entities from Question 1 (again)
  ├─ Extract entities from Question 2 (again)
  ├─ Extract entities from Question 3 (again)
  ├─ [VALIDATION: Check incremental improvements]
  ├─ Record metrics (new nodes added, marginal gain)
  │
Iteration 3-N:
  └─ [CONTINUE UNTIL CONVERGENCE]
```

This means:
- **Per-iteration metrics** = Graph state + Validation status + Extraction quality
- **Phase 8 validation** runs each iteration to track progress
- **Convergence detection** = When metrics stabilize (no new nodes for N iterations)

---

## Phase 7 Implementation: Relation Extraction

### Overview

**Goal**: Extract relationships between entities extracted in Phase 3

**Input**: 
- Entities from IterativeDiscoveryLoop (with provenance)
- Original text chunks (with source documents)
- Ontology relations (domain/range constraints)

**Output**:
- List of ExtractedRelation objects with:
  - source_entity_id
  - target_entity_id
  - predicate (relation type)
  - confidence score
  - evidence (source chunks)

**Constraints**:
- Domain/range validation (relation can only connect certain entity types)
- Cardinality constraints (functional, inverse_functional)
- No circular relations (if applicable)

### Files to Modify/Create

```
src/kgbuilder/extraction/relation.py
  └─ LLMRelationExtractor.extract() [IMPLEMENT THIS]
  └─ LLMRelationExtractor._validate_domain_range() [IMPLEMENT THIS]
  └─ LLMRelationExtractor._check_cardinality_constraints() [IMPLEMENT THIS]

src/kgbuilder/extraction/chains.py
  └─ ExtractionChains.create_relation_extraction_chain() [ALREADY IMPLEMENTED]

tests/test_extraction_assembly.py
  └─ Tests already exist [VERIFY THEY PASS]
```

### Step 1: Understand Current Scaffolding

**File**: `src/kgbuilder/extraction/relation.py`

Currently has:
```python
class LLMRelationExtractor:
    def __init__(self, llm_provider, confidence_threshold=0.5, max_retries=3)
    
    def extract(self, text, entities, ontology_relations):
        # TODO: raise NotImplementedError()
        
    def _build_extraction_prompt(...)
    
    def _validate_domain_range(...)
        # TODO: raise NotImplementedError()
    
    def _check_cardinality_constraints(...)
        # TODO: raise NotImplementedError()
```

**File**: `src/kgbuilder/extraction/chains.py`

Already has:
```python
class ExtractionChains:
    @staticmethod
    def create_relation_extraction_chain(model, base_url, temperature):
        # ✅ COMPLETE - Returns LCEL Runnable chain
        # Prompt template + LLM + Parser all connected
```

The prompt template already includes:
```
"For each relationship found:
1. Assign a unique ID (rel_XXX format)
2. Identify source and target entity IDs
3. Determine the relationship type
4. Estimate confidence (0.0-1.0)
5. Ensure domain and range constraints are satisfied"
```

### Step 2: Implement `LLMRelationExtractor.extract()`

This is the main method. Here's the algorithm:

```python
def extract(
    self,
    text: str,
    entities: list[ExtractedEntity],
    ontology_relations: list[OntologyRelationDef],
) -> list[ExtractedRelation]:
    """
    Extract relations between entities.
    
    Algorithm:
    1. Build prompt with entities + text + ontology relations
    2. Call LLM with structured output (RelationExtractionOutput schema)
    3. Validate each relation:
       - Check domain/range constraints
       - Apply cardinality constraints
       - Filter by confidence threshold
    4. Return relations with evidence
    """
    
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
    attempts = 0
    relations = []
    
    while attempts < self.max_retries:
        try:
            # Run chain
            output = chain.invoke({
                "text": text,
                "entities_list": entity_list,
                "relations_section": relations_section,
            })
            
            # output is RelationExtractionOutput (from Pydantic parser)
            raw_relations = output.relations
            
            # 4. Validate each relation
            validated = []
            for rel in raw_relations:
                # Skip if low confidence
                if rel.confidence < self.confidence_threshold:
                    continue
                
                # Find source and target entities
                source_entity = self._find_entity_by_id(rel.source_id, entities)
                target_entity = self._find_entity_by_id(rel.target_id, entities)
                
                if not source_entity or not target_entity:
                    continue
                
                # Get ontology definition
                onto_def = ontology_dict.get(rel.relation_type)
                
                # Validate domain/range
                if not self._validate_domain_range(
                    relation=rel,
                    source_entity=source_entity,
                    target_entity=target_entity,
                    ontology_def=onto_def
                ):
                    continue
                
                # Convert to ExtractedRelation with evidence
                extracted = ExtractedRelation(
                    id=rel.id,
                    source_entity_id=source_entity.id,
                    target_entity_id=target_entity.id,
                    predicate=rel.relation_type,
                    confidence=rel.confidence,
                    evidence=[
                        Evidence(
                            source_text=text,
                            position=(0, len(text))  # Could refine this
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
                confidence_avg=sum(r.confidence for r in relations) / len(relations) if relations else 0
            )
            
            return relations
            
        except Exception as e:
            attempts += 1
            self._logger.warning(
                "relation_extraction_retry",
                attempt=attempts,
                error=str(e)
            )
            if attempts >= self.max_retries:
                self._logger.error(
                    "relation_extraction_failed",
                    error=str(e)
                )
                raise
```

### Step 3: Implement Helper Methods

**`_validate_domain_range()`**:

```python
def _validate_domain_range(
    self,
    relation: ExtractedRelation,
    source_entity: ExtractedEntity,
    target_entity: ExtractedEntity,
    ontology_def: OntologyRelationDef | None,
) -> bool:
    """
    Validate that relation respects ontology constraints.
    
    Args:
        relation: The extracted relation
        source_entity: Source entity
        target_entity: Target entity
        ontology_def: Ontology definition (if exists)
        
    Returns:
        True if valid, False otherwise
    """
    # If no ontology definition, assume valid (permissive)
    if not ontology_def:
        return True
    
    # Check domain (source must be in domain)
    if ontology_def.domain:
        source_match = any(
            entity_type in ontology_def.domain
            for entity_type in source_entity.entity_type.split("|")
        )
        if not source_match:
            self._logger.debug(
                "domain_check_failed",
                expected=ontology_def.domain,
                actual=source_entity.entity_type
            )
            return False
    
    # Check range (target must be in range)
    if ontology_def.range:
        target_match = any(
            entity_type in ontology_def.range
            for entity_type in target_entity.entity_type.split("|")
        )
        if not target_match:
            self._logger.debug(
                "range_check_failed",
                expected=ontology_def.range,
                actual=target_entity.entity_type
            )
            return False
    
    return True
```

**`_check_cardinality_constraints()`**:

```python
def _check_cardinality_constraints(
    self,
    relations: list[ExtractedRelation],
    ontology_defs: dict[str, OntologyRelationDef],
) -> list[ExtractedRelation]:
    """
    Filter relations by cardinality constraints.
    
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
            duplicate = any(
                r.source_entity_id == relation.source_entity_id and
                r.predicate == relation.predicate
                for r in filtered
            )
            if duplicate:
                self._logger.debug(
                    "functional_constraint_violated",
                    source=relation.source_entity_id,
                    predicate=relation.predicate
                )
                # Keep the one with higher confidence
                existing_idx = next(
                    i for i, r in enumerate(filtered)
                    if r.source_entity_id == relation.source_entity_id
                    and r.predicate == relation.predicate
                )
                if relation.confidence > filtered[existing_idx].confidence:
                    filtered[existing_idx] = relation
                continue
        
        # Check inverse functional constraint
        # (object, predicate) should not appear more than once
        if onto_def.is_inverse_functional:
            duplicate = any(
                r.target_entity_id == relation.target_entity_id and
                r.predicate == relation.predicate
                for r in filtered
            )
            if duplicate:
                self._logger.debug(
                    "inverse_functional_constraint_violated",
                    target=relation.target_entity_id,
                    predicate=relation.predicate
                )
                # Keep the one with higher confidence
                existing_idx = next(
                    i for i, r in enumerate(filtered)
                    if r.target_entity_id == relation.target_entity_id
                    and r.predicate == relation.predicate
                )
                if relation.confidence > filtered[existing_idx].confidence:
                    filtered[existing_idx] = relation
                continue
        
        # No constraint violation
        filtered.append(relation)
    
    return filtered
```

### Step 4: Integration with build_kg.py

The `build_kg.py` script already calls this in Phase 5:

```python
# In build_kg.py, Phase 5: Extract Relations

relation_extractor = LLMRelationExtractor(
    llm_provider=llm_provider,
    confidence_threshold=args.confidence_threshold,
    max_retries=3
)

relations = []
for chunk_text in all_chunks:
    chunk_relations = relation_extractor.extract(
        text=chunk_text,
        entities=discovered_entities,  # From Phase 3
        ontology_relations=ontology_relations
    )
    relations.extend(chunk_relations)
```

### Step 5: Testing

Run existing tests:

```bash
pytest tests/test_extraction_assembly.py::TestExtractionChains::test_format_relations_section -v
pytest tests/test_extraction_assembly.py -v
```

The tests are already written and should pass once implementation is complete.

---

## Integration into Phase 3 (Optional Future Enhancement)

Currently, Phase 7 extracts relations AFTER gathering all entities. 

**Future improvement** (Phase 8): Extract relations DURING Phase 3 iterations:

```
Iteration 1:
  ├─ Extract entities from all questions
  ├─ [NEW] Extract relations from discovered entities
  ├─ [Validation: Check entity + relation constraints]
  ├─ Record metrics
  │
Iteration 2:
  ├─ Extract entities from all questions (again)
  ├─ [NEW] Extract new relations
  ├─ [Validation: Check growth]
```

This would give per-iteration metrics on both entities AND relations.

---

## Phase 8: Validation Per Iteration (Architecture)

Once Phase 7 is done, Phase 8 will be integrated into the discovery loop:

```python
# Pseudocode for Phase 8 integration

for iteration in 1..max_iterations:
    # Phase 3: Extract entities
    entities = discovery_loop.run_discovery_iteration()
    
    # Phase 7: Extract relations
    relations = relation_extractor.extract_from_entities(entities)
    
    # Phase 8: VALIDATE THIS ITERATION
    validation_metrics = validator.validate(
        entities=entities,
        relations=relations,
        ontology=ontology,
        shacl_shapes=shacl_shapes
    )
    
    # Record metrics
    iteration_metrics = IterationMetrics(
        iteration_id=iteration,
        graph_state=GraphStateMetrics(
            node_count=len(entities),
            edge_count=len(relations),
            new_nodes_added=len(entities) - prev_count
        ),
        validation=ValidationMetrics(
            shacl_violations=validation_metrics.violations,
            cq_coverage=calculate_coverage(entities, cqs),
        ),
        extraction=ExtractionMetrics(
            avg_entity_confidence=mean(e.confidence for e in entities),
            avg_relation_confidence=mean(r.confidence for r in relations),
        )
    )
    metrics_collector.record(iteration_metrics)
    
    # Check convergence
    if is_converged(iteration_metrics, prev_metrics):
        break
```

This is Phase 10 (Experiment Framework) work, which depends on Phases 7-8.

---

## Success Criteria

- [ ] `LLMRelationExtractor.extract()` implemented and returns ExtractedRelation list
- [ ] Domain/range validation working
- [ ] Cardinality constraints enforced
- [ ] Confidence scoring on relations
- [ ] All tests passing
- [ ] Relations being created in Neo4j (verify with `/tmp/query_graph.py`)
- [ ] Graph structure visible (edges connecting nodes)

---

## Files Summary

| File | Status | Action |
|------|--------|--------|
| `src/kgbuilder/extraction/relation.py` | 🟡 Partial | Implement 3 methods |
| `src/kgbuilder/extraction/chains.py` | ✅ Done | No changes |
| `tests/test_extraction_assembly.py` | ✅ Done | Just run |
| `scripts/build_kg.py` | ✅ Done | Already integrated |

---

## Quick Start

1. Open `src/kgbuilder/extraction/relation.py`
2. Implement `LLMRelationExtractor.extract()` using the algorithm above
3. Implement `_validate_domain_range()` 
4. Implement `_check_cardinality_constraints()`
5. Run tests: `pytest tests/test_extraction_assembly.py -v`
6. Test with: `python scripts/build_kg.py --questions-per-class 1 --max-iterations 1`

**Estimated time: 6-8 hours**

Once done, you'll have full entities + relations in the KG! 🎉

