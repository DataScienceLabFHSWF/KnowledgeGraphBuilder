# Repository Cleanup Plan

> Status: **In Progress**
> Created: 2026-02-13
> Updated: 2026-02-13

---

## 1. Current State Summary

The repo is **functionally complete** for its core purpose (KG construction,
validation, export) but has accumulated clutter from 10+ development phases:
planning docs for sibling repos, overlapping scripts, stray log files, broken
pyproject.toml entry points, and several superseded planning documents.

### What works today

| Component | Status |
|-----------|--------|
| Document ingestion (PDF, DOCX, law XML) | Working |
| Ontology-guided LLM extraction | Working |
| Discovery loop (iterative extraction) | Working |
| Confidence tuning + coreference | Working |
| KG assembly into Neo4j | Working |
| pySHACL validation (always runs) | Working |
| SHACL shapes auto-generation from OWL | Working |
| KG export (Turtle, JSON-LD, Cypher, GraphML) | Working |
| Experiment framework + W&B logging | Working |
| SHACL2FOL / Vampire static checks | **Working** — satisfiability + action validation via lib/SHACL2FOL.jar |
| CI (pytest + SHACL smoke test) | Minimal |

### Key metrics (current KG)

- Neo4j: 1 397 nodes, 4 906 edges, 39 entity types
- pySHACL: conforms=True, 0 violations
- Combined quality score: 1.0

---

## 2. Cleanup Tasks

### 2.1 Root Directory — Remove Log Files & Clutter

**Problem**: 11 log files (~7 500 lines) and 4 misplaced markdown files in
the root.

| Action | File(s) |
|--------|---------|
| **Delete** | `pipeline_log.txt`, `kg_build.log`, `law_graph_20260209_210225.log`, `law_graph_20260211_072015.log`, `nohup.out`, `production_baseline_run_v8.log`, `production_baseline_run_v9.log`, `production_baseline_run_v10.log`, `single_experiment.log`, `test_experiment.log`, `test_experiment_fixed.log`, `.coverage` |
| **Move → `Planning/`** | `IMPLEMENTATION_SUMMARY.md`, `PIPELINE_COMPARISON.md` |
| **Move → `Planning/archive/`** | `CHANGELOG_20260205.md`, `QUESTIONS_ANSWERED.md` |
| **Keep or merge into README** | `QUICKSTART_LAW_GRAPH.md` (decision: keep for now, consider merging later) |
| **Add to `.gitignore`** | `*.log`, `nohup.out`, `.coverage`, `htmlcov/`, `.pytest_cache/`, `wandb/`, `__pycache__/`, `config.properties` |

**Effort**: 15 min

---

### 2.2 Planning/ — Consolidate & Archive Stale Docs

**Problem**: 30+ docs in `Planning/`, many overlapping or superseded. Users
can't tell which is authoritative.

#### Archive (move to `Planning/archive/`)

| File | Reason |
|------|--------|
| `LAW_GRAPH_PLAN.md` | Explicitly superseded by `LAW_GRAPH_IMPLEMENTATION.md` |
| `NEXT_STEPS.md` | Overlaps `04_ISSUES_BACKLOG.md` — merge actionable items into backlog first |
| `INTERFACE_CONTRACT.md` | Subset of `03_INTERFACES.md` — merge new content into 03 first |
| `KGL_INTEGRATION_STRATEGY.md` | Phase 11 plan, unclear if adopted; archive until revisited |
| `SHACL_STATIC_VALIDATION_PLAN.md` | Superseded by `VALIDATION_PLAN.md` |

#### Move to sibling repos (when they exist)

| Files | Target |
|-------|--------|
| `C1_*.md` (7 files) | `OntologyExtender` repo (or archive for now) |
| `C3_*.md` (5 files) | `GraphQAAgent` repo (or archive for now) |

#### Keep (canonical set)

| # | File | Purpose |
|---|------|---------|
| 1 | `01_ACADEMIC_OVERVIEW.md` | Research framing |
| 2 | `02_ARCHITECTURE.md` | Pipeline architecture |
| 3 | `03_INTERFACES.md` | Protocol & interface specs |
| 4 | `04_ISSUES_BACKLOG.md` | Unified task list (merge NEXT_STEPS items in) |
| 5 | `05_SMOKE_TEST_RESULTS.md` | Test snapshots |
| 6 | `06_VERSIONING_GUIDE.md` | KG versioning how-to |
| 7 | `12_SEMANTIC_ENHANCEMENT.md` | Future phase plan |
| 8 | `COMPETENCY_QUESTIONS.md` | Domain CQs |
| 9 | `LAW_DOCUMENT_CHECKLIST.md` | Law document tracking |
| 10 | `LAW_GRAPH_IMPLEMENTATION.md` | Law graph design (canonical) |
| 11 | `LAW_ONTOLOGY_RATIONALE.md` | Ontology selection justification |
| 12 | `LAW_ONTOLOGY_SOURCES.md` | Citation list |
| 13 | `LANGEXTRACT_EVAL.md` | LangExtract evaluation |
| 14 | `VALIDATION_PLAN.md` | Validation & scoring (canonical) |

**Effort**: 30 min (includes merging actionable items before archiving)

---

### 2.3 scripts/ — Consolidate & Clean Up

**Problem**: 39 scripts with 3 overlapping pipeline entry points, 1 `.bak`
file, and 1 misplaced test.

| Action | File(s) | Detail |
|--------|---------|--------|
| **Delete** | `build_law_graph.py.bak` | Dead backup |
| **Delete or archive** | `pipeline_phase6.py` | References archived MASTER_PLAN.md; likely dead |
| **Move → `tests/`** | `test_inference.py` | It's a test, not a script |
| **Consolidate** | `build_kg.py` + `full_kg_pipeline.py` + `run_kg_pipeline_on_documents.py` | Keep `full_kg_pipeline.py` as the canonical pipeline script; make `build_kg.py` a thin Docker entry-point calling it; archive `run_kg_pipeline_on_documents.py` |
| **Review** | `organize_and_download_xml.py` | Overlaps `download_law_xml_zips.py` — verify and consolidate |
| **Rename** | `ABLATION_STUDY_EXAMPLES.py` | It's a config reference, not an executable — rename to `.md` or move to `examples/` |

**Effort**: 45 min

---

### 2.4 SHACL2FOL — Fix or Formalize as Optional

**Problem**: SHACL2FOL is wired in at the code level but effectively dormant
because (a) shapes are generated in-memory from OWL (never persisted to disk),
and (b) the prover output parser is fragile.

#### Option A: Make it work (recommended)

1. **Persist `shapes.ttl`** — after `SHACLShapeGenerator.generate()`, write
   the graph to `output/validation_reports/shapes.ttl` so `StaticValidator`
   can find a file on disk.
2. **Fix `_parse_output()`** — run SHACL2FOL manually, collect actual output
   samples for all modes, and write proper parsers (regex or structured).
3. **Add integration test** — extend `tests/integration/test_static_validation_real.py`
   to cover satisfiability and action validation with the law ontology shapes.
4. **Docker optional** — keep Docker container as a CI/server artifact; for
   local dev, invoke the JAR directly (already works via `lib/SHACL2FOL.jar`).

#### Option B: Remove SHACL2FOL entirely

1. Remove `StaticValidator`, `ActionConverter`, Docker SHACL2FOL image.
2. Simplify scorer to only use pySHACL.
3. Remove `consistency` and `acceptance` from score weights.
4. Adjust CI workflow.

**Recommendation**: Option A. SHACL2FOL provides unique value (pre-commit
validation of graph updates), and the remaining work is small.

**Effort**: Option A ~2–3 hours; Option B ~1 hour.

---

### 2.5 pyproject.toml — Fix Broken Entry Points & Metadata

**Problem**: 4 entry points reference non-existent modules (`scripts.ingest_data`,
`scripts.extract_kg`, `scripts.serve`). Project URL has placeholder
`yourusername`.

| Action | Detail |
|--------|--------|
| Fix or remove entry points | Either create proper CLI modules in `src/kgbuilder/cli/` or remove the broken `[project.scripts]` section |
| Update project URLs | Replace `yourusername` with `DataScienceLabFHSWF` |
| Verify `requirements.txt` vs `pyproject.toml` deps | Ensure they're in sync |

**Effort**: 20 min

---

### 2.6 Tests — Reorganize

**Problem**: 8 test files at `tests/` root mixing unit and integration tests.
Only 1 file in `tests/unit/`.

| Action | Detail |
|--------|--------|
| Move unit tests to `tests/unit/` | `test_evaluation.py`, `test_simple_kg_assembler.py`, `test_findings_synthesizer.py`, `test_question_generator.py` |
| Move integration tests to `tests/integration/` | `test_integration.py`, `test_phase7_integration.py`, `test_extraction_assembly.py`, `test_storage.py` |
| Keep `conftest.py` at root | Shared fixtures |

**Effort**: 20 min

---

### 2.7 CI — Add Lint & Type-Check Jobs

**Problem**: CI only runs pytest. No linting, formatting, or type-checking.

| Action | Detail |
|--------|--------|
| Add `ruff check` step | Catches lint issues before merge |
| Add `mypy --strict` step | Catches type errors |
| Add `ruff format --check` step | Enforces consistent formatting |

**Effort**: 20 min (modify `.github/workflows/ci-shacl.yml`)

---

### 2.8 .gitignore — Expand Coverage

Add the following patterns (if not already present):

```gitignore
# Logs
*.log
nohup.out

# Coverage
.coverage
htmlcov/

# Caches
.pytest_cache/
__pycache__/
*.pyc

# IDE
.vscode/
.idea/

# Build
dist/
*.egg-info/

# Runtime
wandb/
experiment_output/
output/
config.properties
```

**Effort**: 5 min

---

### 2.9 README.md — Minor Tweaks

The README was rewritten recently and is in good shape. Minor updates:

| Action | Detail |
|--------|--------|
| Add SHACL2FOL status note | Clarify it's optional / best-effort |
| Add quickstart for law graph | Or link to `QUICKSTART_LAW_GRAPH.md` |
| Update Documentation table | Remove archived docs, add `REPO_CLEANUP_PLAN.md` once actions complete |

**Effort**: 10 min

---

## 3. Planned Final State

After cleanup, the repository structure should look like:

```
KnowledgeGraphBuilder/
├── README.md                     # Clean project overview
├── LICENSE
├── pyproject.toml                # Fixed entry points + URLs
├── requirements.txt
├── docker-compose.yml            # Neo4j, Qdrant, Fuseki, Ollama
├── Dockerfile                    # Main pipeline container
├── .env.example
├── .gitignore                    # Comprehensive exclusions
│
├── .github/
│   ├── copilot-instructions.md
│   └── workflows/
│       └── ci.yml                # pytest + ruff + mypy + SHACL smoke
│
├── docker/
│   └── Dockerfile.shacl2fol      # Optional SHACL2FOL container
│
├── lib/                          # JARs + binaries (gitignored or vendored)
│   ├── SHACL2FOL.jar
│   └── vampire
│
├── data/
│   ├── README.md
│   ├── ontology/                 # OWL ontologies + generated shapes
│   ├── evaluation/
│   ├── smoke_test/
│   └── ...
│
├── examples/
│   ├── build_pipeline_example.py
│   └── experiment configs
│
├── scripts/                      # ~25 scripts (down from 39)
│   ├── full_kg_pipeline.py       # Canonical pipeline entry point
│   ├── build_kg.py               # Docker entry point (delegates to above)
│   ├── build_law_graph.py        # Law-specific pipeline
│   ├── run_kg_scoring.py         # Standalone scorer
│   ├── run_single_experiment.py  # Experiment runner
│   ├── validate_*.py             # Validation utilities
│   ├── download_*.py             # Data acquisition (consolidated)
│   └── docker/
│       └── run_shacl2fol_container.sh
│
├── src/kgbuilder/                # Source code (unchanged)
│   ├── core/
│   ├── document/
│   ├── extraction/
│   ├── confidence/
│   ├── assembly/
│   ├── validation/               # pySHACL + SHACL2FOL (fixed)
│   ├── storage/
│   ├── analytics/
│   ├── experiment/
│   └── ...
│
├── tests/                        # Reorganized
│   ├── conftest.py
│   ├── unit/                     # Fast, isolated tests
│   ├── integration/              # Slow, requires services
│   ├── validation/
│   ├── confidence/
│   ├── extraction/
│   └── assembly/
│
└── Planning/                     # ~14 canonical docs (down from 30+)
    ├── 01_ACADEMIC_OVERVIEW.md
    ├── 02_ARCHITECTURE.md
    ├── 03_INTERFACES.md
    ├── 04_ISSUES_BACKLOG.md
    ├── 05_SMOKE_TEST_RESULTS.md
    ├── 06_VERSIONING_GUIDE.md
    ├── 12_SEMANTIC_ENHANCEMENT.md
    ├── COMPETENCY_QUESTIONS.md
    ├── LAW_DOCUMENT_CHECKLIST.md
    ├── LAW_GRAPH_IMPLEMENTATION.md
    ├── LAW_ONTOLOGY_RATIONALE.md
    ├── LAW_ONTOLOGY_SOURCES.md
    ├── LANGEXTRACT_EVAL.md
    ├── VALIDATION_PLAN.md
    └── archive/                  # Everything else
```

---

## 4. Execution Order

Suggested sequence to minimize risk:

| # | Task | Risk | Effort | Status |
|---|------|------|--------|--------|
| 1 | Expand `.gitignore` (§2.8) | None | 5 min | **Done** |
| 2 | Delete log files + `.bak` (§2.1) | None | 15 min | **Done** |
| 3 | Move misplaced root markdowns (§2.1) | None | 5 min | **Done** |
| 4 | Archive superseded Planning docs (§2.2) | Low | 30 min | **Done** |
| 5 | Fix `pyproject.toml` (§2.5) | Low | 20 min | **Done** |
| 6 | Consolidate scripts (§2.3) | Medium | 45 min | Not started |
| 7 | Reorganize tests (§2.6) | Medium | 20 min | Not started |
| 8 | Add CI lint/type-check (§2.7) | Low | 20 min | Not started |
| 9 | Fix SHACL2FOL integration (§2.4) | Medium | 2–3 hrs | **Done** |
| 10 | README minor tweaks (§2.9) | None | 10 min | Not started |

**Total**: ~5 hours

---

## 5. Documentation Updates Required

After cleanup, these docs need a refresh:

| Doc | Update needed |
|-----|---------------|
| `README.md` | Reflect consolidated scripts, SHACL2FOL status |
| `02_ARCHITECTURE.md` | Add validation architecture diagram from VALIDATION_PLAN |
| `04_ISSUES_BACKLOG.md` | Merge items from NEXT_STEPS before archiving it |
| `VALIDATION_PLAN.md` | Update SHACL2FOL status after fix; mark persisted shapes as done |
| `data/README.md` | Verify still accurate |
| `.github/copilot-instructions.md` | Update module tree to match final structure |
