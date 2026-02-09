# Issues Backlog

## Implementation Status, Next Steps & Nice-to-Haves

**Last Updated**: February 9, 2026

---

## 1. Implementation Status

### Completed Phases

| Phase | Name | Status | LOC | Key Deliverables |
|-------|------|--------|-----|-----------------|
| 1 | Core Infrastructure | ✅ Done | ~800 | Protocols, models, exceptions, config |
| 2 | Document Processing | ✅ Done | ~1,200 | PDF/DOCX/PPTX loaders, 4 chunking strategies |
| 3 | Entity Extraction | ✅ Done | ~1,500 | LLMEntityExtractor, confidence scoring, Qdrant indexing |
| 4 | Autonomous Discovery | ✅ Done | ~1,100 | Discovery loop, question generator, iterative extraction |
| 5 | Confidence Tuning | ✅ Done | ~1,400 | Analyzer, booster, calibrator, coreference, voter |
| 6 | Relation Extraction | ✅ Done | ~900 | LLMRelationExtractor, domain/range validation, cross-document |
| 7 | KG Assembly & Storage | ✅ Done | ~1,200 | Neo4jGraphStore, RDFStore, multi-store KGBuilder, 5-format export |
| 8 | Validation Pipeline | ✅ Done | ~2,050 | SHACL, rules engine, consistency checker, reporter |
| 9 | QA Evaluation | ✅ Done | ~1,300 | QA datasets, query executor, metrics (F1/accuracy/coverage) |
| 10 | Experiment Framework | ✅ Done | ~3,300 | Manager, analyzer, plotter, reporter, checkpointing |
| 11 | High-Performance Optimizations | ✅ Done | ~1,200 | Caching, Tiered Extraction, Parallelism |
| 12 | Semantic Enhancement & Analytics | ✅ Done | ~1,500 | OWL-RL inference, SKOS enrichment, graph analytics, pipeline integration |

### Current State

- **Working pipeline**: `scripts/run_single_experiment.py` and `scripts/full_kg_pipeline.py`
- **Baseline experiment**: Run on 33 nuclear decommissioning documents, ~280 entities, ~156 relations
- **Known issues**: Ollama timeouts under Docker (~120s reads), JSON parsing from LLM occasionally malformed
- **Recent fixes**: Pydantic retry logic in `generate_structured()`, JSON recovery strategies, persistent response caching, tiered heuristic extraction

---

## 2. Immediate Next Steps (High Priority)

### 2.1 Structured Generation Robustness

**Priority**: 🔴 Critical  
**Status**: ✅ Complete  
**Effort**: Done

- [x] Add `max_retries` parameter with validation error feedback to LLM
- [x] JSON recovery strategies (brace balancing, truncation, incomplete field removal)
- [x] `model_validate_json()` for unified parsing + validation
- [x] Add schema-specific few-shot examples to extraction prompts (entity.py + relation.py)
- [x] Benchmark structured output success rate via `StructuredGenerationBenchmark`
- [ ] Consider Ollama's native `format: "json"` parameter for guaranteed JSON output

### 2.2 Enrichment Pipeline Integration

**Priority**: 🔴 Critical  
**Status**: ✅ Complete (fully wired)  
**Effort**: 4-6h (Done)

Fully implemented enrichment pipeline:

- [x] Implement `SemanticEnrichmentPipeline` class in `src/kgbuilder/enrichment/pipeline.py`
  - [x] Phase 1: `DescriptionEnricher` — LLM generates descriptions per entity
  - [x] Phase 2: `EmbeddingEnricher` — 384-dim embeddings via Ollama
  - [x] Phase 3: `CompetencyQuestionEnricher` — 3-5 CQs per entity
  - [x] Phase 4: `TypeConstraintEnricher` — semantic type compatibility
  - [x] Phase 5: `AliasEnricher` — synonyms, abbreviations
- [x] Wire enrichment into `full_kg_pipeline.py` between discovery and assembly
- [x] Add enrichment metrics to experiment reports
- [x] Enrichment output stored in `self.enriched_entities`, `self.enriched_relations`

### 2.3 Checkpoint-Based Re-Enrichment Flow

**Priority**: 🔴 Critical  
**Status**: ✅ Complete (fully wired)  
**Effort**: 2-3h (Done)

Fully implemented checkpoint CLI and re-enrichment:

- [x] CLI module: `src/kgbuilder/pipeline/checkpoint_cli.py`
  - [x] `enrich_from_checkpoint(path)` function for standalone enrichment
  - [x] Load checkpoint → run enrichment → optional persist
- [x] Wired into `full_kg_pipeline.py`:
  - [x] `--enrich-only` flag for checkpoint-based re-enrichment mode
  - [x] `--checkpoint <path>` argument to specify checkpoint file
  - [x] `--skip-enrichment` flag to skip enrichment phase
  - [x] `_enrich_from_checkpoint()` method for standalone enrichment
  - [x] `_run_enrichment()` method for pipeline enrichment
- [x] CheckpointManager integrated for loading/saving

### 2.4 Ollama Timeout & Reliability

**Priority**: 🔴 Critical  
**Status**: ✅ Complete  
**Effort**: 2-3h (Done)

---

## 3. Near-Term Tasks (Medium Priority)

### 3.1 QA Evaluation Dataset Curation

**Priority**: 🟡 Medium  
**Effort**: 4-6h (manual + automated)

- [ ] Create benchmark QA dataset for nuclear decommissioning domain
  - [ ] 50+ questions with expected answers
  - [ ] Mix of entity, relation, count, and boolean queries
  - [ ] Difficulty levels 1-5
  - [ ] Map to competency questions
- [ ] Validate dataset against current KG
- [ ] Compute baseline QA metrics

### 3.2 RAG Comparison Framework (Phase 12)

**Priority**: 🟡 Medium  
**Effort**: 12-16h

- [ ] Implement 3 RAG architecture variants:
  - [ ] `ClassicRAG` — Vector retrieval only (Qdrant)
  - [ ] `HybridRAG` — Vector + KG subgraph retrieval
  - [ ] `KGOnlyRAG` — Pure graph traversal
- [ ] Shared evaluation harness (same QA dataset, same metrics)
- [ ] Comparative analysis: latency, accuracy, faithfulness, coverage
- [ ] Ablation: with/without ontology guidance, different models, CQ variants

### 3.3 KG Versioning Service

**Priority**: 🟡 Medium  
**Status**: ✅ Complete  
**Effort**: Done

- [x] Implement `KGVersioningService` in `src/kgbuilder/versioning/service.py`
  - [x] `create_snapshot(name, description) → version_id`
  - [x] `list_versions() → list[VersionMetadata]`
  - [x] `diff(v1, v2) → VersionDiff`
  - [x] `restore(version_id)`
- [x] Auto-version after each pipeline run
- [x] Track entity/relation additions, deletions, modifications
- [x] Version metadata: timestamp, trigger, content hashing

### 3.4 Configuration Management Overhaul

**Priority**: 🟡 Medium  
**Status**: ✅ Complete  
**Effort**: 3-4h (Done)

- [x] Migrate from JSON configs to YAML/Pydantic with Environment variable support
- [x] Support for `.env` files and hierarchical overrides
- [x] CLI flags for `top-k`, `follow-ups`, `max-iterations`, etc.
- [x] Clear error messages on config validation failure

### 3.5 Interface Naming & Protocol Cleanup

**Priority**: 🟡 Medium  
**Status**: ✅ Complete  
**Effort**: 2-3h (Done)

- [x] Standardize on `properties` across all models
- [x] Fix `Neo4jGraphStore` protocol gaps (`get_all_nodes`, `get_all_edges`)
- [x] Alignment of `top_k_docs` and `confidence_threshold` names
- [x] Standardize `Evidence` fields

### 3.6 High-Performance Extraction Tiers

**Priority**: 🔴 Critical  
**Status**: ✅ Complete  
**Effort**: 6-8h (Done)

- [x] Implement `OllamaProvider` persistent disk cache ([.cache/ollama/](.cache/ollama/))
- [x] Implement `TieredExtractor` (Deterministic Rules -> LLM fallback)
- [x] Implement `TieredRelationExtractor` (Proximity Rules -> LLM fallback)
- [x] Implement Parallel Question Processing in `DiscoveryLoop` (ThreadPoolExecutor)
- [x] Point-based check for skipping redundant vector indexing

---

## 4. Nice-to-Have Features (Lower Priority)

### 4.1 FusionRAG Multi-Strategy Retrieval

**Effort**: 8-12h

- [ ] Implement multi-strategy retrieval pipeline
  - [ ] Dense vector retrieval (existing)
  - [ ] Sparse/BM25 retrieval
  - [ ] KG-guided entity expansion
  - [ ] Reciprocal Rank Fusion (RRF)
- [ ] Cross-encoder re-ranking
- [ ] Adaptive strategy selection based on query type

### 4.2 Advanced Document Processing

**Effort**: 6-8h

- [ ] `AdvancedDocumentProcessor` — unified pipeline with:
  - [ ] Table extraction from PDFs
  - [ ] VLM (Vision-Language Model) for image/diagram analysis
  - [ ] Language detection
  - [ ] Progressive loading for large documents
  - [ ] Processing cache with content hashing

### 4.3 Documentation & SDK (Phase 11)

**Effort**: 8-12h

- [ ] API documentation (auto-generated from docstrings)
- [ ] Tutorial notebooks (Jupyter)
- [ ] SDK for external consumers (simplified API)
- [ ] Architecture decision records (ADRs)

### 4.4 Ablation Study Tooling

**Effort**: 4-6h

- [ ] With/without specific ontology classes
- [ ] With/without CQ groups
- [ ] Different chunking strategies
- [ ] Different embedding models
- [ ] Different LLM models (Qwen3 vs Llama3.1 vs Mistral)
- [ ] Automated ablation runner + comparison reports

### 4.5 Multi-Agent QA System

**Status**: ➡️ Moved to [GraphQAAgent](https://github.com/DataScienceLabFHSWF/GraphQAAgent)  
**Effort**: 12-16h

This is now a separate repository. See [Planning/C3_*.md](.) for blueprints.

- [ ] Agent roles: QuestionParser, ContextAssembler, AnswerGenerator, Explainer
- [ ] Multiple retrieval strategies: Vector, Graph, Hybrid FusionRAG
- [ ] Ontology-informed query expansion
- [ ] Full evaluation framework (accuracy, faithfulness, strategy comparison)

### 4.6 Graph UI & Exploration

**Effort**: 8-12h

- [ ] Web-based graph explorer (Neo4j Browser integration or custom)
- [ ] Entity/relation inspection with provenance
- [ ] Subgraph highlighting for QA explanations
- [ ] Query builder with natural language interface

### 4.7 CI/CD & Testing

**Effort**: 4-6h

- [ ] GitHub Actions pipeline (lint, type-check, test)
- [ ] Pre-commit hooks (ruff, black, mypy)
- [ ] Integration tests with Docker Compose
- [ ] Test coverage target: 75%+ overall
- [ ] Performance regression tests

### 4.8 Structured Logging & Observability

**Effort**: 3-4h  
**Status**: ✅ Complete

- [x] Migrate from stdlib `logging` to `structlog` (`logging_config.py`)
- [x] Structured JSON log output
- [x] Log every LLM call with prompt/response/tokens/latency (`LLMCallTracker`)
- [x] wandb integration for experiment metrics
- [x] Pipeline health monitoring (`PipelineHealthMonitor`)

### 4.9 Semantic Enhancement & Post-Construction Analytics

**Status**: ✅ Core complete (analytics pipeline integrated)  
**Effort**: Remaining items are stretch goals

#### 4.9.1 Inference Layer — ✅ Done

- [x] OWL-RL inference via `Neo4jInferenceEngine` (`analytics/inference.py`)
- [x] SKOS enrichment (`analytics/skos.py`)
- [x] Graph metrics (node/edge counts, typed coverage, centrality) (`analytics/metrics.py`)
- [x] Analytics pipeline orchestrator (`analytics/pipeline.py`)
- [x] Integrated into `full_kg_pipeline.py` with `--skip-analytics` flag

#### 4.9.2–4.9.5 — Remaining Stretch Goals

- [ ] Embedding-based synonym discovery & entity linking
- [ ] Community detection (Leiden/iGraph)
- [ ] Data quality dashboard
- [ ] Parquet export & incremental snapshots

---

## 5. Known Technical Debt

| Issue | Severity | Location | Description |
|-------|----------|----------|-------------|
| Duplicate docstring in `generate()` | Low | `embedding/ollama.py` | Fixed Feb 6 |
| `re` imported inside method | Low | `embedding/ollama.py` | Move to top-level import |
| Missing `__all__` exports | Medium | Multiple `__init__.py` | Define public API per module |
| Inconsistent error types | Medium | Extraction modules | Some raise `RuntimeError`, others `ValueError` |
| Test coverage gaps | Medium | validation/, evaluation/ | Need unit tests for validators and evaluators |
| `eval()` for arithmetic | Low | `extraction/entity.py` | Safe but could use `ast.literal_eval` |
| Missing type hints | Low | Some older modules | Add complete annotations |

---

## 6. Milestone Targets

### Milestone A: Publication-Ready Pipeline — ✅ Achieved
- [x] Complete enrichment pipeline wiring (§2.2)
- [x] Structured generation robustness (§2.1)
- [x] KG versioning (§3.3)
- [x] Structured logging & observability (§4.8)
- [x] Semantic enhancement & analytics (§4.9)
- [ ] QA dataset curation (§3.1) → moved to [GraphQAAgent](https://github.com/DataScienceLabFHSWF/GraphQAAgent)
- [ ] RAG comparison → moved to [GraphQAAgent](https://github.com/DataScienceLabFHSWF/GraphQAAgent)

### Milestone B: Sibling Repos (next)
- [ ] Scaffold [GraphQAAgent](https://github.com/DataScienceLabFHSWF/GraphQAAgent) (blueprints: `Planning/C3_*.md`)
- [ ] Scaffold [OntologyExtender](https://github.com/DataScienceLabFHSWF/OntologyExtender) (blueprints: `Planning/C1_*.md`)
- [ ] FusionRAG retrieval comparison (C3.3 + C3.5)
- [ ] HITL ontology extension workflow (C1)

### Milestone C: Production Quality
- [ ] CI/CD (§4.7)
- [ ] Graph UI (§4.6)
- [ ] Comprehensive test suite (75%+ coverage)
- [ ] End-to-end evaluation across all three repos