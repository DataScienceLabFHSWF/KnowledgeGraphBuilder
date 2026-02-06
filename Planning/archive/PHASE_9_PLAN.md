# Phase 9 Plan: QA Evaluation & Metrics

**Status**: Pending  
**Duration**: 12-14 hours (+ 2-4h for QA dataset)  
**Dependencies**: Phases 7-8 (validation framework)  
**Priority**: High - Essential for KG quality measurement

---

## Overview

Phase 9 implements **QA Evaluation** to measure the quality of the constructed knowledge graph against benchmark questions. This phase uses the validation framework from Phase 8 to:

1. Load benchmark QA datasets
2. Execute queries against the KG
3. Compute evaluation metrics (accuracy, precision, recall, F1)
4. Generate evaluation reports
5. Compare against baselines

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│ Phase 9: QA Evaluation Module                       │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌──────────────────┐  ┌──────────────────┐        │
│  │ QA Dataset       │  │ Graph Store      │        │
│  │ - Questions      │  │ (Neo4j/RDF/etc)  │        │
│  │ - Answers        │  │                  │        │
│  │ - Metrics        │  │                  │        │
│  └──────────────────┘  └──────────────────┘        │
│         ↓                      ↓                    │
│  ┌──────────────────────────────────┐              │
│  │ Query Executor                   │              │
│  │ - SPARQL query generation        │              │
│  │ - Query execution                │              │
│  │ - Result collection              │              │
│  └──────────────────────────────────┘              │
│                  ↓                                  │
│  ┌──────────────────────────────────┐              │
│  │ Metrics Computation              │              │
│  │ - Accuracy                       │              │
│  │ - Precision/Recall               │              │
│  │ - F1 Score                       │              │
│  │ - BLEU (semantic matching)       │              │
│  │ - Coverage                       │              │
│  └──────────────────────────────────┘              │
│                  ↓                                  │
│  ┌──────────────────────────────────┐              │
│  │ Evaluation Report Generation     │              │
│  │ - Summary metrics                │              │
│  │ - Per-question breakdown         │              │
│  │ - Baseline comparisons           │              │
│  │ - Recommendations                │              │
│  └──────────────────────────────────┘              │
│                                                      │
└─────────────────────────────────────────────────────┘
     ↓
Evaluation Results + Benchmark Report
```

---

## Task Breakdown

### Task 9.1: QA Dataset Management (2-3 hours)

**Goal**: Implement QA dataset loading and management.

**Deliverables**:
- `src/kgbuilder/evaluation/qa_dataset.py` - Dataset management
- Support for multiple QA formats (JSON, CSV, SPARQL)
- Dataset validation and statistics
- Test coverage: 70%+

**Technical Details**:

```python
@dataclass
class QAQuestion:
    """Single QA question with expected answer."""
    id: str
    question: str
    expected_answers: list[str]  # Multiple valid answers
    query_type: str  # "entity" | "relation" | "count" | "boolean"
    difficulty: int  # 1-5
    tags: list[str]  # Categories
    metadata: dict[str, Any]

@dataclass
class QADataset:
    """Collection of QA questions for evaluation."""
    name: str
    description: str
    questions: list[QAQuestion]
    version: str
    source: str
    
    def load(path: Path) -> "QADataset"
    def save(path: Path) -> None
    def get_statistics(self) -> dict[str, Any]
    def filter_by_type(self, query_type: str) -> "QADataset"
    def filter_by_difficulty(self, min: int, max: int) -> "QADataset"
```

**Supported Formats**:
- **JSON**: Questions with expected answers
- **CSV**: Simple tabular format
- **SPARQL**: Questions with SPARQL templates
- **Custom**: User-defined loaders via Protocol

**Key Features**:
- Load from file or directory
- Validate dataset structure
- Compute dataset statistics (avg difficulty, question types, etc.)
- Support train/test splits

### Task 9.2: Query Executor (3-4 hours)

**Goal**: Execute queries against the KG and collect results.

**Deliverables**:
- `src/kgbuilder/evaluation/query_executor.py` - Query execution
- Support SPARQL queries
- Entity/relation lookups
- Fuzzy matching for approximate answers
- Test coverage: 70%+

**Technical Details**:

```python
class QueryExecutor:
    """Execute questions against knowledge graph."""
    
    def execute(
        self,
        question: QAQuestion,
        store: GraphStore
    ) -> QueryResult
    
    def execute_entity_query(self, entity_name: str) -> list[str]
    def execute_relation_query(self, subject: str, relation: str) -> list[str]
    def execute_count_query(self, entity_type: str) -> int
    def execute_boolean_query(self, triple: tuple) -> bool

@dataclass
class QueryResult:
    question_id: str
    question_text: str
    retrieved_answers: list[str]
    confidence_scores: list[float]
    execution_time_ms: float
    error: str | None = None
```

**Query Types**:
1. **Entity Queries**: "Who is Alice?" → entity lookup
2. **Relation Queries**: "What company does Bob work for?" → relation traversal
3. **Count Queries**: "How many organizations are there?" → aggregation
4. **Boolean Queries**: "Is Alice CEO of TechCorp?" → fact verification
5. **Complex Queries**: SPARQL for multi-hop reasoning

**Fuzzy Matching**:
- String similarity (Levenshtein distance)
- Semantic similarity (using embeddings if available)
- Threshold-based acceptance

### Task 9.3: Metrics Computation (3-4 hours)

**Goal**: Compute evaluation metrics.

**Deliverables**:
- `src/kgbuilder/evaluation/metrics.py` - Metrics calculation
- Accuracy, precision, recall, F1
- Coverage, completeness metrics
- Semantic similarity metrics
- Test coverage: 75%+

**Technical Details**:

```python
@dataclass
class EvaluationMetrics:
    """Computed evaluation metrics."""
    accuracy: float  # % correct answers
    precision: float  # TP / (TP + FP)
    recall: float  # TP / (TP + FN)
    f1: float  # 2 * (precision * recall) / (precision + recall)
    
    coverage: float  # % answerable questions
    completeness: float  # Answer completeness score
    
    avg_execution_time_ms: float
    error_rate: float  # % queries with errors

class MetricsComputer:
    """Compute evaluation metrics."""
    
    def compute(
        self,
        results: list[QueryResult],
        dataset: QADataset
    ) -> EvaluationMetrics
    
    def compute_accuracy(self, results: list[QueryResult]) -> float
    def compute_f1(self, results: list[QueryResult]) -> float
    def compute_coverage(self, results: list[QueryResult]) -> float
    def compute_semantic_similarity(
        self,
        retrieved: str,
        expected: str
    ) -> float
```

**Metrics Definitions**:

1. **Accuracy**: % of questions with at least one correct answer
   - Threshold-based: retrieved answer matches expected (string or semantic)

2. **Precision**: TP / (TP + FP)
   - True Positives: Correctly retrieved answers
   - False Positives: Incorrectly retrieved answers

3. **Recall**: TP / (TP + FN)
   - False Negatives: Valid answers not retrieved

4. **F1 Score**: Harmonic mean of precision and recall

5. **Coverage**: % of answerable questions
   - Question answerable if at least one correct answer retrieved

6. **Completeness**: For multi-answer questions, % of expected answers found

7. **Semantic Similarity**: BM25 or embedding-based similarity

### Task 9.4: Evaluation Report Generation (2-3 hours)

**Goal**: Generate comprehensive evaluation reports.

**Deliverables**:
- `src/kgbuilder/evaluation/reporter.py` - Report generation
- Markdown and JSON report formats
- Per-question breakdown
- Comparison with baselines
- Test coverage: 70%+

**Technical Details**:

```python
@dataclass
class EvaluationReport:
    """Complete evaluation results."""
    dataset_name: str
    kg_name: str
    evaluation_timestamp: datetime
    
    metrics: EvaluationMetrics
    results_by_question: list[QueryResult]
    results_by_type: dict[str, EvaluationMetrics]
    results_by_difficulty: dict[int, EvaluationMetrics]
    
    baseline_comparison: dict[str, float] | None
    recommendations: list[str]

class EvaluationReporter:
    """Generate evaluation reports."""
    
    def generate_report(
        self,
        results: list[QueryResult],
        dataset: QADataset
    ) -> EvaluationReport
    
    def to_markdown(self, report: EvaluationReport) -> str
    def to_json(self, report: EvaluationReport) -> dict
    def to_html(self, report: EvaluationReport) -> str
```

**Report Contents**:

1. **Executive Summary**
   - Overall accuracy/F1
   - Coverage percentage
   - Comparison with baseline

2. **Metrics Breakdown**
   - By question type (entity, relation, count, etc.)
   - By difficulty level (1-5)
   - By topic/tag

3. **Detailed Results**
   - Per-question breakdown
   - Retrieved vs. expected answers
   - Failure analysis

4. **Baseline Comparison**
   - Simple keyword retrieval baseline
   - Previous KG version (if available)
   - State-of-the-art benchmark

5. **Recommendations**
   - Questions to focus on improving
   - Common error patterns
   - Suggestions for KG enhancement

### Task 9.5: Integration & Testing (2-3 hours)

**Goal**: Integrate evaluation into build pipeline and create comprehensive tests.

**Deliverables**:
- Integrate EvaluationFramework into build_kg.py
- Unit tests for all components
- Integration tests with sample datasets
- Test coverage: 80%+

**Integration Points**:

```python
# In scripts/build_kg.py
result = builder.build(entities=entities, relations=relations)

# Run evaluation (if dataset provided)
if args.evaluate and args.qa_dataset:
    evaluator = EvaluationFramework(
        graph_store=neo4j_store,
        dataset_path=args.qa_dataset
    )
    evaluation_report = evaluator.evaluate()
    print(f"Accuracy: {evaluation_report.metrics.accuracy:.1%}")
    print(f"Coverage: {evaluation_report.metrics.coverage:.1%}")
```

---

## Files to Create/Modify

### New Files

| File | Purpose | LOC (est.) |
|------|---------|-----------|
| `src/kgbuilder/evaluation/__init__.py` | Module exports | 30 |
| `src/kgbuilder/evaluation/qa_dataset.py` | QA dataset management | 250 |
| `src/kgbuilder/evaluation/query_executor.py` | Query execution | 350 |
| `src/kgbuilder/evaluation/metrics.py` | Metrics computation | 300 |
| `src/kgbuilder/evaluation/reporter.py` | Report generation | 350 |
| `tests/test_evaluation.py` | Unit + integration tests | 700 |

**Total New Code**: ~1,980 LOC

### Modified Files

| File | Change |
|------|--------|
| `scripts/build_kg.py` | Add `--evaluate` and `--qa-dataset` arguments |
| `src/kgbuilder/__init__.py` | Export evaluation module |

---

## QA Dataset Format

### JSON Format

```json
{
  "name": "DBpedia 50",
  "description": "50 QA questions from DBpedia",
  "version": "1.0",
  "source": "DBpedia",
  "questions": [
    {
      "id": "q1",
      "question": "Who is the founder of Apple?",
      "expected_answers": ["Steve Jobs"],
      "query_type": "entity",
      "difficulty": 1,
      "tags": ["company", "founder"]
    },
    {
      "id": "q2",
      "question": "What is the capital of France?",
      "expected_answers": ["Paris"],
      "query_type": "entity",
      "difficulty": 1,
      "tags": ["geography"]
    }
  ]
}
```

### SPARQL Format

```sparql
# q1: Who is the founder of Apple?
PREFIX dbo: <http://dbpedia.org/ontology/>
SELECT ?founder WHERE {
  ?company dbo:name "Apple" .
  ?company dbo:founder ?founder .
}
```

---

## Testing Strategy

### Unit Tests (60% of test time)

```python
def test_qa_dataset_load_json()
def test_qa_dataset_filter_by_type()
def test_query_executor_entity_query()
def test_query_executor_relation_query()
def test_metrics_accuracy_computation()
def test_metrics_f1_computation()
def test_reporter_markdown_generation()
```

### Integration Tests (40% of test time)

```python
def test_evaluation_complete_workflow()
def test_evaluation_with_sample_dataset()
def test_evaluation_comparison_with_baseline()
def test_evaluation_report_generation()
```

### Test Fixtures

- Sample QA datasets (JSON, CSV)
- Sample KG with known questions
- Baseline KG for comparison

---

## Acceptance Criteria

✅ **Must Have**:
- [ ] QA dataset loading (JSON, CSV, SPARQL)
- [ ] Query execution against KG
- [ ] Metrics computation (accuracy, precision, recall, F1)
- [ ] Coverage calculation
- [ ] Report generation (Markdown, JSON)
- [ ] All tests passing (35+ tests)
- [ ] 70%+ code coverage
- [ ] Integration with build_kg.py

✅ **Should Have**:
- [ ] Baseline comparison
- [ ] Per-question breakdown
- [ ] Per-difficulty breakdown
- [ ] Semantic similarity metrics
- [ ] HTML report generation

✅ **Could Have**:
- [ ] ML-based answer matching
- [ ] Interactive evaluation dashboard
- [ ] Incremental evaluation tracking
- [ ] Dataset augmentation tools

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Code Coverage | 75%+ |
| Tests Passing | 100% |
| Documentation | Complete |
| Performance | <100ms per query |
| Metrics Accuracy | Match reference implementation |

---

## Dependencies

### New Dependencies

```toml
# None required for core evaluation
# Optional for enhanced features:
scikit-learn = "^1.0"  # For ML-based metrics
scipy = "^1.0"         # For similarity computation
```

### Existing Dependencies Used

- `structlog` - Logging
- `pydantic` - Data validation
- `rdflib` - SPARQL query support (if using RDF backend)

---

## Risk & Mitigation

| Risk | Mitigation |
|------|-----------|
| QA dataset size/quality | Start with small benchmark, extend iteratively |
| Performance on large datasets | Implement query batching and caching |
| Metric definition ambiguity | Use standard metrics from literature (BLEU, F1) |
| Baseline comparison unavailability | Implement simple keyword retrieval baseline |

---

## Related Files & References

- [MASTER_PLAN.md](MASTER_PLAN.md) - Overall roadmap
- [PHASE_8_PLAN.md](PHASE_8_PLAN.md) - Validation framework
- [INTERFACES.md](INTERFACES.md) - Protocol specifications
- QA Dataset Examples: TBD

---

## Next Phase (Phase 10)

Phase 10 will implement **Experiment Framework** for reproducible experiments:
- Metrics collection across multiple KG configurations
- Convergence analysis
- Comparative analysis reports
- Publication-ready visualizations

---

## Implementation Checklist

### Setup
- [ ] Create feature branch `feature/phase-9-evaluation`
- [ ] Create directory structure
- [ ] Setup __init__.py files

### Task 9.1: QA Dataset
- [ ] Implement QAQuestion dataclass
- [ ] Implement QADataset class
- [ ] Support JSON loading
- [ ] Support CSV loading
- [ ] Implement dataset statistics
- [ ] Write tests (15+)

### Task 9.2: Query Executor
- [ ] Implement QueryResult dataclass
- [ ] Implement QueryExecutor class
- [ ] Implement entity query execution
- [ ] Implement relation query execution
- [ ] Implement fuzzy matching
- [ ] Write tests (20+)

### Task 9.3: Metrics
- [ ] Implement EvaluationMetrics dataclass
- [ ] Implement MetricsComputer class
- [ ] Implement accuracy computation
- [ ] Implement F1 computation
- [ ] Implement coverage computation
- [ ] Write tests (15+)

### Task 9.4: Reporting
- [ ] Implement EvaluationReport dataclass
- [ ] Implement EvaluationReporter class
- [ ] Implement Markdown generation
- [ ] Implement JSON generation
- [ ] Write tests (10+)

### Task 9.5: Integration
- [ ] Update build_kg.py with --evaluate flag
- [ ] Update build_kg.py with --qa-dataset argument
- [ ] Integrate EvaluationFramework
- [ ] Integration tests (8+)
- [ ] Test coverage: 75%+

### Documentation
- [ ] Create PHASE_9_PLAN.md (this file) ✓
- [ ] Create API documentation
- [ ] Create usage guide
- [ ] Add examples

### Final
- [ ] All tests passing
- [ ] Code coverage: 75%+
- [ ] Documentation complete
- [ ] Commit to feature branch
- [ ] Merge to main
