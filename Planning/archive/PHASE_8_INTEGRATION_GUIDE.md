# Phase 8 Integration Guide: Validation Pipeline & Stopping Criteria

## Overview

The Phase 8 validation pipeline has been fully integrated into the main `build_kg.py` script. This enables:

1. **Phase 7: Validation & Quality Assessment** - Run consistency checks on the assembled KG
2. **Phase 8: Competency Question Coverage** - Implement stopping criteria based on CQ answering

## Quick Start

### Default Build (with validation)

```bash
python scripts/build_kg.py
```

This runs the full pipeline with validation enabled (Phase 7 only).

### Build with Competency Question Checking (Stopping Criterion)

```bash
python scripts/build_kg.py \
  --check-competency-questions \
  --cq-coverage-threshold 0.8 \
  --validation-report-dir ./reports
```

**Parameters:**
- `--check-competency-questions`: Enable Phase 8 (CQ coverage check)
- `--cq-coverage-threshold`: Minimum % of questions that must be answerable (default: 0.8 = 80%)
- `--validation-report-dir`: Where to save JSON/Markdown/HTML reports

### Build without Validation

```bash
python scripts/build_kg.py --validate false
```

## Pipeline Phases

### Phase 1-6: Standard Discovery & Assembly
Same as before - loads ontology, generates questions, retrieves documents, extracts entities/relations, deduplicates, and assembles KG.

### Phase 7: Validation & Quality Assessment

**What it does:**
- Runs consistency checks on the assembled KG
- Detects conflicts (type conflicts, value conflicts, cardinality violations)
- Identifies potential duplicates via similarity
- Generates validation reports (JSON, Markdown, HTML)

**Output:**
```
PHASE 7: Knowledge Graph Validation & Quality Assessment
--------
✓ Consistency check complete
  - Conflicts detected: 5
  - Potential duplicates: 12
  - Conflict rate: 1.25%
  - Recommendations: Review detected conflicts and resolve manually or via automatic merge
  - Reports saved to: ./validation_reports
```

**Reports generated:**
- `validation_reports/validation_report.json` - Machine-readable format
- `validation_reports/validation_report.md` - Human-readable Markdown
- `validation_reports/validation_report.html` - Interactive HTML report

### Phase 8: Competency Question Coverage Check (Stopping Criterion)

**What it does:**
- Checks which competency questions are answered by the KG
- Calculates coverage percentage
- Compares against threshold to determine if stopping criterion is met
- Lists unanswered questions for guidance

**Output:**
```
PHASE 8: Competency Question Coverage Check (Stopping Criterion)
--------
✓ Competency Question Coverage Analysis
  - Total questions: 15
  - Answerable: 13
  - Coverage: 86.7%
  - Threshold: 80.0%
  ✓ STOPPING CRITERION MET - Coverage above threshold

Unanswered questions to address:
  - How did organization X acquire company Y?
  - What is the timeline of acquisitions in sector Z?
```

**Stopping Criterion Logic:**
- If coverage ≥ threshold → BUILD SUCCESSFUL ✓
- If coverage < threshold → NEED MORE DATA ✗ (provides list of missing questions)

## Full Example: High-Quality Build with All Features

```bash
python scripts/build_kg.py \
  --questions-per-class 5 \
  --max-iterations 10 \
  --classes-limit 20 \
  --confidence-threshold 0.6 \
  --similarity-threshold 0.85 \
  --dense-weight 0.7 \
  --sparse-weight 0.3 \
  --top-k 10 \
  --validate \
  --check-competency-questions \
  --cq-coverage-threshold 0.85 \
  --validation-report-dir ./reports/phase_8 \
  --verbose
```

**What this does:**
1. Generates 5 questions per ontology class (max 20 classes)
2. Runs discovery loop up to 10 times per question
3. Extracts with 60% confidence minimum
4. Deduplicates entities with 85% similarity threshold
5. Uses 70% dense + 30% sparse retrieval
6. Retrieves top 10 documents per query
7. Runs Phase 7 validation (consistency checking)
8. Runs Phase 8 stopping criterion (must answer 85% of CQs)
9. Saves detailed reports to `./reports/phase_8`
10. Prints verbose debug output

## Summary Report

After the pipeline completes, you'll see:

```
================================================================================
PIPELINE EXECUTION SUMMARY
================================================================================
Status:                  SUCCESS ✓
Total time:              284.3s

Ontology:
  Classes processed:     20
  Questions generated:   100

Knowledge Discovery:
  Entities discovered:   1,523
  Entities synthesized:  1,245
  Merge rate:            18.3%

Relation Extraction:
  Relations extracted:   3,456

Neo4j Graph:
  Nodes created:         1,245
  Relationships created: 3,456
  Assembly errors:       0

Validation:
  Status:                ✓ PASSED
  Conflicts detected:    3

Competency Questions (Stopping Criterion):
  Coverage:              87.5%
  Threshold:            85.0%
  Status:                ✓ MET

Database: bolt://localhost:7687
================================================================================
```

## Integration Points

### Modified `scripts/build_kg.py`

**New imports:**
```python
from kgbuilder.validation import (
    SHACLValidator, 
    RulesEngine, 
    ConsistencyChecker, 
    ReportGenerator, 
    ValidationResult
)
from kgbuilder.validation.validators import CompetencyQuestionValidator
```

**New CLI arguments:**
- `--validate` (bool, default: True) - Enable Phase 7
- `--check-competency-questions` (bool, default: False) - Enable Phase 8
- `--cq-coverage-threshold` (float, default: 0.8) - CQ coverage minimum
- `--validation-report-dir` (str, default: "./validation_reports") - Report output dir

**New pipeline phases:**
- Phase 7: Consistency checking → conflict detection → report generation
- Phase 8: CQ coverage analysis → stopping criterion evaluation

### Validation Module Files

Located in `src/kgbuilder/validation/`:

1. **models.py** - Data models (ValidationViolation, Conflict, etc.)
2. **shacl_validator.py** - SHACL constraint validation
3. **rules_engine.py** - Semantic rule execution (inverse, transitive, domain/range, functional)
4. **consistency_checker.py** - Conflict and duplicate detection
5. **reporter.py** - Multi-format report generation (JSON/Markdown/HTML)
6. **validators.py** - Existing validators including CompetencyQuestionValidator
7. **__init__.py** - Public API exports

## Typical Workflows

### Workflow 1: Quick Discovery

```bash
python scripts/build_kg.py \
  --questions-per-class 3 \
  --max-iterations 5 \
  --validate
```
**Use when:** You want a basic KG quickly with validation

### Workflow 2: High-Quality Build with Quality Gate

```bash
python scripts/build_kg.py \
  --questions-per-class 5 \
  --max-iterations 10 \
  --confidence-threshold 0.7 \
  --similarity-threshold 0.9 \
  --validate \
  --check-competency-questions \
  --cq-coverage-threshold 0.9 \
  --validation-report-dir ./quality_reports
```
**Use when:** You need high-quality KG with comprehensive CQ coverage

### Workflow 3: Targeted Discovery for Missing Questions

```bash
# First, identify missing questions from previous run
# Then focus discovery on those areas
python scripts/build_kg.py \
  --questions-per-class 10 \
  --max-iterations 15 \
  --check-competency-questions \
  --cq-coverage-threshold 0.95
```
**Use when:** You have an existing KG and want to complete coverage

### Workflow 4: Experimental/Development

```bash
python scripts/build_kg.py \
  --validate false \
  --verbose
```
**Use when:** Testing components without full validation overhead

## Troubleshooting

### Issue: Competency question coverage is low

**Solution:**
1. Review the unanswered questions listed in output
2. Add more source documents to Qdrant
3. Increase `--max-iterations` to run longer discovery
4. Lower `--confidence-threshold` to include more tentative findings
5. Increase `--questions-per-class` for more coverage

### Issue: Too many conflicts detected

**Solution:**
1. Increase `--similarity-threshold` to avoid merging different entities
2. Increase `--confidence-threshold` to exclude uncertain extractions
3. Review and clean source documents in Qdrant

### Issue: Pipeline runs out of memory

**Solution:**
1. Reduce `--classes-limit` to process fewer classes
2. Lower `--max-iterations` per question
3. Reduce `--top-k` for retrieval

## Next Steps

- Phase 9: Analytics & Evaluation (not yet integrated)
- Phase 10: Human-in-the-loop refinement
- Phase 11: KG export and publication formats

## References

- [PHASE_8_PLAN.md](./PHASE_8_PLAN.md) - Detailed Phase 8 specifications
- [Validation Module Architecture](../src/kgbuilder/validation/README.md) - Technical details
- [tests/test_validation.py](../tests/test_validation.py) - Test examples
