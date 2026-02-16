# Backlog — KnowledgeGraphBuilder

**Last updated**: 2026-02-16  
**Baseline**: 213 unit tests passing, 0 failing, 0 errors (5 infra-dependent skipped)  
**Coverage**: ~16% (unit tests only, most integration tests need services)

---

## How to use this document

Each item has a **priority**, **effort estimate**, **skill level**, and a brief
description of what needs to happen.  Pick an item, move it to *In Progress*
in whatever tracker you use, and open a PR against `main`.

Priority labels:

| Label | Meaning |
|-------|---------|
| P0 | Blocks correctness / CI / installability — fix first |
| P1 | Important for research quality or usability |
| P2 | Improves robustness, developer experience, or extensibility |
| P3 | Nice-to-have, stretch goals |

---

## P0 — Blocking / Correctness (ALL RESOLVED)

### ~~B-001  Fix `pyproject.toml` dependency: `qdrant-client`~~ ✅

Fixed `qdrant-client>=2.7.0` → `qdrant-client>=1.16.0,<2.0`.

---

### ~~B-002  Fix 39 failing unit tests + 31 errors~~ ✅

All 213 unit tests now pass (0 failures, 0 errors). Fixes applied:

- **ExperimentRun**: Backward-compat constructor with legacy kwargs
- **ConvergenceAnalysis/ComparativeAnalysis**: Added `__post_init__` auto-compute, `metrics=` alias, `best_margin`/`margins`
- **ConfigRunner**: Accept `ConfigVariant | Path` as first arg
- **ExperimentResults**: `config` now optional, added `total_duration`/`aggregated_metrics` properties
- **ExperimentAnalyzer**: Accepts `list[ExperimentRun]` or `ExperimentResults`
- **EvaluationConfig**: Added `dataset_path`/`compute_metrics`/`confidence_threshold` legacy aliases
- **ExperimentConfig**: `output_dir` optional, `parallel_workers` alias, `save`/`load`/`to_json` methods
- **QADataset**: `load()` → `@classmethod`, `split_ratio` alias, `difficulties` key alias
- **EvaluationMetrics**: Added `completeness` field
- **Node/Edge**: `label` default `""`, `source_node_type`/`target_node_type` optional
- **ValidationViolation**: `to_dict()` returns uppercase severity NAME
- **ValidationResult**: `_recompute_pass_rate()` on mutation (SHACL violations only)
- **SHACLValidator**: Empty shapes graph accepted, `shape_uri` optional
- **SemanticRule**: `name`/`description` defaults
- **ReportGenerator**: Safe format strings, ✓/✗ symbols, "No violations found" message
- **KGBuilderParams**: `similarity_threshold` default `0.85` → `0.8`

---

### ~~B-003  `datetime.utcnow()` deprecation~~ ✅

Replaced all 10 occurrences across `protocol.py`, `assembler.py`, `export.py`
with `datetime.now(tz=timezone.utc)`. Zero deprecation warnings.

---

---

## P1 — Research Quality & Usability

### ~~B-004  Delete stub validators in `validation/validators.py`~~ ✅

Deleted `validators.py` (192 lines of dead code). Removed `SHACLValidator`,
`OntologyValidator`, `CompetencyQuestionValidator` stubs and `Validator`
protocol. Updated `validation/__init__.py`, `kgbuilder/__init__.py`, and
`scripts/full_kg_pipeline.py` imports. Also added `@pytest.mark.skip` to 5
infra-dependent tests that hang without Ollama/Neo4j.

---

### ~~B-005  Implement stub methods in `storage/rdf.py`~~ ✅

Implemented all 4 `FusekiStore` stubs:
- `add_triple()` — SPARQL INSERT DATA via update endpoint
- `export_rdf()` — GET with content-negotiation (turtle/rdfxml/ntriples/jsonld)
- `add_triples_batch()` — chunked SPARQL INSERT DATA (500 triples/chunk)
- `validate_ontology()` — SPARQL check for missing rdfs:domain on ObjectProperties

---

### ~~B-006  Implement `versioning/service.py` restore + diff~~ ✅

Implemented:
- `diff()` — set-based comparison using manifest.json when snapshots exist,
  falls back to count-based diff otherwise
- `restore()` — clears graph via DETACH DELETE, reloads from Cypher or
  JSON-LD export files in snapshot directory
- `_export_kg()` — writes Cypher CREATE statements or JSON-LD entities
- `_write_manifest()` / `_load_manifest()` — entity/relation ID manifests
  for accurate set-based diffing

---

### B-007  `rag/` module — decide keep or delete

**Effort**: 1 h | **Skill**: any

`src/kgbuilder/rag/__init__.py` contains a 200-line `StandardRAGPipeline`
class.  It's functional but:
- Has zero tests
- Not imported anywhere in the pipeline
- Overlaps with the `retrieval/` module

**Decision needed**: Keep as a RAG baseline for the experiment framework
(wire into ablation/comparison), or delete and point to `GraphQAAgent` repo.

---

### B-008  Increase unit test coverage from 12% to ≥50%

**Effort**: 8–12 h | **Skill**: intermediate

Modules with **0% coverage** (no unit tests at all):

| Module | Lines | Notes |
|--------|-------|-------|
| `analytics/inference.py` | ~200 | OWL-RL inference engine |
| `analytics/metrics.py` | ~150 | Graph analytics |
| `analytics/pipeline.py` | ~120 | Analytics orchestrator |
| `analytics/skos.py` | ~100 | SKOS enrichment |
| `assembly/core.py` | ~300 | KG assembly logic |
| `document/` (all loaders) | ~1200 | PDF/DOCX/PPTX/XML loaders |
| `embedding/ollama.py` | ~250 | OllamaProvider |
| `enrichment/pipeline.py` | ~200 | Enrichment stages |
| `enrichment/enrichers.py` | ~300 | Individual enrichers |
| `pipeline/orchestrator.py` | ~400 | Main pipeline orchestrator |
| `retrieval/` (all) | ~1000 | FusionRAGRetriever, phase2 |
| `storage/neo4j_store.py` | ~300 | Neo4j driver wrapper |
| `storage/rdf.py` | ~250 | Fuseki store |
| `versioning/service.py` | ~190 | Snapshot/diff/restore |
| `validation/scorer.py` | ~500 | Quality scoring |
| `validation/shacl_generator.py` | ~200 | SHACL shape generation |
| `validation/shacl_validator.py` | ~150 | pySHACL runner |

Priority targets for unit tests (no external services needed):
- `analytics/metrics.py` — pure computation
- `enrichment/enrichers.py` — mock LLM provider
- `assembly/core.py` — mock graph store
- `validation/scorer.py` — uses rdflib (no Neo4j needed)

---

### B-009  CI/CD pipeline (GitHub Actions)

**Effort**: 3–4 h | **Skill**: GitHub Actions, Docker

No CI pipeline exists.  Minimum viable:

```yaml
# .github/workflows/ci.yml
jobs:
  lint:    ruff check + black --check + mypy
  test:    pytest tests/unit/ tests/confidence/ tests/extraction/
  docs:    mkdocs build --strict
```

Integration tests (requiring Neo4j/Qdrant/Fuseki/Ollama) should be a separate
workflow triggered manually or on release tags.

---

### B-010  Quickstart script validation & smoke test

**Effort**: 2 h | **Skill**: any

`scripts/quickstart.py` was written but never tested end-to-end with real
infrastructure.  Needs:

1. A smoke test with a tiny ontology + 1-2 docs
2. Verification that all imports resolve (several imports may be wrong — e.g.
   `FusekiStore`, `AdvancedDocumentProcessor`, `QdrantStore` constructor args)
3. A small example dataset under `data/examples/` or `data/smoke_test/`

---

## P2 — Robustness & Developer Experience

### B-011  Clean up dead TODO comments in `__init__.py` files

**Effort**: 1 h | **Skill**: any

Several `__init__.py` files contain multi-line TODO blocks that describe work
already completed in other files.  These are misleading.

**Files**: `agents/__init__.py`, `storage/__init__.py`, `core/protocols.py`,
`document/loaders/base.py`, `document/loaders/pdf.py`,
`document/loaders/office.py`, `document/chunking/strategies.py`

**Fix**: Remove completed TODO comments; leave only genuine open items.

---

### ~~B-011b  Clean up dead/duplicate code in validators.py~~ ✅

Resolved by B-004 — `validators.py` deleted entirely.

---

### B-012  Standardize exception hierarchy

**Effort**: 2 h | **Skill**: intermediate

Some modules raise `RuntimeError`, others `ValueError`, others domain
exceptions from `core/exceptions.py`.  Standardize on the domain hierarchy:

```
KGBuilderError
├── DocumentLoadError
├── ExtractionError
├── ValidationError
├── StorageError
└── PipelineError
```

**Files to audit**: `extraction/entity.py`, `extraction/relation.py`,
`embedding/ollama.py`, `storage/neo4j_store.py`

---

### B-013  Pre-commit hooks configuration

**Effort**: 1 h | **Skill**: any

`pyproject.toml` already lists `pre-commit>=3.5` in dev deps but there's no
`.pre-commit-config.yaml`.

**Create**:
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks: [{ id: ruff, args: [--fix] }, { id: ruff-format }]
  - repo: https://github.com/psf/black
    hooks: [{ id: black }]
  - repo: https://github.com/pre-commit/mirrors-mypy
    hooks: [{ id: mypy, additional_dependencies: [...] }]
```

---

### B-014  Fix remaining ruff lint issues (604 errors after auto-fix)

**Effort**: 3–4 h | **Skill**: any

After `ruff --fix`, 604 issues remain (mostly E501 line-too-long, E402
import-not-at-top, F821 undefined-name, bare-except).

Breakdown:
- **157** E501 (line > 100 chars) — manual reformatting
- **39** E402 (import not at top) — mostly `sys.path` hacks in scripts
- **5** F821 (undefined name) — actual bugs, investigate
- **2** E722 (bare except) — replace with specific exceptions

---

### B-015  `telemetry/` module — wire or remove

**Effort**: 1 h | **Skill**: any

`telemetry/__init__.py` is 5 lines (empty module docstring).
`telemetry/langsmith.py` is 63 lines with a `LangsmithTracer` class.
Neither is imported or used anywhere in the pipeline.

**Decision**: Wire into the pipeline as an optional tracing backend, or
remove to avoid dead code.

---

## P3 — Nice-to-Have / Research Extensions

### B-016  Ablation study tooling

**Effort**: 4–6 h | **Skill**: intermediate

Automated ablation runner that varies:
- Ontology classes (subset selection)
- Competency question groups
- Chunking strategies (semantic, fixed, paragraph, sliding)
- Embedding models (`qwen3-embedding` vs `nomic-embed-text`)
- LLM models (`qwen3:8b` vs `llama3.1:8b` vs `mistral`)

Produces a comparison report (HTML or Markdown) with metrics per variant.

---

### B-017  Community detection & cluster analysis

**Effort**: 4–6 h | **Skill**: graph algorithms

Add community detection to `analytics/`:
- Leiden or Louvain algorithm (via `igraph` or `networkx`)
- Cluster entities by connectivity
- Detect isolated subgraphs
- Visualize communities

---

### B-018  Embedding-based entity linking / deduplication

**Effort**: 6–8 h | **Skill**: NLP / embeddings

Detect near-duplicate entities using embedding similarity:
- Compute pairwise cosine similarity
- Cluster entities above threshold
- Propose merge candidates
- Optional auto-merge with provenance tracking

---

### B-019  Data quality dashboard

**Effort**: 6–8 h | **Skill**: frontend / visualization

Web-based dashboard showing:
- Entity/relation counts over pipeline iterations
- Confidence distribution histograms
- Coverage heatmap (ontology class × documents)
- Validation report summaries
- Could use Streamlit or Panel for rapid prototyping

---

### B-020  Tutorial Jupyter notebooks

**Effort**: 4–6 h | **Skill**: any

Create notebooks under `examples/notebooks/`:
1. `01_document_ingestion.ipynb` — load, chunk, embed a document
2. `02_entity_extraction.ipynb` — extract entities from chunks
3. `03_kg_assembly.ipynb` — build a mini KG in Neo4j
4. `04_validation.ipynb` — run SHACL validation and quality scoring
5. `05_full_pipeline.ipynb` — end-to-end on sample data

---

### B-021  Parquet / Arrow export for large KGs

**Effort**: 2–3 h | **Skill**: intermediate

Export entities and relations as Parquet files for downstream analytics
(Pandas, DuckDB, Spark).  Useful for KGs with >10k entities.

---

### B-022  Ollama native JSON mode

**Effort**: 1–2 h | **Skill**: any

Ollama supports `format: "json"` in the API to guarantee well-formed JSON
output.  Currently we do custom JSON recovery.

**Test**: Compare structured generation success rate with and without
`format: "json"`.  May eliminate the need for retry/recovery logic.

---

### B-023  Static validator (SHACL2FOL) output parsing robustness

**Effort**: 3–4 h | **Skill**: regex / parsing

The Vampire prover output format varies between versions.  The current parser
is fragile.

**Fix**: Write a more robust parser with fallback strategies, or switch to
a more predictable prover output format.

**File**: `src/kgbuilder/validation/static_validator.py`

---

## Dependency Map

```
B-001  (qdrant-client fix)
  └─> B-009  (CI needs installable package)
  └─> B-010  (quickstart needs working install)

B-002  (test fixes)
  └─> B-009  (CI needs green tests)
  └─> B-008  (coverage increase builds on passing tests)

B-003  (deprecation warnings)
  └─> B-014  (part of general lint cleanup)
```

---

## Quick wins (< 1 hour each)

| ID | Description |
|----|-------------|
| B-001 | Fix qdrant-client version in pyproject.toml |
| B-003 | Replace `datetime.utcnow()` with timezone-aware |
| B-011 | Remove completed TODO comments |
| B-013 | Add `.pre-commit-config.yaml` |
| B-015 | Decide on telemetry module (keep/delete) |

---

## Suggested sprint plan

### Sprint 1 (P0 — get CI green)
1. B-001 — Fix pyproject.toml
2. B-002 — Fix all 70 test failures/errors
3. B-003 — Fix deprecation warnings
4. B-009 — Set up GitHub Actions CI

### Sprint 2 (P1 — consolidate)
5. B-004 / B-011b — Remove or implement validator stubs
6. B-005 — Implement RDF store methods
7. B-008 — Add unit tests for untested modules (target 50%)
8. B-010 — Smoke-test quickstart.py

### Sprint 3 (P2 — polish)
9. B-012 — Standardize exceptions
10. B-013 — Pre-commit hooks
11. B-014 — Fix remaining lint issues
12. B-011 — Clean up TODO comments

### Sprint 4 (P3 — research extensions)
13. B-016 — Ablation tooling
14. B-020 — Tutorial notebooks
15. B-017 — Community detection
