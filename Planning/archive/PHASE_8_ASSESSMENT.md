# Phase 8 Assessment: Validation Pipeline

**Date**: February 3, 2026  
**Status**: Pre-Implementation Assessment  
**Estimated Duration**: 16 hours  

---

## 1. Existing Infrastructure Assessment

### Available Components

#### From Phase 7: Storage Layer
- ✅ GraphStore protocol (unified interface)
- ✅ Neo4jGraphStore (query capability)
- ✅ RDFGraphStore (SPARQL capability)
- ✅ GraphStatistics (metrics)

#### From Phase 6: KG Content
- ✅ Node/Edge dataclasses with metadata
- ✅ Entity confidence scoring
- ✅ Evidence tracking

#### From Phase 5: Quality Signals
- ✅ ConfidenceAnalyzer (statistical analysis)
- ✅ ConfidenceCalibraror (isotonic regression)
- ✅ EntityQualityFilter (pre-filtering)

#### From Ontology Layer
- ✅ Ontology classes and properties
- ✅ Domain/range constraints
- ✅ Cardinality information
- ⚠️ SHACL shapes (needs creation/import)

### Dependencies Analysis

**Already Available**:
- `rdflib` - Used in RDFGraphStore
- `structlog` - Logging throughout
- `pydantic` - Data models
- `dataclasses` - Core data structures

**Need to Add**:
- `pyshacl` - SHACL validation engine
- `jinja2` - HTML templating (optional)

**Import Strategy**:
```toml
[tool.poetry.dependencies]
pyshacl = "^0.26"  # Latest SHACL support
jinja2 = "^3.1"    # Optional, for HTML reports
```

---

## 2. Design Patterns & Reusable Code

### Pattern 1: Protocol-Based Design (from Phase 7)

```python
@runtime_checkable
class Validator(Protocol):
    """Unified validator interface."""
    def validate(self, kg: KG) -> ValidationResult:
        """Validate knowledge graph."""
        ...
```

**Benefits**:
- Can implement multiple validators (SHACL, rules, consistency)
- Easy to add new validators
- Testable with mocks

### Pattern 2: Chain of Responsibility

```
Input KG
   ↓
SHACLValidator → RulesEngine → ConsistencyChecker → Reporter
   ↓              ↓               ↓                     ↓
Step 1           Step 2           Step 3              Final Report
```

**Benefits**:
- Each validator independent
- Can skip/configure steps
- Easy to extend

### Pattern 3: Data Class Hierarchies (from Phase 5)

```python
@dataclass
class ValidationViolation:
    """Base violation type."""
    severity: str
    path: str
    message: str

@dataclass
class SHACLViolation(ValidationViolation):
    """SHACL-specific violation."""
    shape_uri: str
    focus_node: str
```

**Benefits**:
- Type-safe violations
- Extensible for specific validators
- Serializable to JSON

---

## 3. Reusable Implementation Patterns

### From Phase 7: Error Handling

```python
# Pattern we'll reuse
try:
    result = validator.validate(kg)
except ValidationException as e:
    logger.error("validation_failed", error=str(e))
    result = ValidationResult(valid=False, violations=[...])
```

### From Phase 5: Metrics Aggregation

```python
# Pattern for calculating pass rates
violations_by_type = {}
for violation in violations:
    violations_by_type[violation.severity] = \
        violations_by_type.get(violation.severity, 0) + 1

pass_rate = 1.0 - (len(violations) / total_constraints)
```

### From Phase 6: Batch Processing

```python
# We'll batch validate nodes/edges like edge creation
def _batch_validate_nodes(self, nodes: list[Node], batch_size: int):
    for i in range(0, len(nodes), batch_size):
        batch = nodes[i:i+batch_size]
        # Validate batch
```

---

## 4. Expected Challenges & Solutions

### Challenge 1: SHACL Complexity

**Problem**: SHACL has steep learning curve, many features

**Solution**:
- Start with simple shapes (type, cardinality)
- Build shape library from ontology
- Provide helper functions for common patterns
- Generate SHACL from ontology programmatically

**Example**:
```python
# Helper to generate cardinality shape
def create_cardinality_shape(property_uri: str, min: int, max: int):
    # Generate SHACL shape for cardinality constraint
    ...
```

### Challenge 2: Performance on Large Graphs

**Problem**: Validating 10k nodes might be slow

**Solution**:
- Batch validation (1000 nodes at a time)
- Parallel validation where possible
- Caching of shape compilation
- Optional sampling for initial feedback

**Metrics**:
- <100ms for 1000 nodes (target)
- <1s for 10k nodes (target)

### Challenge 3: Rule Conflicts

**Problem**: Multiple rules might conflict (e.g., cardinality vs. optional)

**Solution**:
- Clear rule priority ordering
- Explicit conflict handling in rules
- Document assumptions
- Provide rule composition utilities

### Challenge 4: Test Data Creation

**Problem**: Need valid + invalid KGs for testing

**Solution**:
- Use existing Phase 7 test fixtures
- Generate programmatically:
  ```python
  @pytest.fixture
  def kg_with_type_violations():
      kg = create_sample_kg()
      # Add a node with wrong type
      kg.add_node(Node(..., node_type="InvalidType"))
      return kg
  ```

---

## 5. Implementation Approach

### Phase 8.1: SHACL Validator (Suggested Implementation)

**Step 1** (30 min): Set up pyshacl integration
```python
from pyshacl import validate

def validate_with_shacl(data_graph, shapes_graph):
    conforms, results_graph, results_text = validate(...)
    # Parse results into our ValidationResult
```

**Step 2** (90 min): Implement SHACLValidator class
```python
class SHACLValidator:
    def __init__(self, shapes_graph: rdflib.Graph):
        self.shapes_graph = shapes_graph
    
    def validate(self, data_graph: rdflib.Graph):
        # Use pyshacl.validate
        # Parse violations
        # Return ValidationResult
```

**Step 3** (60 min): Create shape library
```python
# Load/generate SHACL shapes from ontology
# Support for Node shapes, property shapes
# Type, cardinality, range constraints
```

### Phase 8.2: Rules Engine (Suggested Implementation)

**Key insight**: Rules are just functions that check graph state

```python
# Pattern: a rule is a callable
def check_inverse_property(kg, relation: str, inverse: str):
    violations = []
    for edge in kg.get_edges_by_type(relation):
        if not kg.has_edge(edge.target_id, edge.source_id, inverse):
            violations.append(RuleViolation(...))
    return violations

# Rules engine executes these
class RulesEngine:
    def execute_rules(self, kg, rules):
        all_violations = []
        for rule in rules:
            all_violations.extend(rule(kg))
        return all_violations
```

### Phase 8.3: Consistency Checker (Suggested Implementation)

**Duplicate Detection**: Use embeddings + similarity
```python
def find_duplicates(self, kg, threshold=0.9):
    # Get entity embeddings (from Phase 2)
    # Compute similarity matrix
    # Find clusters above threshold
```

**Conflict Detection**: Check for contradictory properties
```python
def find_value_conflicts(self, kg):
    violations = []
    for entity in kg.nodes:
        # Check for conflicting property values
        # Check for type conflicts
        # Check for cardinality violations
    return violations
```

---

## 6. Testing Strategy Detail

### Unit Test Examples

```python
# tests/test_validation.py

def test_shacl_validator_catches_type_mismatch():
    """SHACL should catch when node type doesn't match shape."""
    kg = KG()
    kg.add_node(Node("n1", "Test", node_type="Person"))
    
    shape = """
    ex:PersonShape a sh:NodeShape ;
        sh:targetClass ex:Person ;
        sh:property [
            sh:path ex:age ;
            sh:datatype xsd:integer ;
        ] .
    """
    
    result = validator.validate(kg)
    assert not result.valid
    assert any(v.path == "age" for v in result.violations)

def test_rules_engine_detects_missing_inverse():
    """Rules should detect when inverse relation is missing."""
    kg = KG()
    kg.add_edge(Edge(..., edge_type="knows", ...))
    
    rules = [create_inverse_rule("knows", "knows")]
    violations = engine.execute_rules(kg, rules)
    
    assert len(violations) > 0
    assert violations[0].rule.name == "knows-inverse"

def test_consistency_checker_finds_duplicates():
    """Should detect likely duplicate entities."""
    kg = KG()
    kg.add_node(Node("n1", "Albert Einstein", node_type="Person", ...))
    kg.add_node(Node("n2", "Albert Einsteinn", node_type="Person", ...))  # Typo
    
    duplicates = checker.find_duplicates(kg, threshold=0.85)
    
    assert len(duplicates) > 0
    assert {"n1", "n2"} in [set(d.entities) for d in duplicates]
```

### Integration Tests

```python
def test_validation_pipeline_complete():
    """End-to-end validation workflow."""
    # Build KG
    kg = build_sample_kg()
    
    # Run validation
    validator = ValidationPipeline(kg, ontology)
    result = validator.validate()
    
    # Check report
    assert hasattr(result, "violations")
    assert hasattr(result, "conflicts")
    assert hasattr(result, "pass_rate")
    assert 0.0 <= result.pass_rate <= 1.0
```

---

## 7. File Structure Plan

```
src/kgbuilder/validation/
├── __init__.py
│   ├── SHACLValidator
│   ├── RulesEngine
│   ├── ConsistencyChecker
│   ├── ValidationPipeline (orchestrator)
│   └── ValidationResult/ValidationViolation (models)
├── shacl_validator.py
│   └── SHACLValidator class (~300 LOC)
├── rules_engine.py
│   ├── RulesEngine class (~150 LOC)
│   └── Built-in rules (~100 LOC)
├── consistency_checker.py
│   └── ConsistencyChecker class (~280 LOC)
├── reporter.py
│   ├── ValidationReporter class (~250 LOC)
│   └── HTML/JSON templates (~100 LOC)
└── models.py
    ├── ValidationResult (~50 LOC)
    ├── ValidationViolation (~30 LOC)
    ├── RuleViolation (~30 LOC)
    └── Conflict (~30 LOC)

tests/
├── test_validation.py (~400 LOC integration tests)
├── test_shacl_validator.py (~250 LOC SHACL tests)
├── test_rules_engine.py (~200 LOC rule tests)
├── test_consistency_checker.py (~200 LOC conflict tests)
└── fixtures/
    ├── sample_ontology.rdf
    ├── sample_kg_valid.json
    ├── sample_kg_invalid.json
    └── sample_rules.json

scripts/
└── validate_kg.py (CLI utility for validation)
```

---

## 8. Estimated Time Breakdown

| Task | Hours | Notes |
|------|-------|-------|
| 8.1: SHACL Validator | 3.5 | Including shape library |
| 8.2: Rules Engine | 3.5 | Including built-in rules |
| 8.3: Consistency Checker | 3.5 | Duplicate + conflict detection |
| 8.4: Reporter | 2.5 | Markdown, JSON, HTML formats |
| 8.5: Integration & Tests | 3 | Full test coverage |
| **Total** | **16** | ~2 days intensive |

---

## 9. Success Criteria Checklist

### Code Quality
- [ ] All new code follows PEP 8 + project style
- [ ] Type hints on all functions
- [ ] Docstrings (Google style) on all public APIs
- [ ] 75%+ code coverage for validation modules

### Functionality
- [ ] SHACL validation working for type constraints
- [ ] SHACL validation working for cardinality constraints
- [ ] Rules engine executing semantic rules
- [ ] Duplicate detection working
- [ ] Conflict detection working
- [ ] Reports generated in Markdown/JSON

### Testing
- [ ] 40+ unit tests
- [ ] 5+ integration tests
- [ ] All tests passing
- [ ] Sample KGs with known violations

### Documentation
- [ ] API documentation complete
- [ ] Example usage in docstrings
- [ ] Phase 8 plan and assessment complete
- [ ] README updated with validation info

---

## 10. Go/No-Go Decision

### Go Criteria ✅
- [ ] Phase 7 fully merged and tested
- [ ] All Phase 7 tests passing
- [ ] MASTER_PLAN updated
- [ ] Dependencies available (pyshacl installable)
- [ ] Team ready to start

### Potential Blockers
- ⚠️ Ontology SHACL shapes not yet defined (create or auto-generate)
- ⚠️ Performance concerns (plan batch validation)
- ⚠️ Rule complexity (start simple, extend iteratively)

**Recommendation**: Proceed to Phase 8 with focus on MVP (SHACL + basic rules)

---

## 11. References

- [PHASE_7_PLAN.md](PHASE_7_PLAN.md) - Multi-store foundation
- [MASTER_PLAN.md](MASTER_PLAN.md) - Overall roadmap
- SHACL Specification: https://www.w3.org/TR/shacl/
- pyshacl Documentation: https://github.com/RDFLib/pySHACL
