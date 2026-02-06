# Issues Backlog

## Implementation Status, Next Steps & Nice-to-Haves

**Last Updated**: February 6, 2026

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
| 12 | Semantic Enhancement & Analytics | � In Progress | ~1,500 | OWL-RL inference, SKOS enrichment, embedding-based discovery, graph analytics |

### Current State

- **Working pipeline**: `scripts/run_single_experiment.py` and `scripts/full_kg_pipeline.py`
- **Baseline experiment**: Run on 33 nuclear decommissioning documents, ~280 entities, ~156 relations
- **Known issues**: Ollama timeouts under Docker (~120s reads), JSON parsing from LLM occasionally malformed
- **Recent fixes**: Pydantic retry logic in `generate_structured()`, JSON recovery strategies, persistent response caching, tiered heuristic extraction

---

## 2. Immediate Next Steps (High Priority)

### 2.1 Structured Generation Robustness

**Priority**: 🔴 Critical  
**Status**: Partially complete  
**Effort**: 1-2h remaining

- [x] Add `max_retries` parameter with validation error feedback to LLM
- [x] JSON recovery strategies (brace balancing, truncation, incomplete field removal)
- [x] `model_validate_json()` for unified parsing + validation
- [ ] Consider Ollama's native `format: "json"` parameter for guaranteed JSON output
- [ ] Add schema-specific few-shot examples to extraction prompts
- [ ] Benchmark structured output success rate (target: >95%)

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
**Effort**: 4-6h

- [ ] Implement `KGVersioningService`
  - [ ] `create_snapshot(name, description) → version_id`
  - [ ] `list_versions() → list[VersionMetadata]`
  - [ ] `diff(v1, v2) → VersionDiff`
  - [ ] `restore(version_id)`
- [ ] Auto-version after each pipeline run
- [ ] Track entity/relation additions, deletions, modifications
- [ ] Version metadata: timestamp, trigger, document set hash

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

**Effort**: 12-16h

- [ ] Agent roles:
  - [ ] QuestionAskingAgent — decomposes complex queries
  - [ ] DeepResearchAgent — retrieves + synthesizes evidence
  - [ ] KGBuilderAgent — constructs/updates graph on-the-fly
  - [ ] ValidationAgent — checks answer quality
  - [ ] QAAgent — generates final answers
- [ ] Agent orchestration (LangGraph or custom DAG)
- [ ] Full logging of agent actions and reasoning chains

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

- [ ] Migrate from stdlib `logging` to `structlog`
- [ ] Structured JSON log output
- [ ] Log every LLM call with prompt/response/tokens/latency
- [ ] wandb integration for experiment metrics
- [ ] Dashboard for pipeline health monitoring

### 4.9 Phase 11+: Semantic Enhancement & Post-Construction Analytics

**Rationale**: After baseline validation, enhance constructed KG with semantic closure and analytics capabilities using industry-standard tools.

**Effort**: 8-12h over 2-3 iterations

#### 4.9.1 Inference Layer (KGL + OWL-RL)

- [ ] Integrate KGL's OWL-RL inference to compute transitive closure (e.g., `ancestorOf`, `subClassOf`, `broader`)
- [ ] SKOS hierarchical expansion (`skos:narrower`, `skos:broader` relationships)
- [ ] Automatic axiomatic triple generation for defined properties
- [ ] Conflict detection via `owl:differentFrom` and `owl:sameAs` consolidation
- [ ] Benchmark: measure KG growth (typical: 20-40% triple inflation from transitive closure)

#### 4.9.2 Synonym & Entity Linking (Embeddings)

- [ ] Word2Vec training on entity descriptions (gensim)
- [ ] Compute similarity matrix for all entities
- [ ] Identify missed merges: entities with `sim > 0.85` but not linked
- [ ] Levenshtein distance for variant detection (e.g., "Uranium", "uranium", "U-235")
- [ ] Generate suggestions for human-in-the-loop curation

#### 4.9.3 Community Detection & Clustering

- [ ] iGraph `leiden` algorithm for community structure
- [ ] Identify dense entity clusters (potential missing relations)
- [ ] NetworkX centrality measures (degree, betweenness, closeness)
- [ ] Visualization of cluster hierarchies via PyVis
- [ ] Reports on most important entities per community

#### 4.9.4 KG Measurement & Diagnostics

- [ ] Triple count, node count, edge count growth over iterations
- [ ] Predicate frequency distribution (power-law analysis)
- [ ] Degree distribution (hubs, orphans)
- [ ] Schema coverage: % of entities that are typed vs. untyped
- [ ] Consistency metrics: % of relations that satisfy domain/range constraints  
- [ ] Data quality dashboard (invalid predicates, missing types, orphan entities)

#### 4.9.5 Efficient Serialization & Versioning

- [ ] Parquet export for KG snapshots (10x smaller than JSON-LD)
- [ ] Incremental snapshots: only store deltas from previous iteration
- [ ] Time-travel capability: restore KG to any previous iteration
- [ ] S3/cloud storage integration for snapshot archival
- [ ] Compression strategies: RDF triple compression (brotli/zstd)

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

### Milestone A: Publication-Ready Pipeline (2-3 weeks)
- [ ] Complete enrichment pipeline wiring (§2.2)
- [ ] QA dataset curation (§3.1)
- [ ] Baseline QA metrics computed
- [ ] RAG comparison (classic vs hybrid vs KG-only)
- [ ] Experiment report with convergence analysis

### Milestone B: Full Feature Parity (4-6 weeks)
- [ ] KG versioning (§3.3)
- [ ] FusionRAG (§4.1)
- [ ] Ablation studies (§4.4)
- [ ] Comprehensive test suite (75%+ coverage)

### Milestone C: Production Quality (8-10 weeks)
- [ ] Multi-agent QA system (§4.5)
- [ ] Graph UI (§4.6)
- [ ] CI/CD (§4.7)
- [ ] Documentation & SDK (§4.3)
### Milestone D: Semantic Enhancement & Analytics (Phase 11+, 6-8 weeks)
- [ ] Semantic inference layer (OWL-RL, SKOS)
- [ ] Synonym discovery & entity linking via embeddings
- [ ] Community detection and graph analytics
- [ ] Measurement & diagnostics dashboard
- [ ] Efficient KG versioning and snapshots