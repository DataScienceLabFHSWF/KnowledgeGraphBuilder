# Quick Reference: Next Steps

**TL;DR**: Looping & discovery work ✅ | Need to implement **4 more phases** to reach MVP

---

## The 4 Phases Blocking MVP

### 🔴 PHASE 7: Relation Extraction (CRITICAL)
- **Status**: Scaffolding exists, not implemented
- **File**: `src/kgbuilder/extraction/relation.py` → fill `LLMRelationExtractor.extract()`
- **Why blocking**: Without relations, KG is just isolated entities (20% complete)
- **Effort**: 6-8 hours
- **Priority**: DO FIRST - blocks everything else
- **Pattern**: Copy from entity extraction (similar structure)

### 🟡 PHASE 8: Graph Validation (HIGH PRIORITY)
- **Status**: Interfaces designed, not implemented
- **Files**: New module `src/kgbuilder/validation/`
- **What to build**: SHACL validator, domain rules, conflict detection, metrics
- **Why needed**: Quality assurance before evaluation
- **Effort**: 6-8 hours
- **Priority**: DO SECOND - depends on Phase 7

### 🟡 PHASE 9: QA Evaluation (MEASURES QUALITY)
- **Status**: Interfaces designed, not implemented
- **Files**: New module `src/kgbuilder/evaluation/`
- **What to build**: Load QA dataset, compute accuracy/semantic/RAG metrics
- **Why needed**: Measure KG utility on benchmark questions
- **Effort**: 12-14 hours + 2-4 hours for dataset
- **Priority**: DO THIRD - depends on Phases 7-8

### 🟢 PHASE 10: Experiment Framework (COMPARATIVE SCIENCE)
- **Status**: Fully designed, not implemented
- **Files**: New module `src/kgbuilder/experiment/`
- **What to build**: Metrics collection, convergence analysis, comparison reports
- **Why needed**: Reproducible experiments for publication
- **Effort**: 12-15 hours
- **Priority**: DO FOURTH - nice-to-have, can do manual comparisons

---

## When to Run KG Builder for Evaluation

| Option | When | Includes | Use For |
|--------|------|----------|---------|
| **A: Now** | ASAP (2h) | Entities only | Baseline numbers |
| **B: After Phase 7** | ~8h | Entities + Relations ✓ | Real evaluation |
| **C: Full experiment** | ~3 weeks | All phases + framework | Publication results |

**Recommendation**: Option B after Phase 7 implementation

---

## Current State Summary

```
✅ Phases 1-6: COMPLETE
   • Ontology loading
   • Question generation
   • Iterative discovery (3+ loops verified)
   • Entity extraction
   • KG assembly to Neo4j
   • Backend-agnostic storage & export

❌ Phases 7-10: PENDING
   • Relations (blocks evaluation)
   • Validation (quality assurance)
   • QA evaluation (measure quality)
   • Experiment framework (comparison)
```

**Current KG**: ~50-100 entities, **NO relations** → 20% complete

---

## Files to Know

| File | Purpose |
|------|---------|
| `scripts/build_kg.py` | Production entry point (ready to use) |
| `src/kgbuilder/extraction/relation.py` | Relation extraction (needs implementation) |
| `tests/test_extraction_assembly.py` | Tests for extraction (already written) |
| `Planning/NEXT_STEPS_AND_EVALUATION.md` | Detailed roadmap (READ THIS) |
| `Planning/CURRENT_STATE_VS_END_GOALS.md` | Detailed comparison (READ THIS) |

---

## Critical Blocking Issue

**Without Phase 7 (Relation Extraction)**:
- ❌ KG has entities but no connections
- ❌ Can't evaluate graph structure
- ❌ Can only do single-hop Q&A
- ❌ Results won't be meaningful for publication

**After Phase 7**:
- ✅ Full connected graph
- ✅ Can validate structure
- ✅ Can do multi-hop reasoning
- ✅ Results publishable

---

## Week 1 Action Plan

```
Day 1-2:
  □ Current pipeline finishes (~2 hours)
  □ Check first KG in Neo4j (run /tmp/query_graph.py)
  □ Document baseline (entity count, confidence scores)

Day 3-5:
  □ Implement Phase 7 (Relation Extraction) - 6-8 hours
  □ Run tests: pytest tests/test_extraction_assembly.py
  □ Run fresh build_kg.py with relations included

Day 6-7:
  □ Implement Phase 8 (Graph Validation) - 6-8 hours
  □ Validate first complete KG
  □ Document validation results
```

---

## Key Insight

The looping and discovery are working perfectly! The pipeline is iterating through questions multiple times, extracting more entities each time. The only missing piece is **extracting the relationships between these entities**.

Once Phase 7 is done, we'll have a real, queryable knowledge graph that can answer complex questions.

