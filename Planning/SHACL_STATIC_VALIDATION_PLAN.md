# SHACL Static Validation Integration Plan

**Branch**: `feature/shacl-static-validation`  
**Status**: Stubs created, implementation pending  
**Paper**: Ahmetaj et al. "SHACL Validation under Graph Updates" (arXiv:2508.00137, 2025)  
**Tool**: [paolo7/SHACL2FOL](https://github.com/paolo7/SHACL2FOL) (Apache-2.0)

---

## 1. Motivation

The current validation pipeline has critical gaps discovered during the
`baseline_33docs_20260212_0752` run:

| Gap | Severity | Description |
|-----|----------|-------------|
| G1  | CRITICAL | `SHACLValidator` exists (425 lines) but is **never called** |
| G2  | HIGH     | Validation is **post-hoc only** — errors found after graph write |
| G3  | HIGH     | No SHACL shape generation from OWL ontology |
| G4  | CRITICAL | `RulesEngine` ran with **0 rules** (now fixed) |
| G6  | CRITICAL | `BuildPipeline._validation_step()` returns **mock data** |
| G7  | HIGH     | No validation feedback loop to extraction |

This feature adds **proactive ("pre-commit") validation**: checking whether
proposed entities/relations will violate SHACL constraints *before* writing
them to the graph store.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Discovery Loop  (per iteration)                                │
│                                                                 │
│   Extract entities/relations                                    │
│        │                                                        │
│        ▼                                                        │
│   ┌──────────────────┐                                          │
│   │ ActionConverter   │  entities + relations → SHACL2FOL JSON  │
│   └────────┬─────────┘                                          │
│            │                                                    │
│            ▼                                                    │
│   ┌──────────────────┐   ┌──────────────────┐                   │
│   │ StaticValidator   │◀──│ SHACLShapeGen    │ OWL → shapes.ttl │
│   │ (SHACL2FOL JAR)  │   └──────────────────┘                   │
│   └────────┬─────────┘                                          │
│            │                                                    │
│        ┌───┴───┐                                                │
│        │ VALID │──▶  Write to GraphStore                        │
│        └───────┘                                                │
│        │INVALID│──▶  Feedback: log violation, optionally retry  │
│        └───────┘                                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. New Files (stubs created ✅)

### Source

| File | Purpose | Status |
|------|---------|--------|
| `src/kgbuilder/validation/shacl_generator.py` | OWL → SHACL NodeShapes/PropertyShapes | Stub ✅ |
| `src/kgbuilder/validation/static_validator.py` | SHACL2FOL JAR subprocess wrapper | Stub ✅ |
| `src/kgbuilder/validation/action_converter.py` | Entities/Relations → SHACL2FOL JSON | Stub ✅ |

### Tests

| File | Purpose | Status |
|------|---------|--------|
| `tests/validation/test_shacl_generator.py` | Unit tests for shape generation | Stub ✅ |
| `tests/validation/test_static_validator.py` | Unit tests for JAR wrapper | Stub ✅ |
| `tests/validation/test_action_converter.py` | Unit tests for action conversion | Stub ✅ |

### Updated

| File | Change | Status |
|------|--------|--------|
| `src/kgbuilder/validation/__init__.py` | Export new classes | Done ✅ |

---

## 4. Implementation Phases

### Phase 1: Shape Generation (G3)

**Goal**: Auto-generate SHACL shapes from OWL ontology.

1. Implement `SHACLShapeGenerator.generate()`:
   - Query `FusekiOntologyService.get_all_classes()` → `sh:NodeShape` per class
   - Query `get_class_properties()` → `sh:PropertyShape` with `sh:class`/`sh:datatype`
   - Query `get_special_properties()` → `sh:maxCount 1` for functional, SPARQL constraints for transitive/symmetric
   - Query `get_class_hierarchy()` → `sh:node` linking child to parent shape
2. Implement `serialize()` and `save()` for Turtle/JSON-LD output
3. Wire into pipeline: generate shapes once at startup, cache

**Dependencies**: `rdflib` (already installed)

### Phase 2: Static Validation (G2)

**Goal**: Pre-commit validation using SHACL2FOL theorem prover.

1. Set up SHACL2FOL (local or containerized):
   - Option A (local): Download JAR + Vampire binary to `lib/` and update `StaticValidatorConfig`
   - Option B (recommended): Use the provided Docker image `kgbuilder/shacl2fol` (build with `scripts/docker/run_shacl2fol_container.sh`)
   - Add binaries to `.gitignore` (do not commit Vampire/large binaries)
   - Document setup in `README.md`
2. Implement `ActionConverter.from_entities()` and `from_relations()`:
   - Map `entity.entity_type` → shape URI
   - Map `relation.relation_type` → property path URI
3. Implement `StaticValidator.validate_static()`:
   - Write `config.properties` to temp dir
   - Invoke `java -jar SHACL2FOL.jar` via subprocess (or run inside container)
   - Parse stdout for VALID/INVALID verdict
4. Implement `StaticValidator.validate_entities_and_relations()` convenience wrapper

**Dependencies**: Java 21+, Vampire prover (Linux x86_64). Containerized workflow recommended for portability.

---

## Docker usage (quick)

1. Build & run (example):

   ./scripts/docker/run_shacl2fol_container.sh \
     "<VAMPIRE_TAR_GZ_RELEASE_URL>" \
     "<SHACL2FOL_JAR_DOWNLOAD_URL>"

2. Example smoke test inside container:

   docker run --rm -v "$PWD":/opt/project -w /opt/project kgbuilder/shacl2fol:local smoke

3. Integration pattern:
   - Pipeline can `exec` the static validator inside the same container, or
   - Mount `lib/SHACL2FOL.jar` + Vampire binary and run `StaticValidator` in host Python but pointing `StaticValidatorConfig` to the container-mounted paths.

### Phase 3: Pipeline Integration (G1, G6, G7)

**Goal**: Wire validation into the actual pipeline.

1. In `IterativeDiscoveryLoop._process_question()`:
   - After extraction, run `StaticValidator.validate_entities_and_relations()`
   - If INVALID: log warning, skip writing those entities/relations
   - If VALID: proceed with assembly
2. In `scripts/full_kg_pipeline.py._validate_kg()`:
   - Replace mock validation with real `SHACLValidator.validate()`
   - Add static validation summary to pipeline results
3. Add `--enable-static-validation` CLI flag (off by default for speed)

---

## 5. SHACL2FOL Specifics

### Action JSON Format

```json
[
  {
    "type": "ShapeAction",
    "subjectShape": "https://purl.org/ai4s/shapes/FacilityShape",
    "objectShape": "https://purl.org/ai4s/shapes/OrganizationShape"
  },
  {
    "type": "PathAction",
    "path": "https://purl.org/ai4s/ontology/planning#hasOperator"
  }
]
```

### Config Properties

```properties
proverPath=/path/to/vampire
tptpPrefix=fof
encodeUNA=false
```

### Expected Output

- `VALID`: All possible applications of actions preserve validity
- `INVALID + counterexample`: At least one application violates constraints

---

## 6. Limitations & Mitigations

| Limitation | Mitigation |
|------------|------------|
| SHACL2FOL supports SHACL core only (no SHACL-SPARQL) | Generate core-only shapes; keep SPARQL constraints in pyshacl post-hoc |
| Vampire timeout on large shape sets | Configurable timeout; fall back to pyshacl if prover times out |
| Java 21 requirement | Docker container with Java + Vampire pre-installed |
| No Windows support for Vampire | Linux-only CI/CD; optional in pipeline |

---

## 7. Contribution Mapping

| Contribution | Relevance |
|-------------|-----------|
| **C1** (KG Construction) | Validation-in-the-loop improves construction quality |
| **C3** (Evaluation) | SHACL pass rates as a quality metric |
| **C1 novelty** | Static pre-commit validation is novel for KG construction pipelines |
