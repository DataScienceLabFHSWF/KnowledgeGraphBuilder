# KG Validation & Quality Scoring — Implementation Plan

> Status: **In progress**
> Last updated: 2026-02-13

## Goal

Provide an automated, reproducible quality signal for every KG that the
pipeline builds.  The score must be available in CI, in experiment
snapshots, and via a standalone CLI.

---

## Architecture

```
                  ┌──────────────────────┐
                  │  OWL Ontology (.owl)  │
                  └──────────┬───────────┘
                             │ generate
                  ┌──────────▼───────────┐
                  │  SHACL Shapes Graph   │
                  │  (SHACLShapeGenerator)│
                  └──────────┬───────────┘
              ┌──────────────┼──────────────────┐
              ▼                                 ▼
   ┌──────────────────┐              ┌──────────────────┐
   │  SHACL2FOL/       │              │  pySHACL          │
   │  Vampire          │              │  (runtime)        │
   │  (static checks)  │              │  (always runs)    │
   └────────┬─────────┘              └────────┬─────────┘
            │                                 │
            └────────────┬────────────────────┘
                         ▼
              ┌──────────────────┐
              │  KGQualityScorer  │
              │  → KGQualityReport│
              │  → shacl_report.json │
              └──────────────────┘
```

## Components

### 1. `SHACLShapeGenerator` — DONE

| Item | Status |
|------|--------|
| OWL class → `sh:NodeShape` | Done |
| Object property → `sh:class` constraint | Done |
| Datatype property → `sh:datatype` | Done |
| `owl:FunctionalProperty` → `sh:maxCount 1` | Done |
| SPARQL constraints for symmetric/transitive | Done |

File: `src/kgbuilder/validation/shacl_generator.py`

### 2. `SHACLValidator` (pySHACL) — DONE

| Item | Status |
|------|--------|
| Neo4j → RDF conversion | Done |
| Run pySHACL with RDFS inference | Done |
| Parse violation results | Done |
| Handle edge node-type lookup | Done |

File: `src/kgbuilder/validation/shacl_validator.py`

### 3. `StaticValidator` (SHACL2FOL + Vampire) — PARTIAL

| Item | Status |
|------|--------|
| Docker container with JAR + Vampire | Done |
| Satisfiability mode | Done (prover output parsing fragile) |
| Action containment mode | Done (prover output parsing fragile) |
| Reliable output parsing | TODO — prover format varies |

File: `src/kgbuilder/validation/static_validator.py`
Container: `docker/Dockerfile.shacl2fol`

### 4. `KGQualityScorer` — DONE

| Item | Status |
|------|--------|
| Generate shapes from OWL (no shapes.ttl needed) | Done |
| Always run pySHACL | Done |
| Sample 500 entities + relations from Neo4j | Done |
| SHACL2FOL checks (best-effort, skipped when no file) | Done |
| Class coverage computation | Done |
| Weighted combined score | Done |
| JSON report output | Done |
| Injected SHACLValidator (testable) | Done |

File: `src/kgbuilder/validation/scorer.py`

### 5. Experiment integration — DONE

| Item | Status |
|------|--------|
| Run scorer after KG build in experiment | Done |
| Copy `shacl_report.json` into run directory | Done |
| Log SHACL metrics to W&B | Done |
| Include SHACL metrics in `kg_metrics` | Done |

File: `src/kgbuilder/experiment/manager.py`

### 6. Remaining work (backlog)

| Item | Status | Priority |
|------|--------|----------|
| Persist generated shapes.ttl alongside report | TODO | Medium |
| CI job: run scorer on push and post score | TODO | Medium |
| SHACL2FOL output parser robustness | TODO | Low |
| Comparative scoring (before/after enrichment) | TODO | Low |
| Domain-specific shape constraints (cardinality etc.) | TODO | Low |
| Interactive violation browser (HTML) | TODO | Low |

---

## Score Weights

| Component | Weight | What it measures |
|-----------|--------|------------------|
| `consistency` | 0.30 | SHACL2FOL satisfiability (1.0 if shapes are logically consistent) |
| `acceptance` | 0.20 | SHACL2FOL action validation on sampled entities/relations |
| `class_coverage` | 0.15 | Fraction of ontology classes appearing as Neo4j labels |
| `shacl_score` | 0.35 | 1 − normalised pySHACL violation count (always runs) |

Combined: `0.30 × consistency + 0.20 × acceptance + 0.15 × coverage + 0.35 × shacl`

---

## CLI Usage

```bash
# Standalone scoring against Neo4j
PYTHONPATH=src python scripts/run_kg_scoring.py

# Override OWL path
ONTOLOGY_OWL_PATH=./data/ontology/domain/plan-ontology-v1.0.owl \
  PYTHONPATH=src python scripts/run_kg_scoring.py

# Validate exported TTL file
PYTHONPATH=src python scripts/validate_kg_ttl.py

# Validate live Neo4j graph
PYTHONPATH=src python scripts/validate_neo4j.py
```

---

## Output Artifacts

Each scoring run produces:

```
output/validation_reports/
  shacl_report_<timestamp>.json   ← pySHACL result + violations

experiment_output/<run_id>/
  run_metadata.json               ← includes kg_metrics.shacl.*
  shacl_report.json               ← copy of the pySHACL report
```

### shacl_report.json schema

```json
{
  "timestamp": 1770983426,
  "valid": true,
  "violation_count": 0,
  "node_count": 1397,
  "edge_count": 4906,
  "violations": [
    {
      "severity": "Violation",
      "message": "...",
      "path": "...",
      "focus_node": "...",
      "shape": "..."
    }
  ]
}
```
