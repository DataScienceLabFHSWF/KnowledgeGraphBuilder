# C1: Seed-based Automatic Ontology Extension with HITL

**Status**: Specification & Detailed Design  
**Effort Estimate**: 12-16 weeks  
**Dependencies**: Phase 4 (Discovery loop, entity extraction, relation extraction)  
**Scope**: Sub-project for iterative ontology development driven by document evidence

---

## 1. Overview & Motivation

### Problem Statement
The base Planning Ontology (https://github.com/BharathMuppasani/AI-Planning-Ontology) has 18 classes and 26 relations optimized for **automated planning research**. When applied to **nuclear decommissioning planning documents**, it covers only the high-level structure but misses domain-specific concepts (e.g., `Facility`, `Permit`, `RadiationHazard`, `DecommissioningStrat egy`, `LegalRequirement`).

### Approach: Seed-Driven Ontology Extension
**Hypothesis**: By analyzing document-extracted entities and relations, we can **automatically propose new ontology classes and relations** while preserving semantic correctness via constraints and human review.

**Process**:
1. Start with proven seed ontology
2. Discover candidate new classes from documents
3. Propose relations between new classes and seed classes
4. Validate via SHACL constraints
5. Human expert reviews and accepts/rejects/refines
6. Measure coverage improvement via competency questions

---

## 2. Component Specifications

### C1.1: Seed Ontology & Competency Questions

**Objective**: Get a baseline that correctly answers key questions about decommissioning.

#### Artifacts
- **Seed Ontology**: `data/ontology/plan-ontology-v1.0.owl` (18 classes, 26 relations)
- **Competency Questions**: `data/evaluation/competency_questions.json` (9 questions, already defined)
- **Baseline CQ Assessment**: Run QA over seed ontology on current documents

#### Subtasks

**C1.1.1: Competency Question Refinement**
- [ ] Validate existing 9 CQs against decommissioning domain
  - Are they well-scoped and answerable?
  - Do they cover the full document space?
- [ ] Add 5-10 new domain-specific CQs
  - Example: "What are the prerequisites for decommissioning a facility?"
  - Example: "Which regulations govern plutonium transport?"
  - Example: "What are the main decommissioning strategies documented?"
- [ ] Map each CQ to:
  - Expected entity types (e.g., `Facility`, `Regulation`, `Strategy`)
  - Expected relations (e.g., `appliesTo`, `requiresPrerequisite`)
  - Difficulty level (1-5)
  - Priority (for iterative extension)

**C1.1.2: Seed Ontology Quality Assessment**
- [ ] Load seed ontology into Fuseki
- [ ] Run baseline extraction on 10 sample documents
  - Use existing LLMEntityExtractor + RuleBasedExtractor
  - Map extracted entities to seed ontology classes (coverage %)
- [ ] Run baseline QA
  - Execute each CQ as a SPARQL query
  - Measure answerability rate (% CQs with results)
  - Document gaps

**Deliverables**:
- Refined CQ JSON with mappings
- Baseline coverage report (seed ontology covers X% of extracted concepts)
- Gap analysis: What entity types and relations are **not** in the seed?

---

### C1.2: Ontology-Guided Concept Discovery

**Objective**: Mine documents for candidate new ontology classes and relations.

#### Key Insight
Entities that:
1. Exist in documents (extracted by LLM/Rules)
2. Are not covered by seed ontology classes
3. Appear frequently OR have high semantic importance
→ Should be **candidate new classes**

#### Execution

**C1.2.1: Ontology Gap Analysis**
- [ ] Implement `OntologyGapAnalyzer` class
  ```python
  class OntologyGapAnalyzer:
      def __init__(self, ontology_service, extracted_entities):
          """Analyze which extracted entities don't fit seed ontology."""
      
      def get_uncovered_entities(self) -> list[ExtractedEntity]:
          """Entities not assignable to any seed class."""
      
      def suggest_new_classes(self, min_frequency=3) -> list[ProposedClass]:
          """Suggest new classes based on uncovered entities."""
          # Group by semantic similarity
          # Return top candidates by frequency + confidence
  ```

- [ ] Input: 100-500 extracted entities from Phase 4 extraction
- [ ] Process
  - For each entity, try to match to seed ontology class
  - If no match (or low confidence < 0.6), mark as **gap candidate**
  - Group gap candidates by:
    - Semantic similarity (embeddings)
    - Linguistic patterns (entity_type from LLM)
    - Frequency in documents
- [ ] Output: Ranked list of `ProposedClass(label, definition, examples, frequency, confidence)`

**C1.2.2: Proposed Class Definitions**
- [ ] Implement `ClassDefinitionGenerator`
  ```python
  class ClassDefinitionGenerator:
      def generate_definition(
          self,
          proposed_class: ProposedClass,
          ontology_hierarchy: OntologyHierarchy,
      ) -> ClassDefinition:
          """Generate structured class definition via LLM."""
          # 1. Find most similar seed classes
          # 2. Determine parent class (subClassOf)
          # 3. Generate formal definition
          # 4. Suggest properties (domain: DatatypeProperty)
          # 5. Suggest relations (domain: ObjectProperty)
  ```

- [ ] For each proposed class:
  - Generate formal definition (via LLM with seed ontology context)
  - Suggest parent class (is it a subclass of something in seed?)
  - Example instances from documents
  - Candidate properties (via LLM)
  - Suggested relations to other classes

**C1.2.3: Relation Generation**
- [ ] Implement `RelationProposalGenerator`
  - For new classes and seed classes, look for extracted relations
  - Suggest new ObjectProperties that connect concepts
  - Example: `Facility --requires--> Permit`, `Person --manages--> Facility`

**Deliverables**:
- List of 15-30 proposed new classes with:
  - Label, definition, examples (3-5 each)
  - Parent class (subClassOf link to seed)
  - Confidence score (based on frequency, semantic similarity)
  - Suggested properties and relations
- Ranking by priority (domain experts can review high-priority first)

---

### C1.3: Constraint-Aware Ontology Update

**Objective**: Add proposed classes/relations to ontology while maintaining semantic correctness.

#### Implementation

**C1.3.1: Ontology Schema Management**
- [ ] Implement `OntologySchemaManager`
  ```python
  class OntologySchemaManager:
      def add_class(
          self,
          label: str,
          definition: str,
          parent_uri: str,  # Must exist in seed
          properties: list[PropertyDef],
          constraints: list[SHACLConstraint],
      ) -> ClassDefinition:
          """Add new class to Fuseki ontology with validation."""
          # 1. Validate parent exists
          # 2. Generate OWL/SHACL definitions
          # 3. Check for conflicts with existing classes
          # 4. Upload to Fuseki (in temp graph for review)
          # 5. Return versioned definition
      
      def add_relation(
          self,
          label: str,
          domain: str,  # class URI
          range: str,   # class URI
          constraints: list[SHACLConstraint],
      ) -> RelationDefinition:
          """Add new relation/ObjectProperty."""
  ```

**C1.3.2: SHACL Constraint Definition**
- [ ] For each proposed class, define SHACL shapes:
  ```turtle
  ex:FacilityShape
      a sh:NodeShape ;
      sh:targetClass ex:Facility ;
      sh:property [
          sh:path rdfs:label ;
          sh:minCount 1 ;
          sh:maxCount 1 ;
          sh:datatype xsd:string ;
      ] ;
      sh:property [
          sh:path ex:hasLocation ;
          sh:class ex:Location ;
          sh:maxCount 1 ;
      ] .
  ```

- [ ] Validate proposed additions against:
  - Domain/range constraints
  - Cardinality constraints (1..1, 0..*,etc.)
  - No conflicting definitions
  - Consistent with seed ontology style

**C1.3.3: Versioning & Staging**
- [ ] Create parallel graphs in Fuseki:
  - `kgbuilder-main` — accepted seed + approved extensions
  - `kgbuilder-staging-v1`, `v2`, etc. — under review
  - `kgbuilder-snapshot-<date>` — historical versions

- [ ] Implement `OntologyVersionManager`
  - Track which proposed classes are in which version
  - Record acceptance/rejection decisions
  - Generate diffs between versions

**Deliverables**:
- OWL file with proposed classes in staging graph
- SHACL shape definitions for each new class
- Version metadata with change reasons

---

### C1.4: Human-in-the-Loop Validation

**Objective**: Enable domain experts to review, refine, and accept/reject proposals.

#### Implementation

**C1.4.1: Review Interface Design**
- [ ] Create `OntologyReviewUI` (CLI or web-based)
  - Display proposed class with:
    - Definition
    - Examples from documents
    - Parent class
    - Suggested properties/relations
    - Coverage metrics (how many docs mention this concept?)
  - Buttons: Accept / Reject / Modify / Ask for Clarification

**C1.4.2: Review Workflow**
```
1. Display proposal to expert
   - Show class definition, examples, confidence
   - Ask: "Should this be a class? Yes / No / Discuss"

2. If "Modify":
   - Expert changes definition, properties, parent class
   - System validates against SHACL
   - Re-run competency questions with modified class

3. If "Accept":
   - Class added to kgbuilder-main graph
   - Update versions
   - Log decision + rationale
   - Run full re-indexing

4. If "Reject":
   - Class marked as declined
   - Optionally: suggest alternative characterization
```

**C1.4.3: Feedback Loop Implementation**
- [ ] Implement `OntologyFeedbackCollector`
  - Capture expert comments for each acceptance/rejection
  - Track confidence trends (does expert agree with algo more over time?)
  - Suggest refinements based on patterns of feedback

**Deliverables**:
- CLI/web tool for HITL review
- Workflow documentation
- Feedback database structure

---

### C1.5: Ontology Evaluation

**Objective**: Measure whether extensions improve KG completeness and CQ coverage.

#### Metrics

**C1.5.1: CQ Coverage**
```python
class CQEvaluator:
    def evaluate_coverage(
        self,
        cqs: list[CompetencyQuestion],
        graph: GraphStore,
    ) -> dict[str, CQResult]:
        """For each CQ, run the query and check answerability."""
        # CQResult: {
        #   "cq_id": "CQ_001",
        #   "answerable": True,
        #   "result_count": 5,
        #   "query_time_ms": 234,
        #   "confidence": 0.92,
        # }
```

- [ ] Baseline: CQ coverage with seed ontology
- [ ] After each iteration: Re-measure coverage with extended ontology
- [ ] Target: **80%+ CQ answerability**

**C1.5.2: KG Completeness**
```python
class CompleteneseAnalyzer:
    def measure_schema_coverage(self) -> dict:
        # % of extracted entities assigned to ontology classes
        # before: ~30% (gap candidates)
        # after: target 80%+
        return {
            "covered_entities": 850,
            "total_entities": 1200,
            "coverage_pct": 70.8,
            "gap_entities": 350,
        }
```

**C1.5.3: Ontology Quality Metrics**
- [ ] Class coverage: % of extracted entity types fit ontology
- [ ] Relation coverage: % of extracted relations fit ontology relations
- [ ] Constraint satisfaction: % of triples satisfy SHACL constraints
- [ ] Documentation completeness: % of classes with definitions, examples

**C1.5.4: Expert Feedback Analysis**
- [ ] Track acceptance rate per expert (improving over time?)
- [ ] Analyze rejection reasons (too specific? Wrong parent? Unclear definition?)
- [ ] Measure expert agreement rate (two experts review same class)

**Deliverables**:
- Evaluation framework with metrics
- Comparison reports: seed vs. extended ontology
- Expert feedback analytics

---

## 3. Workflow & Iteration Cycles

### Iteration 1: Initial Extension (2-3 weeks)

**Phase 1: Discovery (Days 1-3)**
- Extract entities from 30 documents (Phase 4 works → ~500 entities)
- Analyze gaps, propose 15-20 new classes
- **Output**: Prioritized list of proposed classes

**Phase 2: Definition (Days 4-6)**
- Expert team reviews top 5 proposals
- Refine definitions, parent classes, properties
- Add to staging graph
- **Output**: 5 accepted new classes in Fuseki staging

**Phase 3: Validation (Day 7)**
- Run full KG extraction with extended ontology
- Measure CQ coverage improvement
- **Output**: Before/after metrics

### Iteration 2-4: Incremental Extension (3-4 cycles, 8-12 weeks)
- Repeat with remaining proposed classes
- Measure compound improvement
- Feedback loop: adjust discovery criteria based on feedback

### Final: Production Release
- Merge staging → main graph
- Create frozen version snapshot
- Document all decisions and rationale

---

## 4. Technical Architecture

### Data Structures

```python
@dataclass
class ProposedClass:
    """Candidate new ontology class."""
    label: str
    definition: str              # Auto-generated initially
    parent_uri: str              # Link to seed class
    examples: list[str]          # From extracted entities
    frequency: int               # How many docs mention it
    confidence: float            # (0-1) based on semantic cohesion
    suggested_properties: list[PropertyDef]
    suggested_relations: list[RelationDef]
    status: Literal["proposed", "under_review", "accepted", "rejected"]

@dataclass
class ReviewDecision:
    """Expert feedback on a proposed class."""
    reviewer: str
    timestamp: datetime
    classification_decision: Literal["accepted", "rejected", "refine"]
    rationale: str
    suggested_changes: dict  # {field: new_value}
    confidence_in_decision: float  # (0-1)

@dataclass
class OntologyDiff:
    """Change summary between versions."""
    added_classes: list[str]
    removed_classes: list[str]
    added_relations: list[tuple[str, str, str]]
    version_id: str
    timestamp: datetime
    cq_coverage_before: float
    cq_coverage_after: float
```

### Module Structure

```
src/kgbuilder/ontology_extension/
├── __init__.py
├── gap_analyzer.py              # C1.2.1
├── class_generator.py           # C1.2.2
├── relation_generator.py        # C1.2.3
├── schema_manager.py            # C1.3.1
├── constraint_validator.py      # C1.3.2
├── version_manager.py           # C1.3.3
├── review_interface.py          # C1.4.1
├── feedback_collector.py        # C1.4.2
├── evaluator.py                 # C1.5
└── workflows/
    ├── __init__.py
    ├── discovery.py             # C1.2 pipeline
    ├── validation.py            # C1.3 pipeline
    ├── review.py                # C1.4 pipeline
    └── evaluation.py            # C1.5 pipeline
```

---

## 5. Implementation Roadmap

### Week 1-2: Foundation (C1.1 → C1.2.1)
- [ ] Competency question refinement
- [ ] Baseline assessment
- [ ] OntologyGapAnalyzer implementation
- **Deliverable**: List of 20 proposed classes

### Week 3-4: Discovery Pipeline (C1.2.2 → C1.2.3)
- [ ] ClassDefinitionGenerator (LLM-based)
- [ ] RelationProposalGenerator
- [ ] SHACL constraint generation
- **Deliverable**: Fully specified proposals with definitions & properties

### Week 5-6: Ontology Management (C1.3)
- [ ] OntologySchemaManager (add/remove classes)
- [ ] Version management infrastructure
- [ ] Fuseki staging graph setup
- **Deliverable**: Staging graph in Fuseki with proposed classes

### Week 7-8: Review Interface (C1.4)
- [ ] CLI/web HITL review tool
- [ ] Feedback database
- [ ] Workflow orchestration
- **Deliverable**: Working review interface, first round of expert reviews

### Week 9-10: Evaluation (C1.5)
- [ ] CQ evaluator
- [ ] Metrics framework
- [ ] Reporting dashboard
- **Deliverable**: Baseline vs. extended comparison report

### Week 11-12: Iteration Cycles
- [ ] Repeat discovery → validation → review → evaluation
- [ ] Refine based on feedback
- [ ] Production release
- **Deliverable**: Extended production ontology

---

## 6. Success Criteria

| Criterion | Target | Measurement |
|-----------|--------|-------------|
| **CQ Answerability** | 80%+ | SPARQL query results / total CQs |
| **Entity Coverage** | 80%+ | Entities assigned to ontology / total extracted |
| **Expert Agreement** | 75%+ | Acceptances / total proposals |
| **Ontology Growth** | 20-30 classes | New classes added to seed (18 base) |
| **Documentation** | 100% | All new classes have definitions + examples |
| **Constraint Validity** | 100% | Triples satisfying SHACL constraints |

---

## 7. Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|-----------|
| Expert review bottleneck | High | Slows iteration | Parallel reviews (2+ experts) |
| Proposed classes too specific | Medium | Low CQ coverage | Adjust semantic similarity threshold |
| Ontology semantic drift | Low | KG quality | Regular SHACL validation + expert audit |
| LLM definition quality | Medium | Poor class definitions | Example verification + refinement loop |
| Fuseki performance | Low | Slow QA/evaluation | Index optimization, caching |

---

## 8. Integration with Main Pipeline

**Trigger Point**: After Phase 4 extraction generates candidate entities

**Data Flow**:
```
Phase 4 Extraction
  ↓ (extracted entities, relations)
C1 Ontology Extension
  ├── C1.2 Discovery (gap analysis)
  ├── C1.3 Schema Update (new classes)
  ├── C1.4 HITL Review (expert validation)
  └── C1.5 Evaluation (metrics)
  ↓ (extended ontology)
Phase 4b Re-extraction
  (using extended ontology for better entity type assignment)
```

**Decision Point**: Accept extended ontology → update Fuseki graph → re-index

---

## 9. References & Related Work

**Ontology Learning**:
- Navigli, R., & Velardi, P. (2010). "Learning word embeddings from SemCor." ACM Transactions on Knowledge Discovery from Data
- Bansal, M., Bhattacharyya, P., & Bhattacharya, I. (2015). "Structured prediction models for RDF triples and entity linking"

**Interactive Ontology Refinement**:
- Völker, J., Vrandečić, D., & Sure, Y. (2007). "Web-based ontology engineering for the semantic web"
- Cimiano, C., & Völker, J. (2005). "Text2Onto: A framework for ontology learning and data-driven ontology acquisition"

**Constraint-Based Validation**:
- Knublauch, H., & Kontokostas, D. (2017). "Shapes Constraint Language (SHACL)"
- Kontokostas, D., & Westphal, P. (2014). "DBpedia quality assessment via constraint validation"

---

## 10. Appendix: Configuration & Defaults

```python
ontology_extension_config = {
    # Gap Analysis
    "min_entity_frequency": 3,         # Min appearances to consider
    "semantic_similarity_threshold": 0.65,  # For grouping candidates
    
    # LLM Definition Generation
    "llm_model": "qwen3:8b",
    "llm_temperature": 0.5,            # Lower = more deterministic
    "definition_max_tokens": 200,
    
    # SHACL Constraints
    "enable_cardinality_constraints": True,
    "enable_datatype_constraints": True,
    
    # Versioning
    "max_staging_versions": 5,
    "auto_snapshot_interval": "weekly",
    
    # Review Workflow
    "require_min_expert_agreement": 0.75,
    "min_reviewers_per_class": 1,
    
    # Evaluation
    "cq_answerability_target": 0.8,
    "entity_coverage_target": 0.8,
}
```

---

**End of Specification**

Questions? Contact: [Domain Expert], [Systems Engineer]  
Last Updated: 2026-02-09  
Version: 1.0 (Specification Draft)
