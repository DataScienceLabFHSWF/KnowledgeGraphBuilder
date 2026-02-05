# Quick Reference: KG Pipeline Commands

**TL;DR**: One command to build complete KG with all validations

---

## The Command You Need

```bash
# Full KG construction with all validations
python scripts/full_kg_pipeline.py

# With custom documents
python scripts/full_kg_pipeline.py --documents data/my_docs

# With config file
python scripts/full_kg_pipeline.py --config config.json

# Validate the results
python scripts/validate_kg_complete.py --output report.json
```

---

## What Those Commands Do

| Command | What Happens | Output |
|---------|--------------|--------|
| `full_kg_pipeline.py` | Loads ontology → documents → extracts entities+relations → builds KG → validates → exports | `output/kg_results/kg_*.json` |
| `validate_kg_complete.py` | Checks ontology, extraction quality, KG structure, integration | `report.json` |
| `run_single_experiment.py` | Runs with multiple variants, tracks metrics | `experiment_results/` |

---

## Running the Current Experiment

```bash
# Start in background
nohup python scripts/run_single_experiment.py examples/experiment_baseline.json > single_experiment.log 2>&1 &

# Watch progress
tail -f single_experiment.log

# Validate while running
python scripts/validate_kg_complete.py
```

---

## Checking Results

### Neo4j (what got created)
```bash
# How many entities?
cypher-shell -u neo4j -p password "MATCH (n) RETURN COUNT(n);"

# How many relations (edges)?
cypher-shell -u neo4j -p password "MATCH ()-[r]->() RETURN COUNT(r);"

# List entity types
cypher-shell -u neo4j -p password "MATCH (n) RETURN DISTINCT labels(n)[0] as type, COUNT(n) as count;"
```

### Files
```bash
# What was created?
ls -lh output/kg_results/

# Validation report
cat output/kg_results/kg_validation_report.json | jq '.'

# Check logs
tail -100 single_experiment.log | grep -E "phase|extracted|error"
```

---

## Configuration Quick-Start

### Simple Config (config.json)
```json
{
  "max_iterations": 2,
  "coverage_target": 0.85,
  "confidence_threshold": 0.6,
  "document_dir": "data/documents",
  "output_dir": "output/my_kg"
}
```

### Run It
```bash
python scripts/full_kg_pipeline.py --config config.json
```

---

## If Something Goes Wrong

### JSON Parsing Errors
- ✅ FIXED! Arithmetic expressions now evaluated
- Just run the pipeline again

### Timeouts
```bash
# Increase timeout in config
{
  "llm_timeout": 600  // 10 minutes instead of 5
}
```

### Empty KG (No Nodes/Edges)
```bash
# Check each phase
python scripts/validate_kg_complete.py --focus ontology    # Are classes loaded?
python scripts/validate_kg_complete.py --focus extraction  # Are entities extracted?
python scripts/validate_kg_complete.py --focus kg          # Is Neo4j connected?
```

---

## What's New (This Session)

✅ **JSON arithmetic fixed** - No more "266 - 12 + 8" errors  
✅ **Phase 5 integrated** - Relations now extracted and in KG  
✅ **All scripts wired** - Automatic validation, export, reporting  
✅ **Complete documentation** - See Planning/ folder  

---

## Key Files

| File | Purpose |
|------|---------|
| `scripts/full_kg_pipeline.py` | Everything in one script |
| `scripts/validate_kg_complete.py` | Comprehensive validation |
| `scripts/run_single_experiment.py` | Track experiments with variants |
| `Planning/COMPLETE_PIPELINE_GUIDE.md` | Full documentation |
| `Planning/PHASE5_IMPLEMENTATION_COMPLETE.md` | Relations implementation |

---

## The Data Flow

```
Ontology (18 classes)
    ↓
Documents (5 PDFs)
    ↓
Discovery Questions
    ↓
Entity Extraction (234 found)
    ↓
Relation Extraction (89 found) ← NEW!
    ↓
Synthesis (198 unique after dedup)
    ↓
Neo4j Graph (198 nodes, 89 edges) ← NOW HAS BOTH!
    ↓
Validation (PASS)
    ↓
Export (JSON-LD, Cypher, RDF)
```

---

## Monitoring Commands

```bash
# Watch extraction progress (real-time)
tail -f single_experiment.log | grep extracted

# Count what's been found so far
tail -f single_experiment.log | grep -E "entity_count|relation_count"

# Find errors
grep -i error single_experiment.log

# Full status
python scripts/validate_kg_complete.py

# Detailed ontology check
python scripts/validate_kg_complete.py --focus ontology
```

---

## One-Liners

```bash
# Full pipeline with all validations
python scripts/full_kg_pipeline.py && python scripts/validate_kg_complete.py

# Experiment + validation
python scripts/run_single_experiment.py examples/experiment_baseline.json & \
  sleep 60 && python scripts/validate_kg_complete.py

# Check what exists
echo "=== Ontology ===" && \
  ls -lh data/ontology/*.owl && \
  echo "=== Documents ===" && \
  ls -lh data/documents/*.pdf | wc -l && \
  echo "=== Results ===" && \
  ls -lh output/kg_results/ 2>/dev/null || echo "(empty - run pipeline first)"
```

---

## Exit Codes

```
0 = Success
1 = Validation failed or errors found
2 = Configuration error
```

---

**Ready to build KGs!** 🚀

For detailed info: See `Planning/COMPLETE_PIPELINE_GUIDE.md`

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

