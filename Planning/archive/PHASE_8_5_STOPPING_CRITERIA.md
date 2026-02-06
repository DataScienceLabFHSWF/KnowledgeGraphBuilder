# Phase 8.5: Build Pipeline with Stopping Criteria

**Objective**: Integrate validation into the KG building pipeline and implement intelligent stopping criteria based on quality metrics and competency question answering.

**Date**: February 3, 2026  
**Status**: Complete (Phase 8.5)  

---

## 1. Overview

### Purpose

This feature adds orchestration and stopping criteria to the KG building pipeline:

1. **Pipeline Orchestration**: Coordinates extraction → assembly → validation → CQ checking
2. **Stopping Criteria**: Intelligently stops building when quality gates are met
3. **Iterative Improvement**: Enables multi-pass extraction with automatic stopping
4. **Quality Assurance**: Ensures final KG meets minimum standards before completion

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    BUILD PIPELINE                              │
│                                                                 │
│  Input: Documents + Ontology + Competency Questions            │
│     ↓                                                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Iteration Loop (max 10)                                  │  │
│  │                                                          │  │
│  │ 1. EXTRACT ENTITIES & RELATIONS                         │  │
│  │    ↓                                                    │  │
│  │ 2. ASSEMBLE TO KG                                       │  │
│  │    ↓                                                    │  │
│  │ 3. VALIDATE (SHACL + Rules + Consistency)              │  │
│  │    ↓                                                    │  │
│  │ 4. CHECK COMPETENCY QUESTIONS                          │  │
│  │    ↓                                                    │  │
│  │ 5. EVALUATE STOPPING CRITERIA                          │  │
│  │    ├─ All quality gates met? → STOP ✓                 │  │
│  │    ├─ Max iterations reached? → STOP (forced)         │  │
│  │    └─ Otherwise → ITERATE                             │  │
│  │                                                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│     ↓                                                            │
│  Output: Complete KG + Validation Report + Stopping Reason      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Key Components

### 2.1 StoppingCriteria Configuration

Defines minimum quality thresholds:

```python
@dataclass
class StoppingCriteria:
    min_cq_coverage: float = 0.95        # 95% of CQs answerable
    min_validation_pass_rate: float = 0.90  # 90% validation pass rate
    min_avg_confidence: float = 0.75    # Avg confidence >= 0.75
    min_entity_count: int = 100         # At least 100 entities
    max_iterations: int = 10            # Max 10 extraction rounds
    require_all: bool = True            # ALL criteria must be met
```

### 2.2 KGBuildState Tracking

Maintains current KG state across iterations:

```python
@dataclass
class KGBuildState:
    entity_count: int              # Current # entities
    edge_count: int                # Current # relations
    avg_confidence: float          # Average confidence score
    iteration_count: int           # Current iteration number
    total_violations: int          # Validation violations
    total_conflicts: int           # Detected conflicts
```

### 2.3 StoppingCriterionChecker

Evaluates if pipeline should stop:

```python
checker = StoppingCriterionChecker(criteria)
should_stop, reason, details = checker.check(
    kg_state, cq_results, validation_results
)
```

Returns:
- `should_stop`: Boolean (True = stop pipeline)
- `reason`: StoppingReason enum (why it stopped)
- `details`: Dict with detailed check results

### 2.4 BuildPipeline Orchestrator

Coordinates the complete pipeline:

```python
pipeline = BuildPipeline(
    config=BuildPipelineConfig(
        enable_validation=True,
        enable_cq_checking=True,
        stopping_criteria=StoppingCriteria(min_cq_coverage=0.95)
    )
)

result = pipeline.run(
    documents=docs,
    competency_questions=cqs
)

print(result.stopping_reason)  # Why it stopped
print(result.total_iterations)  # How many iterations
print(result.cq_summary.coverage_percentage)  # CQ coverage %
```

---

## 3. Usage Examples

### Example 1: Basic Usage with Default Criteria

```python
from kgbuilder.pipeline import (
    BuildPipeline, BuildPipelineConfig, StoppingCriteria
)

# Create pipeline with default criteria
pipeline = BuildPipeline(BuildPipelineConfig())

result = pipeline.run(
    documents=my_documents,
    competency_questions=my_cqs
)

print(result.get_summary_string())
# Output:
# Build Pipeline Result: ✓ SUCCESS
# Stopping Reason: cq_coverage_met
# Iterations: 3
# Final Entity Count: 156
# Final Edge Count: 203
# Average Confidence: 0.87
# CQ Coverage: 95.3% (20/21)
# Validation Pass Rate: 92.1% (210/228)
# Duration: 45.2s
```

### Example 2: Custom Stopping Criteria

```python
# Define custom criteria
criteria = StoppingCriteria(
    min_cq_coverage=0.90,           # 90% CQs must be answerable
    min_validation_pass_rate=0.85,  # 85% validation must pass
    min_avg_confidence=0.80,        # Avg confidence >= 0.80
    min_entity_count=200,           # At least 200 entities
    max_iterations=5,               # Max 5 iterations
    require_all=True                # ALL criteria must be met
)

# Create pipeline with custom criteria
config = BuildPipelineConfig(
    stopping_criteria=criteria,
    validate_at_each_iteration=True
)
pipeline = BuildPipeline(config)

result = pipeline.run(documents=docs, competency_questions=cqs)
```

### Example 3: Checking Stopping Criteria Results

```python
result = pipeline.run(documents=docs, competency_questions=cqs)

# Check why it stopped
print(f"Stopped because: {result.stopping_reason.value}")

# Access detailed CQ results
if result.cq_summary:
    print(f"CQ Coverage: {result.cq_summary.coverage_percentage:.1f}%")
    print(f"Unanswerable: {result.cq_summary.unanswerable}")

# Access detailed validation results
if result.validation_summary:
    print(f"Validation Pass Rate: {result.validation_summary.pass_rate:.1f}%")
    print(f"Violations: {result.validation_summary.violations}")
    print(f"Conflicts: {result.validation_summary.conflicts}")

# Check each iteration
for iteration in result.iterations:
    print(f"\nIteration {iteration.iteration_num}:")
    print(f"  Entities: {iteration.entities_extracted}")
    print(f"  Relations: {iteration.relations_extracted}")
    print(f"  Duration: {iteration.duration_ms:.0f}ms")
```

### Example 4: Viewing Checker Summary

```python
# Get detailed criteria check results
print(pipeline.get_checker_summary())

# Output:
# Stopping Criteria Check Summary:
#   Require All: True
#
#   entity_count: ✓ PASS
#     Current: 156 | Required: 100
#   avg_confidence: ✓ PASS
#     Current: 0.87 | Required: 0.75
#   cq_coverage: ✓ PASS
#     Current: 0.953 | Current_percentage: 95.3
#     Answerable: 20 | Total: 21
#   validation_pass_rate: ✓ PASS
#     Current: 0.921 | Current_percentage: 92.1
#     Passed: 210 | Total: 228
```

---

## 4. StoppingReason Enum

Possible stopping reasons:

| Reason | Meaning |
|--------|---------|
| `NOT_STOPPED` | Pipeline still running |
| `CQ_COVERAGE_MET` | All CQs answerable (or coverage threshold met) |
| `VALIDATION_PASS_RATE_MET` | Validation quality threshold met |
| `CONFIDENCE_THRESHOLD_MET` | Average confidence threshold met |
| `ENTITY_COUNT_REACHED` | Minimum entity count reached |
| `MAX_ITERATIONS_REACHED` | Hit max iteration limit |
| `QUALITY_GATES_PASSED` | All quality gates passed |
| `MANUAL_STOP` | User manually stopped |
| `ERROR_STOPPING` | Error forced stop |

---

## 5. Integration with Existing Components

### 5.1 Validation Integration

The pipeline calls validation during each iteration:

```
Extraction → Validation (SHACL + Rules + Consistency)
                  ↓
          CompetencyQuestionValidator
                  ↓
          StoppingCriterionChecker
```

### 5.2 CQ Integration

Calls CompetencyQuestionValidator to check answerability:

```python
# Pipeline calls this internally
cq_validator = CompetencyQuestionValidator(cqs)
cq_result = cq_validator.validate(kg_store)
```

### 5.3 KG Assembly Integration

Receives extracted entities/relations and assembles to KG:

```python
# Pipeline orchestrates assembly
kg_builder = KGBuilder(config)
kg_builder.build(entities, relations)
```

---

## 6. Configuration Patterns

### Pattern 1: Strict Quality Gates (Default)

All criteria must be met to stop:

```python
StoppingCriteria(
    min_cq_coverage=0.95,
    min_validation_pass_rate=0.90,
    min_avg_confidence=0.75,
    require_all=True  # ← ALL must pass
)
```

### Pattern 2: Fast Build (Any criterion)

Stop as soon as any quality gate passes:

```python
StoppingCriteria(
    min_cq_coverage=0.80,
    require_all=False  # ← ANY can trigger stop
)
```

### Pattern 3: High Confidence Build

Prioritize confidence over coverage:

```python
StoppingCriteria(
    min_avg_confidence=0.85,  # High confidence
    min_cq_coverage=0.80,     # Lower CQ bar
    min_validation_pass_rate=0.85
)
```

### Pattern 4: Complete Build

Ensure comprehensive coverage:

```python
StoppingCriteria(
    min_cq_coverage=0.98,      # Nearly all CQs
    min_entity_count=500,      # Many entities
    min_avg_confidence=0.80,
    max_iterations=15          # Allow more iterations
)
```

---

## 7. Metrics Tracked

### Per Iteration

- Entities extracted
- Relations extracted
- Validation violations
- CQs answered (new)
- Pass rate improvement
- Iteration duration

### Overall

- Total iterations
- Final entity count
- Final edge count
- Average confidence
- CQ coverage %
- Validation pass rate %
- Total pipeline duration
- Stopping reason

---

## 8. Implementation Details

### Criterion Evaluation Logic

```python
def should_stop(criteria, checks):
    if criteria.require_all:
        # ALL criteria must pass
        return all(check['passed'] for check in checks.values())
    else:
        # ANY criteria can pass
        return any(check['passed'] for check in checks.values())
```

### Early Exit

The pipeline exits early if:
1. Max iterations reached (hard stop)
2. All stopping criteria met (quality stop)
3. Error encountered (error stop)

---

## 9. Data Models

### StoppingCriteria

```python
@dataclass
class StoppingCriteria:
    min_cq_coverage: float = 0.95
    min_validation_pass_rate: float = 0.90
    min_avg_confidence: float = 0.75
    min_entity_count: int = 100
    max_iterations: int = 10
    require_all: bool = True
```

### BuildPipelineResult

```python
@dataclass
class BuildPipelineResult:
    success: bool
    stopping_reason: StoppingReason
    total_iterations: int
    final_kg_state: KGBuildState
    iterations: list[IterationResult]
    validation_summary: Optional[ValidationResults]
    cq_summary: Optional[CompetencyQuestionResults]
    total_duration_ms: float
    errors: list[str]
```

---

## 10. Future Enhancements

1. **Weighted Criteria**: Different weights for different criteria
2. **Dynamic Thresholds**: Adjust criteria based on progress
3. **Convergence Detection**: Detect when progress plateaus
4. **Parallel Extraction**: Run multiple extraction models in parallel
5. **Adaptive Iteration**: Adjust iteration count based on convergence
6. **Cost Tracking**: Monitor LLM API costs and stop when budget exceeded
7. **Experiment Tracking**: Log all runs for analysis
8. **A/B Testing**: Compare different stopping criteria

---

## 11. Testing

### Unit Tests

- `test_stopping_criteria_validation()` - Verify config validation
- `test_criterion_checker_all_pass()` - Test all criteria passing
- `test_criterion_checker_some_fail()` - Test mixed results
- `test_kg_build_state_tracking()` - Test state updates
- `test_cq_results_calculation()` - Test CQ metrics

### Integration Tests

- `test_pipeline_basic_execution()` - Basic pipeline run
- `test_pipeline_early_exit()` - Test early stopping
- `test_pipeline_max_iterations()` - Test max iteration limit
- `test_pipeline_with_validation()` - Test validation integration
- `test_pipeline_with_cq_checking()` - Test CQ integration

---

## 12. Files Created/Modified

### New Files

- `src/kgbuilder/pipeline/stopping_criterion.py` - Stopping logic (1000+ LOC)
- `src/kgbuilder/pipeline/orchestrator.py` - Pipeline orchestration (850+ LOC)

### Modified Files

- `src/kgbuilder/pipeline/__init__.py` - Updated exports

### Total LOC Added

- **1,850+ lines** of new functionality

---

## 13. Usage in CLI

```bash
# Run pipeline with default criteria
python -m kgbuilder.cli build \
    --documents data/documents \
    --ontology data/ontology.owl \
    --cq data/competency_questions.json

# Run with custom criteria
python -m kgbuilder.cli build \
    --documents data/documents \
    --min-cq-coverage 0.90 \
    --min-validation-rate 0.85 \
    --max-iterations 5
```

---

## 14. Monitoring & Logging

All pipeline operations are logged with structlog:

```python
# Example logs
"pipeline_run_started" - Pipeline started
"pipeline_iteration_started" - Iteration beginning
"extraction_step" - Extraction completed
"validation_step" - Validation completed  
"cq_checking_step" - CQ checking completed
"stopping_criteria_met" - Criteria evaluation result
"pipeline_completed" - Pipeline finished
```

---

## Summary

**Phase 8.5** adds intelligent pipeline orchestration and stopping criteria to the KG building process, enabling:

✅ Automatic stopping when quality gates are met  
✅ Iterative improvement with validation feedback  
✅ Competency question-driven building  
✅ Flexible criteria configuration  
✅ Detailed metrics tracking and reporting  
✅ Integration with existing validation pipeline  

This completes the core KG building pipeline functionality.
