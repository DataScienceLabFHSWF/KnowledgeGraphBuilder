# Implementation Roadmap

> Last updated: 2026-02-16
>
> Current state: 375 tests passing, ~34.8k LOC, 126 Python files.
> All P0 blockers from the original backlog are resolved.
>
> **Scope:** Build the KG, validate with SHACL + graph metrics, evaluate
> quality. HybridRAG / retrieval is handled in a separate repository.

---

## Status Overview

| Area | Status | Notes |
|------|--------|-------|
| Core / Models / Protocols | **Complete** | Deterministic hash IDs, type hints throughout |
| Document Processing | **Complete** | PDF, DOCX, PPTX; 4 chunking strategies |
| Extraction (Entity + Relation) | **Complete** | LLM + rules + legal ensemble |
| Enrichment (5-phase) | **Complete** | Descriptions, embeddings, CQs, type constraints, aliases |
| Assembly | **Complete** | Multi-store (Neo4j + RDF), batch ops, idempotent MERGE |
| Storage (Neo4j, RDF, Qdrant) | **Complete** | Export: JSON-LD, YARRRML, RDF, DCAT, JSON |
| Validation infrastructure | **Complete** | pyshacl, SHACL2FOL, rules engine, consistency checker |
| SHACL shapes (hand-crafted) | **Missing** | Zero shape files exist; auto-generator produces trivial shapes |
| Consistency rules (domain) | **Wrong domain** | Hardcoded Person/Org rules, not nuclear/law |
| Analytics (structural + embeddings) | **Complete** | Centrality, community, GraphSAGE, interactive Plotly |
| Cross-domain Linking | **Complete** | 3-tier strategy, integrated in pipeline (Phase 6.5) |
| Experiment Framework | **Complete** | Variants, checkpoints, analysis, plotting |
| Gold Standard Dataset | **Insufficient** | 9 CQs, 0 annotated docs, 0 ER pairs |
| Pipeline Orchestrator | **Stub core** | Iteration loop works, core steps return mocks |
| Entity Resolution | **Partial** | Edit-distance only; no embedding-based ER |
| Statistical Rigor | **Missing** | No CI, no KS test, no NMI, no baseline modularity |
| CI/CD | **Not started** | |
| Test Coverage | **~16%** | Target 50%+ |

---

## Phase 1 — Scientific Metrics Hardening (est. 2–3 days)

**Goal:** Make every quantitative claim in the thesis defensible with
proper statistical support.

| Task | Effort | Details |
|------|--------|---------|
| KS goodness-of-fit for power-law | S | Use `powerlaw` package; report p-value alongside α |
| NMI community–ontology alignment | S | `sklearn.metrics.normalized_mutual_info_score(community, type)` |
| Random baseline modularity | S | Configuration model null hypothesis for modularity comparison |
| Small-world coefficient σ | S | `C/C_rand ÷ L/L_rand`; currently declared but never computed |
| Confidence intervals via bootstrap | M | 1000-resample bootstrap for key metrics |
| Per-type degree distribution | S | Degree stats split by entity type, not aggregate |

**Why first:** These are low-effort, high-impact fixes. A thesis committee
will immediately ask "is this statistically significant?" and right now the
answer is "we didn't test."

---

## Phase 2 — SHACL Shapes & Domain Validation Rules (est. 3–5 days)

**Goal:** The validation pipeline is fully built but has no real shapes
to validate against. Fill it.

| Task | Effort | Who | Details |
|------|--------|-----|---------|
| Create `law-shapes.ttl` | L | **Colleague** | 13 classes, cardinality, patterns, disjointness |
| Create `domain-shapes.ttl` | M | **Colleague** | 12 decommissioning classes with property constraints |
| Fix `_FileOntologyService` | S | Dev | `scorer.py` L107–113 returns empty → shapes are useless |
| Fix `SHACLShapeGenerator` | M | Dev | Implement `rdfs:subClassOf` → `sh:node`, `owl:someValuesFrom` → `sh:minCount` |
| Replace hardcoded consistency rules | S | **Colleague** | Domain type pairs + functional properties |
| Auto-generate `DomainRangeRule` | S | Dev | `rules_engine.py` `from_ontology_service()` reads `rdfs:domain`/`rdfs:range` |
| Add `sh:severity` levels | S | **Colleague** | Violation vs Warning vs Info per constraint |

See `Planning/CONTRIBUTION_GUIDE.md` Areas 1, 3, 4, 5 for detailed specs
that colleagues can work from.

---

## Phase 3 — Gold Standard & Extraction Evaluation (est. 5–7 days)

**Goal:** Move from "the pipeline runs" to "the pipeline produces correct
results" with measurable extraction P/R/F1.

| Task | Effort | Who | Details |
|------|--------|-----|---------|
| Annotate 3–5 reference documents | L | **Colleague** | Entity spans, types, relations as JSON |
| Expand competency questions to 50+ | M | **Colleague** | SPARQL + expected results per CQ |
| Create entity resolution pairs | M | **Colleague** | Which extracted entities = same real-world thing |
| Implement extraction P/R/F1 evaluator | M | Dev | Compare extracted entities/relations vs gold standard |
| Replace bag-of-words Jaccard similarity | S | Dev | Use embedding cosine instead (`evaluation/metrics.py`) |
| Per-extractor ablation metrics | M | Dev | Track which extractor found which entities |
| Automated experiment sweep runner | M | Dev | Config YAML → parameter grid → results table |

**Why essential:** Without a gold standard, the thesis cannot make claims
about extraction quality. This is the single most impactful contribution
colleagues can make.

---

## Phase 4 — Embedding-Based Entity Resolution (est. 3–4 days)

**Goal:** Reduce 271 connected components toward the theoretical minimum.

| Task | Effort | Details |
|------|--------|---------|
| Build `EntityResolver` service | M | Embedding cosine + edit distance + type matching |
| Store entity embeddings during build | M | Persist 384-dim vectors as Neo4j node properties |
| Add merge/redirect logic in Neo4j | M | Preserve provenance when merging duplicate nodes |
| Add ER phase to orchestrator | S | After synthesis, before relation extraction |
| Evaluate: component count before/after | S | Automated metric in analytics |

**Evidence this matters:** Current synthesizer uses only string edit
distance — semantically identical entities with different labels
("Kernbrennstoff" vs "nuklearer Brennstoff") are never merged.

---

## Phase 5 — Wire the Orchestrator (est. 2–3 days)

**Goal:** Connect `BuildPipeline` stubs to real implementations.

| Task | Effort | Details |
|------|--------|---------|
| Wire `_extraction_step()` | M | Delegate to `IterativeDiscoveryLoop` + `LLMRelationExtractor` |
| Wire `_validation_step()` | S | Delegate to `ConsistencyChecker` + `SHACLValidator` |
| Wire `_cq_checking_step()` | S | Implement `CompetencyQuestionValidator` using enrichment CQ data |
| Add `_law_linking_step()` | S | Call `KGLawLinker.create_links()` after extraction |
| Deprecate `full_kg_pipeline.py` | S | Thin wrapper that calls `BuildPipeline.run()` |

---

## Phase 6 — Test Coverage & CI/CD (est. 2–3 days)

| Task | Effort | Details |
|------|--------|---------|
| Integration tests for linking module | S | Test `KGLawLinker` with test Neo4j |
| Tests for orchestrator (when wired) | M | End-to-end with mocked LLM |
| GitHub Actions workflow | M | Lint (ruff), type-check (mypy), test (pytest), coverage |
| Pre-commit hooks config | S | `.pre-commit-config.yaml` with ruff + mypy |
| Coverage badge in README | S | `coverage.xml` → badge |

---

## Backlog

| ID | Item | Effort |
|----|------|--------|
| B-009 | Table extraction from PDFs | L |
| B-010 | VLM-based diagram understanding | L |
| B-011 | Named entity linking to Wikidata/DBpedia | M |
| B-013 | Incremental KG updates (append, not rebuild) | L |
| B-015 | Multi-language support (EN+DE) | M |
| B-019 | Federated SPARQL across Neo4j + Fuseki | L |
| B-022 | LangSmith / OpenTelemetry integration | M |

---

## Colleague Contribution Summary

Colleagues can contribute to **Phases 2 and 3** without touching any Python
code — the deliverables are Turtle files, JSON annotations, and SPARQL queries:

| Deliverable | Format | Expertise Needed | Phase |
|-------------|--------|-----------------|-------|
| Law SHACL shapes | `.ttl` | SHACL + German law | 2 |
| Domain SHACL shapes | `.ttl` | SHACL + nuclear decommissioning | 2 |
| Consistency checker rules | Python dict | Domain knowledge | 2 |
| OWL property characteristics | `.owl` edits | OWL ontology | 2 |
| Annotated reference documents | JSON | Domain knowledge | 3 |
| Competency questions + SPARQL | JSON | SPARQL + domain | 3 |
| Entity resolution pairs | JSON | Domain knowledge | 3 |

See **[CONTRIBUTION_GUIDE.md](CONTRIBUTION_GUIDE.md)** for detailed specs.

---

## Recommended Execution Order

1. **Phase 1** (statistical rigor) — 2 days, solo, unblocks defensible claims
2. **Phase 2** (SHACL shapes) — hand off to colleagues immediately, dev fixes in parallel
3. **Phase 3** (gold standard) — hand off to colleagues, dev builds evaluation tooling
4. **Phase 4** (entity resolution) — biggest structural improvement
5. **Phase 5** (orchestrator) — code quality, single entry point
6. **Phase 6** (CI/CD) — long-term maintainability
