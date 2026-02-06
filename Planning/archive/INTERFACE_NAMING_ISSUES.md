# Interface & Naming Issues Found - Phase 4 Implementation

## Summary
During Phase 4 implementation and testing, we encountered multiple naming/interface inconsistencies that led to errors and confusion. This document catalogs them to avoid repeating these mistakes.

---

## Issue Categories

### 1. **Dataclass Field Name Inconsistencies**

#### Issue 1.1: `properties` vs `attributes`
- **Location**: `SynthesizedEntity` dataclass vs code expecting `properties`
- **Details**:
  - `SynthesizedEntity` defines field: `attributes: dict[str, Any]`
  - But `FindingsSynthesizer._merge_group()` checked: `entity.properties`
  - **Error**: `AttributeError: 'SynthesizedEntity' object has no attribute 'properties'`
- **Fix Applied**: Line 230-237 in `src/kgbuilder/extraction/synthesizer.py`
  - Changed from checking `.properties` to checking `.attributes` and `.sources`
- **Prevention**: Always verify field names match between dataclass definition and usage

#### Issue 1.2: `sources` field presence
- **Location**: `ExtractedEntity` vs `SynthesizedEntity`
- **Details**:
  - `ExtractedEntity` (line 90-101 in core/models.py) does NOT have `sources` field
  - Test script tried to initialize: `ExtractedEntity(..., sources=["document_1"])`
  - **Error**: `TypeError: __init__() got an unexpected keyword argument 'sources'`
- **Fix**: Remove `sources` parameter; use only available fields
- **Note**: `SynthesizedEntity` DOES have `sources` field - different models!

---

### 2. **Method Signature Mismatches**

#### Issue 2.1: `QuestionGenerationAgent.generate_questions()` signature
- **Expected**: Takes `ontology_classes`, `existing_coverage` parameters
- **Actual**: Takes only `max_questions`, `covered_threshold`, `coverage_percentage_threshold`
- **Details**:
  - Agent automatically loads classes from `ontology_service` passed to constructor
  - Does NOT take classes as parameter to `generate_questions()`
  - **Error**: `TypeError: generate_questions() got an unexpected keyword argument 'ontology_classes'`
- **Correct Usage**:
  ```python
  agent = QuestionGenerationAgent(ontology_service=mock_ontology)
  questions = agent.generate_questions(max_questions=3)  # Classes loaded from service
  ```

#### Issue 2.2: `IterativeDiscoveryLoop.__init__()` constructor
- **Expected**: Takes `llm_provider`, `retriever`, `max_iterations`
- **Actual**: Takes `retriever`, `extractor`, `question_generator`
- **Details**:
  - Constructor injects dependencies as protocols, not individual services
  - Requires: `Retriever`, `EntityExtractor`, `QuestionGenerationAgent`
  - **Error**: `TypeError: __init__() got an unexpected keyword argument 'llm_provider'`
- **Lesson**: Always check constructor signature before attempting to instantiate

#### Issue 2.3: `SimpleKGAssembler.__init__()` missing required parameter
- **Expected**: `SimpleKGAssembler(neo4j_uri="...")` 
- **Actual**: Requires both `neo4j_uri` and `auth` tuple
- **Details**:
  - Must provide credentials: `auth=("username", "password")`
  - Attempts to connect immediately on init (line 69-72)
  - **Error**: `TypeError: __init__() missing 1 required positional argument: 'auth'`
- **Correct Usage**:
  ```python
  assembler = SimpleKGAssembler(
      neo4j_uri="bolt://localhost:7687",
      auth=("neo4j", "password")
  )
  ```

---

### 3. **Protocol/Interface Definition Issues**

#### Issue 3.1: `OntologyService` Protocol expectations
- **Location**: Line 22-81 in `src/kgbuilder/agents/question_generator.py`
- **Details**:
  - Defines 4 required methods:
    1. `get_all_classes() -> list[str]`
    2. `get_class_hierarchy(class_name: str) -> dict[str, Any]`
    3. `get_class_relations(class_name: str) -> dict[str, list[str]]`
    4. `get_class_properties(class_name: str) -> dict[str, Any]` (optional)
- **Common Mistake**: Forgetting to implement `get_class_relations()` in mocks
- **Prevention**: Always implement all required protocol methods in mocks

#### Issue 3.2: `Retriever` and `EntityExtractor` protocols for IterativeDiscoveryLoop
- **Details**: Not fully documented in code; required by constructor
- **Impact**: Can't instantiate `IterativeDiscoveryLoop` without knowing these protocols
- **Prevention**: Document protocol signatures in class docstring

---

### 4. **Model Field Type Inconsistencies**

#### Issue 4.1: ResearchQuestion return type
- **Location**: `QuestionGenerationAgent.generate_questions()` return type
- **Details**:
  - Returns `list[ResearchQuestion]` dataclass objects
  - But test script expected dict-like access: `q.get("question")`
  - **Error**: Iteration would work, but dict methods fail
  - **Fix**: Convert to dicts or use dataclass attribute access
- **Lesson**: Always check return types vs expected format

#### Issue 4.2: Sources field ownership
- **Location**: Different models have different ways to track sources
- **Details**:
  - `ExtractedEntity`: NO `sources` field
  - `SynthesizedEntity`: HAS `sources: list[str]` field
  - `ExtractedRelation`: HAS `sources: list[str]` field
  - Test tried to use `sources` on wrong model type
- **Prevention**: Keep a lookup table of which models have which fields

---

## Root Causes

### 1. **Incomplete Documentation**
- Constructor signatures not documented
- Required protocol methods not listed in docstrings
- Field differences between similar models not explained

### 2. **Naming Consistency**
- Using `properties` in one place, `attributes` in another
- Inconsistent plural/singular naming (`sources` vs similar patterns)

### 3. **Insufficient Type Hints in Tests**
- Generic `list[dict[str, Any]]` used instead of proper type hints
- Mocks created without proper Protocol typing

### 4. **Lack of Centralized Interface Registry**
- No single place documenting all dataclasses, their fields, and models that use them
- Protocol definitions scattered through codebase

---

## Recommended Practices Going Forward

### 1. **Create Interface Checklist Before Implementation**
```markdown
For each class/agent to implement:
- [ ] Constructor parameters documented with types
- [ ] Input types verified (dict vs dataclass)
- [ ] Output types verified (return values match usage)
- [ ] All protocol methods listed and implemented
- [ ] Field names consistent with existing models
```

### 2. **Centralize Model Definitions**
- Keep all dataclasses in `src/kgbuilder/core/models.py`
- Document field presence in each model
- Create a reference table: Model → Fields → Type

### 3. **Protocol Documentation Template**
```python
@runtime_checkable
class MyProtocol(Protocol):
    """Protocol for [service]."""
    
    def method_name(self, param: Type) -> ReturnType:
        """Description.
        
        Args:
            param: Description
            
        Returns:
            Description of return value
            
        Raises:
            ExceptionType: When this happens
        """
        ...
```

### 4. **Test/Mock Checklist**
- [ ] Mock implements all required protocol methods
- [ ] Mock return types match actual implementation
- [ ] Test data uses correct dataclass constructors
- [ ] Error messages are checked against actual exceptions

### 5. **Naming Rules**
- Use `sources: list[str]` consistently across all models that track origin
- Use `attributes: dict[str, Any]` or `properties: dict[str, Any]` - pick ONE and stick with it
- Document field differences between models explicitly

---

## Issues Summary by Phase 4 Component

### QuestionGenerationAgent (Phase 4a)
| Issue | Type | Severity | Status |
|-------|------|----------|--------|
| Constructor takes `ontology_service`, not separate params | Interface | High | ✅ Documented |
| `generate_questions()` doesn't take class list param | Signature | High | ✅ Documented |
| `OntologyService` protocol not fully documented | Documentation | Medium | ⏳ TODO |

### IterativeDiscoveryLoop (Phase 4b)
| Issue | Type | Severity | Status |
|-------|------|----------|--------|
| Constructor signature completely different | Interface | High | ✅ Documented |
| Requires `Retriever` and `EntityExtractor` protocols | Documentation | High | ⏳ TODO |
| `run_discovery()` parameter names mismatch test expectations | Signature | Medium | ✅ Documented |

### FindingsSynthesizer (Phase 4c)
| Issue | Type | Severity | Status |
|-------|------|----------|--------|
| `entity.properties` should be `entity.attributes` | Naming | High | ✅ Fixed |
| Floating point precision in confidence boost test | Testing | Low | ✅ Fixed |

### SimpleKGAssembler (Phase 4d)
| Issue | Type | Severity | Status |
|-------|------|----------|--------|
| `auth` parameter required but not documented | Documentation | High | ✅ Documented |
| Constructor attempts Neo4j connection immediately | Design | Medium | ✅ Documented |

---

## Model Field Reference

### ExtractedEntity
- id, label, entity_type, description
- aliases, properties, confidence, evidence
- ❌ NO `sources` field
- ❌ NO `attributes` field

### SynthesizedEntity  
- id, label, entity_type, description
- confidence, evidence, sources, merged_count
- ✅ HAS `sources` field
- ✅ HAS `attributes` field (not properties)

### ExtractedRelation
- id, source_id, target_id, predicate
- confidence, evidence, sources

---

## Action Items

- [ ] Add detailed docstrings to all protocol definitions
- [ ] Document constructor parameters in class docstrings
- [ ] Create `docs/MODELS_REFERENCE.md` listing all dataclasses and fields
- [ ] Update test templates to use proper typing
- [ ] Add validation methods to dataclasses to catch field errors early
- [ ] Create mock templates for common protocols
