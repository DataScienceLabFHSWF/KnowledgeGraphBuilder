# Validation

## Overview

Every KG build is validated and scored automatically using multiple
complementary approaches.

## Validation Layers

### 1. SHACL Validation (pySHACL)

SHACL shapes are **auto-generated** from the OWL ontology. No manual
shape authoring is required.

```bash
PYTHONPATH=src python scripts/run_kg_scoring.py
```

The `SHACLShapeGenerator` converts:

- OWL classes to `sh:NodeShape`
- Object properties to `sh:class` constraints
- Datatype properties to `sh:datatype` constraints
- `owl:FunctionalProperty` to `sh:maxCount 1`
- Symmetric/transitive properties to SPARQL constraints

### 2. SHACL2FOL Static Validation (Optional)

Uses the [SHACL2FOL](https://doi.org/10.1007/978-3-031-47243-5_7) approach
with the Vampire theorem prover for static satisfiability checking:

```bash
./scripts/setup_shacl2fol.sh  # one-time setup
```

### 3. Semantic Rules Engine

Four rule types run against the assembled graph:

| Rule | What It Checks |
|------|---------------|
| `DomainRangeRule` | Source type in domain, target type in range |
| `FunctionalPropertyRule` | At most one value per subject |
| `InversePropertyRule` | Inverse relation consistency |
| `TransitiveRule` | Transitive closure completeness |

### 4. Consistency Checker

Detects:

- Type conflicts (entity assigned conflicting types)
- Value conflicts (contradictory property values)
- Cardinality violations
- Duplicate entity sets

## Quality Score

The `KGQualityScorer` computes a weighted composite score:

| Metric | Weight | Description |
|--------|--------|-------------|
| Consistency | 0.2 | SHACL2FOL satisfiability |
| SHACL conformance | 0.3 | 1.0 minus normalized violation count |
| Class coverage | 0.3 | Fraction of ontology classes in graph |
| Acceptance rate | 0.2 | Sampled action validation pass rate |

Output: `output/validation_reports/shacl_report_<timestamp>.json`

## Standalone Validation

```bash
# Full validation suite
PYTHONPATH=src python scripts/validate_kg_complete.py

# Quality scoring only
PYTHONPATH=src python scripts/run_kg_scoring.py
```
