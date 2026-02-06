# Next Steps & Evaluation Strategy

**Status**: February 3, 2026 | Phase 6 Complete  
**Last Updated**: Current pipeline running (2.5+ hours into build cycle)

---

## Executive Summary

The **core KG building pipeline is COMPLETE AND WORKING** (all 5 phases verified):
- ✅ Ontology loading
- ✅ Question generation  
- ✅ Iterative discovery (3+ loops confirmed)
- ✅ Entity extraction
- ✅ KG assembly to Neo4j

**To reach end goals**, we need to implement these 4 phases in order:

| Phase | Priority | Timeframe | Component | Purpose |
|-------|----------|-----------|-----------|---------|
| **7** | 🔴 CRITICAL | Week 1 | Relation Extraction | Extract entity relationships |
| **8** | 🟡 HIGH | Week 1-2 | Graph Validation | Validate KG quality |
| **9** | 🟡 HIGH | Week 2 | QA Evaluation | Test on benchmark questions |
| **10** | 🟢 MEDIUM | Week 3 | Experiment Framework | Track/compare experiments |

---

## Phase 7: Relation Extraction (CRITICAL NEXT)

**Status**: Scaffolding exists, but `LLMRelationExtractor.extract()` not implemented

### What's Already Done
- ✅ `LLMRelationExtractor` class exists with constructor
- ✅ LangChain chain (`create_relation_extraction_chain`) exists with prompt
- ✅ Pydantic schema (`RelationExtractionOutput`) for JSON output
- ✅ Domain/range validation methods stubbed out
- ✅ Cardinality constraint methods stubbed out
- ✅ Tests in `test_extraction_assembly.py`

### What Needs Implementation

```python
# File: src/kgbuilder/extraction/relation.py

def extract(
    self,
    text: str,
    entities: list[ExtractedEntity],
    ontology_relations: list[OntologyRelationDef],
) -> list[ExtractedRelation]:
    """
    TODO:
    1. Generate ontology-guided prompt with entity context
    2. Call LLM with structured output schema
    3. Validate domain/range constraints
    4. Filter by confidence threshold
    5. Check cardinality constraints
    6. Return relations with evidence
    """
    # Currently: raise NotImplementedError()
```

### Acceptance Criteria
- [ ] Extract relations between entities from text
- [ ] Respect ontology domain/range constraints
- [ ] Enforce cardinality constraints (functional, inverse_functional)
- [ ] Support n-ary relations via reification
- [ ] Confidence scores calibrated
- [ ] Unit tests passing (use existing test framework)

### Why It's Blocking
- **build_kg.py Phase 5** calls `SimpleKGAssembler` which needs relations
- Currently relations are being **created empty or not used**
- Without relations, the KG is just isolated entities (not a true graph)
- Can't evaluate graph structure, reasoning, or answer multi-hop questions

### Estimated Effort
- **Implementation**: 4-6 hours (mostly copy pattern from entity extraction)
- **Testing**: 1-2 hours
- **Total**: ~6-8 hours

---

## Phase 8: Graph Validation (SECOND PRIORITY)

**Status**: Interfaces defined, components partially implemented

### What's Already Done
- ✅ Validation interfaces defined in `INTERFACES.md`
- ✅ SHACL validation foundation exists
- ✅ Graph statistics collection in new `GraphStateMetrics` class
- ✅ Neo4j query layer ready

### What Needs Implementation

```python
# Purpose: Ensure KG quality before evaluation

Components:
1. SHACLValidator
   - Validate against ontology shapes
   - Report constraint violations
   
2. DomainRuleValidator
   - Check project-specific rules
   - e.g., "Every Action must have an Actor"
   
3. ConflictDetector
   - Find contradictory claims
   - Merge equivalent entities
   
4. QualityMetrics
   - Completeness (coverage of ontology classes)
   - Consistency (no contradictions)
   - Coherence (graph structure quality)
   - Confidence distribution analysis
```

### Acceptance Criteria
- [ ] Validate KG against SHACL shapes (from Fuseki)
- [ ] Detect and report violations
- [ ] Check domain-specific rules
- [ ] Identify mergeable entities
- [ ] Generate validation report with statistics
- [ ] CLI to run: `python scripts/validate_kg.py`

### Why It's Important
- **Before QA evaluation**: Ensure KG is valid
- **Before experiment comparison**: Understand KG quality
- **For iteration**: Know what went wrong if results are poor

### Estimated Effort
- **Implementation**: 4-6 hours
- **Testing**: 1-2 hours
- **Total**: ~6-8 hours

---

## Phase 9: QA Evaluation (THIRD PRIORITY)

**Status**: Interfaces fully defined, no implementation yet

### What's Already Done
- ✅ `QADataset` model defined with QA examples
- ✅ `QAEvaluationResult` model defined
- ✅ `AccuracyMetrics`, `SemanticMetrics`, `RAGMetrics` models
- ✅ `RetrievalMetrics` module exists (`src/kgbuilder/retrieval/evaluation.py`)
- ✅ Deepeval integration point defined (but not implemented)

### What Needs Implementation

```python
# Purpose: Answer benchmark questions using the KG

Component: QAEvaluator
- Load QA dataset (Gold standard questions + answers)
- For each question:
  1. Query KG for answer
  2. Compute accuracy (Exact Match, F1)
  3. Compute semantic similarity (embedding-based)
  4. Compute RAG metrics (Faithfulness, Relevance, etc.)
  5. Track reasoning hops for multi-hop questions

Metrics to compute:
- Exact Match
- F1 Score
- Precision/Recall
- Semantic Similarity (BERTScore)
- Faithfulness (answer grounded in retrieved context)
- Relevance (retrieved context relevant to question)
- Answer Completeness
- Average Latency
- Reasoning accuracy (for multi-hop questions)

Breakdown by:
- Difficulty (easy/medium/hard)
- Answer type (exact/list/boolean/freeform)
- Reasoning hops (1-hop direct, 2+ multi-hop)
```

### Acceptance Criteria
- [ ] Load QA dataset from file or directory
- [ ] Execute questions against built KG
- [ ] Compute accuracy metrics
- [ ] Compute semantic metrics (BERTScore, embedding similarity)
- [ ] Compute RAG metrics (deepeval integration)
- [ ] Track efficiency metrics (latency, tokens)
- [ ] Generate per-question result table
- [ ] Generate aggregate results with confidence intervals
- [ ] Export results to CSV/JSON for analysis

### Why It's Important
- **Measure quality**: How good is our KG at answering questions?
- **Identify gaps**: Which question types fail?
- **Compare variants**: Test different ontology/RAG/extraction versions
- **Publish results**: Needed for research paper

### Estimated Effort
- **Implementation**: 6-8 hours (requires deepeval integration)
- **Dataset prep**: 2-4 hours (curating nuclear decommissioning QA pairs)
- **Testing**: 2 hours
- **Total**: ~12-14 hours

---

## Phase 10: Experiment Tracking & Comparison (FOURTH PRIORITY)

**Status**: Fully designed, scaffolding exists, not implemented

### What's Already Done
- ✅ `ExperimentConfig` model defined
- ✅ `IterationMetrics` model with all fields
- ✅ `ConvergenceAnalysis` model
- ✅ `ExperimentReport` model
- ✅ Comparison models (`OntologyDiff`, `KGBuildingComparison`, `RAGComparisonResult`)
- ✅ File structure planned

### What Needs Implementation

```python
# Purpose: Track experiments systematically for scientific evaluation

Components:

1. ExperimentRunner
   - Load config
   - Run build_kg.py with metrics collection
   - Collect per-iteration metrics
   - Save experiment report

2. MetricsCollector
   - Hook into build_kg.py phases
   - Record: nodes/edges added, confidence scores, time, tokens
   - Detect convergence (no new nodes for N iterations)
   - Track CQ coverage progression

3. ComparisonFramework
   - Compare two experiments:
     * Different ontology versions
     * Different RAG variants (classic/hybrid/kg-only)
     * Different extraction configs
   - Generate comparison report with deltas
   - Statistical significance testing

4. ReportGenerator
   - Markdown reports
   - CSV tables for paper
   - Plots (matplotlib): convergence curves, metric breakdowns
   - LaTeX export for academic papers
```

### Acceptance Criteria
- [ ] Run experiments with full metrics tracking
- [ ] Generate convergence analysis (iterations to converge, final scores)
- [ ] Compare two experiments (ontology versions, RAG variants)
- [ ] Generate comparison reports (Markdown + JSON)
- [ ] Export to LaTeX tables
- [ ] Generate visualization plots
- [ ] CLI: `python scripts/run_experiment.py --config config.json`

### Why It's Important
- **Scientific rigor**: Reproducible, comparable experiments
- **Ablation studies**: Measure impact of ontology/RAG changes
- **Publication-ready**: Results formatted for academic paper
- **Scaling**: Can run multiple experiments to identify best settings

### Estimated Effort
- **Implementation**: 8-12 hours
- **Testing**: 2-3 hours
- **Total**: ~12-15 hours

---

## When to Run KG Builder for First Evaluation

### Option A: Run NOW (Recommended for Quick Feedback)
**✅ DO THIS FIRST**

- **When**: Once current pipeline finishes (should be within next few hours)
- **What to do**:
  ```bash
  # 1. Let current run finish
  tail -f /tmp/kg_pipeline_output.log
  
  # 2. Check final graph size
  python /tmp/query_graph.py  # Check Neo4j
  
  # 3. Run Phase 8 validation (once implemented)
  python scripts/validate_kg.py
  
  # 4. Document findings for Phase 7 implementation
  ```

- **Expected output**: First complete KG with entities only (no relations yet)
- **Purpose**: Baseline understanding before Phase 7 implementation
- **Time**: 2-3 hours from now

### Option B: Wait for Phase 7 (Recommended for Full Evaluation)
**✅ DO THIS SECOND**

- **When**: After Phase 7 (Relation Extraction) is implemented (~6-8 hours)
- **What to do**:
  ```bash
  # Fresh run with relations included
  python scripts/build_kg.py --questions-per-class 5 --max-iterations 10
  
  # Then validate + evaluate
  python scripts/validate_kg.py  # Phase 8
  python scripts/evaluate_qa.py  # Phase 9
  ```

- **Expected output**: Full KG with entities AND relationships
- **Purpose**: Real graph structure, can evaluate reasoning
- **Time**: ~4-6 hours for full build + validation + QA

### Option C: Comprehensive Experiment (Recommended for Paper)
**✅ DO THIS THIRD**

- **When**: After Phases 7-9 are implemented (~2-3 weeks)
- **What to do**:
  ```bash
  # Run controlled experiment with metrics tracking
  python scripts/run_experiment.py \
    --config experiments/base_ontology.json \
    --output results/experiment_001/
  
  # Compare with variant
  python scripts/run_experiment.py \
    --config experiments/extended_ontology.json \
    --output results/experiment_002/
  
  # Generate comparison
  python scripts/compare_experiments.py \
    --exp1 results/experiment_001/ \
    --exp2 results/experiment_002/
  ```

- **Expected output**: Scientific report with metrics and plots
- **Purpose**: Publication-quality results
- **Time**: ~6-8 hours per experiment

---

## Critical Path to MVP

### Week 1 (This Week)
- ✅ Let current build_kg.py run finish → First KG baseline
- ⏳ **Implement Phase 7** (Relation Extraction) → Relations in KG
- ⏳ **Implement Phase 8** (Graph Validation) → Quality metrics

### Week 2
- ⏳ **Implement Phase 9** (QA Evaluation) → Answer benchmark questions
- ⏳ Create gold-standard QA dataset for nuclear decommissioning
- ⏳ Run evaluation → First quality metrics

### Week 3
- ⏳ **Implement Phase 10** (Experiment Tracking)
- ⏳ Run controlled experiments
- ⏳ Generate paper-ready results

### MVP Achieved
- ✅ Working KG builder (all phases)
- ✅ Validated KG (structural quality)
- ✅ QA evaluation (functional quality)
- ✅ Reproducible experiments
- ✅ Publishable results

---

## File Locations for Implementation

### Phase 7 (Relation Extraction)
```
src/kgbuilder/extraction/relation.py     # Update LLMRelationExtractor.extract()
src/kgbuilder/extraction/chains.py       # Relation chain already exists
tests/test_extraction_assembly.py        # Already has tests
```

### Phase 8 (Graph Validation)
```
src/kgbuilder/validation/
├── __init__.py
├── shacl_validator.py      # SHACL shape validation
├── domain_rules.py         # Domain-specific rules
├── conflict_detector.py     # Contradiction detection
└── quality_metrics.py       # Graph quality analysis

scripts/validate_kg.py       # Entry point
```

### Phase 9 (QA Evaluation)
```
src/kgbuilder/evaluation/
├── __init__.py
├── qa_evaluator.py         # QA evaluation logic
├── metrics.py              # Metric computation
└── deepeval_integration.py # Deepeval wrapper

data/qa/                     # QA datasets
└── nuclear_decom_qa.json   # Gold standard questions

scripts/evaluate_qa.py       # Entry point
```

### Phase 10 (Experiment Tracking)
```
src/kgbuilder/experiment/
├── __init__.py
├── runner.py               # ExperimentRunner
├── metrics_collector.py     # MetricsCollector
├── comparison.py            # Comparison logic
└── reporter.py             # Report generation

scripts/run_experiment.py    # Entry point
scripts/compare_experiments.py

experiments/                 # Experiment configs
└── base_ontology.json
```

---

## Summary: What's Next?

### Immediately (Today)
1. ✅ Current pipeline finishes → Check first KG in Neo4j
2. 📝 Document baseline metrics (node/edge count, confidence distribution)
3. 🔍 Visually inspect KG structure (should be entities only for now)

### This Week
1. **Implement Phase 7** - Relation Extraction (CRITICAL)
   - Without this, KG is incomplete
   - ~6-8 hours of work
   - Enables real graph structure evaluation

2. **Implement Phase 8** - Graph Validation
   - Ensures KG quality before QA tests
   - ~6-8 hours of work
   - Generates quality metrics

### Next Week
1. **Implement Phase 9** - QA Evaluation
   - Measures functional quality
   - Requires gold-standard QA dataset
   - ~12-14 hours of work

2. Create benchmark questions
   - Nuclear decommissioning domain-specific
   - Mix of easy/medium/hard, single-hop/multi-hop
   - ~10-15 questions minimum

### Milestone: MVP Achieved
All phases 1-9 complete → **Production-ready KG builder with full evaluation**

---

## Questions to Guide Next Steps

1. **Should we wait for Phase 7?** 
   - YES - Current KG is incomplete without relations
   - Could run now to establish baseline, but results won't be meaningful

2. **What's the gold-standard QA dataset?**
   - Need 10-30 questions about nuclear decommissioning
   - Each with ground truth answer(s)
   - Covering different difficulty/hop levels
   - Could extract from initial documents or create manually

3. **What ontology variant should we test?**
   - Current ontology in Fuseki
   - Could create extended version with more classes/relations
   - Comparison would show impact of ontology quality

4. **Timeline for paper?**
   - If publishing soon: Prioritize Phases 7-9
   - If more exploratory: Can do full Phase 10 experiment framework

