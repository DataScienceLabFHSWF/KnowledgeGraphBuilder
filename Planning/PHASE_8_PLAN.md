# Phase 8: Validation Pipeline

**Objective**: Build a comprehensive validation pipeline to ensure Knowledge Graph quality using SHACL shapes, domain rules, and consistency constraints.

**Timeline**: ~16 hours (est. 2-3 days intensive)  
**Date**: February 3, 2026  
**Status**: Planning  

---

## 1. Overview

### Purpose

Phase 8 implements data quality assurance for the Knowledge Graph by:

1. **SHACL Validation**: Shape-based constraint validation using SHACL shapes
2. **Domain Rules**: Semantic rules that enforce ontology semantics
3. **Consistency Checking**: Detect contradictions and conflicts between related facts
4. **Quality Reporting**: Generate detailed validation reports with pass/fail metrics

### Why This Matters

- **Data Quality**: Ensure only high-quality entities/relations enter the KG
- **Ontology Compliance**: Validate that extracted facts conform to OWL constraints
- **Conflict Detection**: Find contradictions that need manual review
- **Audit Trail**: Generate reports for stakeholders showing data quality

### Architecture Pattern

```
KGBuilder Output
      ↓
┌─────────────────────────────────────────────────────┐
│           Validation Pipeline                       │
│  ┌─────────────────────────────────────────────┐   │
│  │ 1. SHACL Validator                          │   │
│  │    - Shape compliance                       │   │
│  │    - Type validation                        │   │
│  │    - Cardinality constraints                │   │
│  └─────────────────────────────────────────────┘   │
│                      ↓                              │
│  ┌─────────────────────────────────────────────┐   │
│  │ 2. Domain Rules Engine                      │   │
│  │    - Ontology rules (inverse, transitivity) │   │
│  │    - Custom semantic rules                  │   │
│  │    - Business logic constraints             │   │
│  └─────────────────────────────────────────────┘   │
│                      ↓                              │
│  ┌─────────────────────────────────────────────┐   │
│  │ 3. Consistency Checker                      │   │
│  │    - Duplicate detection                    │   │
│  │    - Conflict identification                │   │
│  │    - Transitive contradiction detection     │   │
│  └─────────────────────────────────────────────┘   │
│                      ↓                              │
│  ┌─────────────────────────────────────────────┐   │
│  │ 4. Report Generation                        │   │
│  │    - Pass/fail metrics                      │   │
│  │    - Detailed violation list                │   │
│  │    - Recommendations                        │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
      ↓
Valid KG + Detailed Report
```

---

## 2. Task Breakdown

### Task 8.1: SHACL Shape Validator (3-4 hours)

**Goal**: Implement SHACL-based validation for graph structure and types.

**Deliverables**:
- `src/kgbuilder/validation/shacl_validator.py` - SHACL validator class
- Validation against ontology shapes
- Type and cardinality constraint checking
- Test coverage: 70%+

**Technical Details**:

```python
class SHACLValidator:
    """Validate RDF graphs against SHACL shapes."""
    
    def validate_graph(self, graph: rdflib.Graph, shapes_graph: rdflib.Graph) -> ValidationResult
    def validate_node(self, node_id: str, shape: SHACLShape) -> NodeValidationResult
    def validate_edge(self, edge_id: str, shape: SHACLShape) -> EdgeValidationResult
```

**Key Validations**:
- Node types match ontology classes
- Required properties present
- Property values match expected types (string, int, float, etc.)
- Cardinality constraints (min/max occurrences)
- Reference integrity (edges point to valid nodes)

**Data Models**:
```python
@dataclass
class ValidationViolation:
    severity: str  # "error" | "warning" | "info"
    path: str      # Property/field path
    message: str   # Violation description
    value: Any     # Actual value
    expected: str  # Expected constraint

@dataclass
class ValidationResult:
    valid: bool
    violations: list[ValidationViolation]
    node_count: int
    edge_count: int
    pass_rate: float  # % of constraints passed
```

### Task 8.2: Domain Rules Engine (3-4 hours)

**Goal**: Implement rule-based validation for ontology semantics.

**Deliverables**:
- `src/kgbuilder/validation/rules_engine.py` - Rule execution engine
- Built-in rules for common ontology patterns
- Custom rule support
- Test coverage: 70%+

**Technical Details**:

```python
class RulesEngine:
    """Execute semantic rules for validation."""
    
    def add_rule(self, rule: SemanticRule) -> None
    def execute_rules(self, graph: KG) -> list[RuleViolation]
    def evaluate_rule(self, rule: SemanticRule) -> bool
```

**Built-in Rules**:
1. **Inverse Property Rules**: If `rel(A,B)` exists and rel has inverse, then `inv_rel(B,A)` should exist
2. **Transitive Rules**: If `rel(A,B)` and `rel(B,C)` exist and rel is transitive, then `rel(A,C)` should exist
3. **Domain/Range**: Properties only connect nodes of compatible types
4. **Uniqueness**: Functional properties appear at most once per subject
5. **Cardinality**: Properties respect min/max cardinality constraints

**Data Models**:
```python
@dataclass
class SemanticRule:
    name: str
    description: str
    rule_type: str  # "inverse" | "transitive" | "domain_range" | "custom"
    subject_type: str
    relation: str
    object_type: str
    expected_inverse: str | None = None

@dataclass
class RuleViolation:
    rule: SemanticRule
    subject_id: str
    relation: str
    object_id: str
    reason: str
    recommendation: str
```

### Task 8.3: Consistency Checker (3-4 hours)

**Goal**: Detect contradictions and conflicts in the knowledge graph.

**Deliverables**:
- `src/kgbuilder/validation/consistency_checker.py` - Conflict detector
- Duplicate entity detection
- Conflicting property values
- Test coverage: 70%+

**Technical Details**:

```python
class ConsistencyChecker:
    """Detect contradictions and conflicts."""
    
    def check_consistency(self, graph: KG) -> ConsistencyReport
    def find_conflicts(self, entity_id: str) -> list[Conflict]
    def find_duplicates(self, threshold: float = 0.9) -> list[DuplicateSet]
```

**Conflict Types**:
1. **Type Conflicts**: Node labeled with incompatible types
2. **Value Conflicts**: Same property with multiple conflicting values
3. **Transitive Conflicts**: `rel(A,B)` and `rel(B,C)` but NOT `rel(A,C)` when transitive
4. **Cardinality Conflicts**: Functional property with multiple values
5. **Domain/Range Violations**: Property violating domain/range constraints

**Data Models**:
```python
@dataclass
class Conflict:
    entity_id: str
    conflict_type: str  # "type" | "value" | "transitive" | "cardinality" | "domain"
    description: str
    involved_facts: list[tuple[str, str, str]]  # (subject, predicate, object)
    severity: str  # "critical" | "warning" | "info"

@dataclass
class ConsistencyReport:
    conflicts: list[Conflict]
    duplicates: list[DuplicateSet]
    conflict_count: int
    conflict_rate: float  # % of entities with conflicts
    recommendations: list[str]
```

### Task 8.4: Report Generation (2-3 hours)

**Goal**: Create comprehensive validation reports in multiple formats.

**Deliverables**:
- `src/kgbuilder/validation/reporter.py` - Report generation
- Report formats: Markdown, JSON, HTML
- Summary metrics and detailed findings
- Test coverage: 70%+

**Technical Details**:

```python
class ValidationReporter:
    """Generate validation reports."""
    
    def generate_report(self, validation_result: ValidationResult) -> str
    def generate_html_report(self, result: ValidationResult) -> str
    def export_violations(self, violations: list, format: str) -> str
```

**Report Contents**:
1. **Executive Summary**
   - Overall pass rate
   - Total violations
   - Severity breakdown

2. **Detailed Findings**
   - SHACL violations (grouped by shape)
   - Rule violations (grouped by rule)
   - Conflicts detected

3. **Metrics**
   - Node coverage
   - Edge coverage
   - Type distribution
   - Property completeness

4. **Recommendations**
   - Auto-fixable issues
   - Manual review items
   - Quality improvement suggestions

### Task 8.5: Integration & Testing (2-3 hours)

**Goal**: Integrate validation into build pipeline and create comprehensive tests.

**Deliverables**:
- Integrate ValidationPipeline into build_kg.py
- Unit tests for each validator component
- Integration tests with sample KGs
- Test coverage: 80%+

**Integration Points**:
```python
# In scripts/build_kg.py
result = builder.build(entities=entities, relations=relations)

# Run validation
validator = ValidationPipeline(builder.primary_store, ontology)
validation_result = validator.validate()

# Generate report
report = validator.generate_report(validation_result)
print(f"Validation: {validation_result.pass_rate*100:.1f}% pass rate")
```

---

## 3. Files to Create/Modify

### New Files

| File | Purpose | LOC (est.) |
|------|---------|-----------|
| `src/kgbuilder/validation/__init__.py` | Module exports | 20 |
| `src/kgbuilder/validation/shacl_validator.py` | SHACL validation | 300 |
| `src/kgbuilder/validation/rules_engine.py` | Domain rules | 250 |
| `src/kgbuilder/validation/consistency_checker.py` | Conflict detection | 280 |
| `src/kgbuilder/validation/reporter.py` | Report generation | 350 |
| `tests/test_validation.py` | Unit + integration tests | 600 |
| `tests/test_shacl.py` | SHACL validator tests | 250 |

**Total New Code**: ~2,050 LOC

### Modified Files

| File | Change |
|------|--------|
| `scripts/build_kg.py` | Add ValidationPipeline integration |
| `src/kgbuilder/assembly/kg_builder.py` | Add validation hooks |

---

## 4. Dependencies & Tools

### New Dependencies

```toml
pyshacl = "^0.26"          # SHACL shape validation
rdflib = "^7.0"            # RDF graph manipulation
jinja2 = "^3.1"            # HTML report templates
```

### Existing Dependencies Used

- `structlog` - Logging
- `pydantic` - Data validation
- `numpy` - Metrics calculation

---

## 5. Testing Strategy

### Unit Tests (60% of test time)

```python
def test_shacl_validator_type_constraint()
def test_shacl_validator_cardinality_constraint()
def test_rules_engine_transitive_rule()
def test_rules_engine_inverse_rule()
def test_consistency_checker_duplicate_detection()
def test_consistency_checker_conflict_detection()
def test_reporter_markdown_generation()
def test_reporter_json_generation()
```

### Integration Tests (40% of test time)

```python
def test_validation_pipeline_complete_workflow()
def test_validation_with_real_kg()
def test_validation_with_sample_documents()
def test_report_generation_with_violations()
```

### Validation Fixtures

- Sample ontology with SHACL shapes
- Sample KG with intentional violations
- Sample rules library

---

## 6. Acceptance Criteria

✅ **Must Have**:
- [ ] SHACL validator validates type constraints
- [ ] SHACL validator validates cardinality constraints
- [ ] Domain rules engine executes semantic rules
- [ ] Consistency checker detects duplicates
- [ ] Consistency checker detects conflicts
- [ ] Reports generated in Markdown and JSON
- [ ] All tests passing (36+ tests)
- [ ] 70%+ code coverage

✅ **Should Have**:
- [ ] HTML report generation
- [ ] Custom rule support
- [ ] Performance metrics (<1s for 10k nodes)
- [ ] Integration with build_kg.py

✅ **Could Have**:
- [ ] Auto-repair of common violations
- [ ] Machine learning-based quality score
- [ ] Interactive validation UI
- [ ] Incremental validation

---

## 7. Success Metrics

| Metric | Target |
|--------|--------|
| Code Coverage | 75%+ |
| Tests Passing | 100% |
| Documentation | Complete |
| Performance | <1s for 10k nodes |
| False Positive Rate | <5% |

---

## 8. Risk & Mitigation

| Risk | Mitigation |
|------|-----------|
| SHACL complexity | Start with simple shapes, extend iteratively |
| Performance on large graphs | Implement batch validation, add caching |
| Rule conflicts | Implement conflict resolution strategy |
| Report formatting | Use templates for consistency |

---

## 9. Related Files & References

- [MASTER_PLAN.md](MASTER_PLAN.md) - Overall roadmap
- [PHASE_7_PLAN.md](PHASE_7_PLAN.md) - Multi-store implementation
- [INTERFACES.md](INTERFACES.md) - Protocol specifications
- Ontology: `data/ontology/` - SHACL shapes

---

## 10. Next Phase (Phase 9)

Phase 9 will implement **Analytics & Evaluation**:
- Metrics collection (precision, recall, F1)
- Benchmark datasets
- Performance profiling
- Comparison reports
