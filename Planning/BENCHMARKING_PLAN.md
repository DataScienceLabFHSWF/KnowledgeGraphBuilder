# Benchmarking Plan — Nuclear Decommissioning KG Paper

**Date**: 2026-03-19  
**Domain**: Nuclear decommissioning (33 German PDFs, ~126 MB)  
**Ontology**: law-ontology-v1.0.owl + decommissioning classes (~28 ontology classes)

---

## 1. What Are We Comparing Against?

There is no "standard benchmark" for ontology-guided iterative KG construction from domain PDFs.
We define our own baselines and compare **internally** (ablation-style). The comparison axes are:

| Condition | What it proves |
|-----------|---------------|
| **Single-pass extraction** (max_iterations=1) | Baseline — what a naive "extract once" approach yields |
| **Multi-pass with shallow questions** (existence-only, max_iterations=5) | Shows value of iteration alone |
| **Multi-pass with deep questions** (existence + relations + cross-entity, max_iterations=5) | Shows value of question depth/quality |
| **Multi-pass + law graph context** (deep questions + LAW_GRAPH_ENABLED=true) | Shows value of external knowledge augmentation |

Additionally, if time allows:

| External reference | Purpose |
|---|---|
| **Manual expert KG** (gold standard) | Upper-bound quality reference |
| **Naive RAG → LLM dump** (single prompt, no ontology guidance) | Lower-bound: what happens without structure |

### Why Not Compare Against Other KG-Building Systems?

- No directly comparable system operates on German legal/nuclear PDFs with an OWL ontology
- Published KG benchmarks (FB15k, WN18RR) are link prediction tasks, not construction
- The closest related work (REBEL, DeepKE, GraphRAG) target different settings (English, open-domain, sentence-level)
- **Our contribution is the iterative ontology-guided loop itself** — the right comparison is "with vs. without" our key components

---

## 2. Experiment Design

### 2.1 Main Experiment: 5 Conditions × 3 Runs

Each run uses the same document set and ontology. `num_runs=3` for variance estimation.
Two orthogonal ablations: **iteration count + law graph augmentation** (A/B/C) and
**model size** (B/D/E), allowing the paper to clearly attribute gains to each factor.

| ID | Condition | Model | max_iter | law_graph | Est. time/run |
|----|-----------|-------|----------|-----------|---------------|
| **A** | Single-pass baseline | qwen3:8b | 1 | OFF | ~15–25 min |
| **B** | Multi-pass (no law) | qwen3:8b | 5 | OFF | ~60–90 min |
| **C** | Multi-pass + law graph | qwen3:8b | 5 | ON | ~70–100 min |
| **D** | Multi-pass, small model | nemotron-3-nano:4b | 5 | OFF | ~40–70 min |
| **E** | Multi-pass, large model | nemotron-3-nano:30b | 5 | OFF | ~90–150 min |

**Total: 5 × 3 = 15 runs ≈ 10–18 hours** (sequential on single Ollama instance)

> If runtime is too long, drop to `num_runs=2` (10 runs ≈ 7–12 hours).

**Narrative for D/E**: Conditions B, D, E share identical settings — only the model differs.
This directly answers: *"Does a larger/different model family yield more complete KGs
under multi-pass iterative extraction?"*  D uses the efficient 4B Nemotron-Nano; E uses
the 30B variant. Compare B↔D↔E on entity count, ontology coverage, and CQ-answerability.

### 2.2 Secondary Ablation (if budget allows): Iteration Convergence

Single condition B or C, but track **per-iteration** metrics to plot convergence curves:

| Iteration | New entities | New relations | Ontology coverage | Marginal gain |
|-----------|-------------|---------------|-------------------|---------------|
| 1 | ... | ... | ... | — |
| 2 | ... | ... | ... | Δ from iter 1 |
| ... | ... | ... | ... | ... |

This is the key plot for showing "deeper questions across iterations find new things."
Since question generation targets under-covered classes and generates relational/cross-entity
questions automatically, later iterations naturally produce more sophisticated queries.

---

## 3. Metrics to Report

### 3.1 Primary Metrics (Table 1 in paper)

| Metric | How | Why |
|--------|-----|-----|
| **Ontology class coverage %** | unique entity types / total ontology classes | Completeness |
| **Relation coverage %** | discovered relation types / ontology relations | Structural completeness |
| **Total entities** | count after dedup | Size |
| **Total edges** | count | Connectivity |
| **Avg entity confidence** | mean over all entities | Extraction quality |
| **CQ answerability** | % of 9 competency questions answerable | Functional quality |
| **Build time (sec)** | wall-clock | Practicality |

### 3.2 Graph Structural Metrics (Table 2)

| Metric | Tool | Interpretation |
|--------|------|----------------|
| **Graph density** | NetworkX | How connected |
| **Connected components** | NetworkX | Fragmentation |
| **Avg degree** | NetworkX | Entity connectivity |
| **Clustering coefficient** | NetworkX | Local structure |
| **Small-world σ** | statistical.py | Graph topology character |

### 3.3 Per-Iteration Convergence (Figure 1)

- X-axis: iteration number (1–5)
- Y-axis: cumulative ontology coverage, entity count, new-entities-per-iteration
- One line per condition (A at iter 1 only, B and C across iterations)
- **This is the money plot** — shows diminishing but nonzero marginal gains

### 3.4 Law Graph Impact (Table 3)

- Condition B vs. C side-by-side
- Additional: # law-linked edges, # new entity types discovered with law context
- Confidence distribution shift (box plot)

---

## 4. Statistical Rigor

### 4.1 With 3 Runs Per Condition

- **Report mean ± std** for all metrics
- **Bootstrap 95% CI** on key metrics (coverage, entity count, F1 if gold standard available)
  - Already implemented in `analytics/statistical.py` (1000 resamples)
- **Effect size**: Cohen's d between conditions A↔B, B↔C
- **Paired comparison**: Wilcoxon signed-rank test (n=3 is tiny, so also report raw numbers)

### 4.2 Acknowledge Limitations

- n=3 is small — report individual run values, not just means
- LLM outputs are non-deterministic (Ollama temperature>0) — this IS part of what we measure
- No external gold standard KG for the nuclear domain → we measure **internal consistency** and **ontology coverage** rather than precision/recall against ground truth

### 4.3 What Would Make It More Rigorous (but costs too much time)

- n=5+ runs (15–30 hours)
- Multiple annotators creating gold KGs for precision/recall
- Multiple LLM backends (qwen3, llama3, mistral) — full factorial would be 12+ conditions
- Cross-domain validation (run on a second domain)

---

## 5. Implementation Gaps — What Needs to Be Done Before Running

### 5.1 CRITICAL (must fix)

| # | Gap | Location | Effort |
|---|-----|----------|--------|
| **G1** | **Per-iteration metrics logging** — currently only final metrics are saved. Need to capture entities/relations/coverage at each iteration and write to `iter_001.json`, `iter_002.json`, etc. | `discovery_loop.py`, `manager.py` | ~2–3 hours |
| **G2** | **FusionRAGRetriever instantiation** — previous runs failed. Verify the `qdrant_store` param name is correct in ALL code paths (manager.py, full_kg_pipeline.py). Do a smoke test. | `manager.py`, retrieval code | ~1 hour |
| ~~**G3**~~ | ~~Question depth control~~ — **NOT NEEDED**: `QuestionGenerationAgent` already generates all question types (existence, relations, cross-entity) at every iteration. The difference between conditions A/B comes from iteration count, not question filtering. | — | — |
| **G4** | **Experiment config for 4-condition benchmark** — create the JSON experiment config with all conditions and correct parameters | New config file | ~30 min |
| **G5** | **Build full law graph** — currently only 6 laws in linker, but 17 downloaded in `data/law_html/`. Need to run `build_law_graph.py` with all 17 laws and verify completeness. One-time build. | `scripts/build_law_graph.py` | ~1–2 hours |

### 5.2 IMPORTANT (for paper quality)

| # | Gap | Location | Effort |
|---|-----|----------|--------|
| **G6** | **Gold standard annotations** — only 1 example exists. Need 3–5 annotated documents for entity/relation P/R/F1. Even a small sample adds credibility. | `data/evaluation/gold_standard/` | ~4–8 hours (manual annotation work) |
| **G7** | **Convergence curve plotting** — need a script to read per-iteration JSONs and produce the convergence plot | `scripts/` or `experiment/plotter.py` | ~1–2 hours |
| **G8** | **Statistical comparison script** — Wilcoxon test + Cohen's d across conditions | `scripts/` or `evaluation/` | ~1–2 hours |
| **G9** | **LLM seed propagation** — Ollama supports `seed` param. Pass it through for better reproducibility (won't be perfect but reduces variance). | `extraction/chains.py`, LLM calls | ~1 hour |

### 5.3 NICE-TO-HAVE

| # | Gap | Effort |
|---|-----|--------|
| **G10** | W&B dashboard setup for live monitoring | ~1 hour |
| **G11** | Naive RAG baseline (no ontology, single prompt) for lower-bound comparison | ~3 hours |

---

## 6. Recommended Execution Order

```
Day 1 — Fix & prepare
  1. Manual ontology review (domain + law ontology sufficiency check)
  2. Build full law graph with all 17 laws (G5)         ~1-2h
  3. Fix G2 (FusionRAGRetriever smoke test)             ~1h
  4. Implement G1 (per-iteration metrics logging)       ~2h
  5. Create G4 (experiment config)                      ~30min
  6. Smoke test: run condition A (1 iteration) end-to-end

Day 2 — Run experiments
  7. Launch 9 runs (sequential, ~5-9h)
  8. Start G6 (gold standard annotation) in parallel    manual work

Day 3 — Analysis & plots
  9. Implement G7 (convergence plot)                    ~1h
  10. Implement G8 (statistical comparison)             ~1h
  11. Generate all tables and figures
  12. Run G6 evaluation if annotations ready
```

---

## 7. Proposed Experiment Config

```json
{
  "name": "Nuclear Decommissioning Benchmark",
  "description": "3-condition benchmark: single-pass, multi-pass, multi-pass+law",
  "output_dir": "experiment_results/benchmark_paper",
  "num_runs": 3,
  "seed": 42,
  "variants": [
    {
      "name": "A_single_pass",
      "description": "Single iteration, no law graph",
      "params": {
        "model": "qwen3:8b",
        "max_iterations": 1,
        "questions_per_class": 3,
        "similarity_threshold": 0.85,
        "confidence_threshold": 0.6,
        "law_graph_enabled": false
      }
    },
    {
      "name": "B_multipass",
      "description": "5 iterations, no law graph",
      "params": {
        "model": "qwen3:8b",
        "max_iterations": 5,
        "questions_per_class": 3,
        "similarity_threshold": 0.85,
        "confidence_threshold": 0.6,
        "law_graph_enabled": false
      }
    },
    {
      "name": "C_multipass_law",
      "description": "5 iterations, law graph context augmentation",
      "params": {
        "model": "qwen3:8b",
        "max_iterations": 5,
        "questions_per_class": 3,
        "similarity_threshold": 0.85,
        "confidence_threshold": 0.6,
        "law_graph_enabled": true
      }
    }
  ],
  "evaluation": {
    "qa_dataset_path": "data/evaluation/competency_questions.json",
    "gold_standard_path": "data/evaluation/gold_standard/",
    "metrics": [
      "ontology_class_coverage",
      "relation_coverage",
      "entity_count",
      "edge_count",
      "avg_confidence",
      "cq_answerability",
      "graph_density",
      "connected_components",
      "avg_degree",
      "clustering_coefficient",
      "build_time_seconds"
    ],
    "per_iteration_tracking": true,
    "similarity_threshold": 0.8
  }
}
```

---

## 8. Expected Paper Narrative

> **Story**: A single extraction pass misses many ontology classes and relationships.
> Iterating with targeted questions — which automatically become deeper and more relational
> as coverage grows — progressively fills gaps (convergence curve). The question generator
> targets under-covered classes first, then generates cross-entity and relational questions
> in later iterations when simple existence is already covered.
> Augmenting with a law knowledge graph further improves coverage of regulatory relationships.

### Key Claims to Support with Data

1. **Multi-pass > single-pass**: A vs. B — expect +30–60% ontology coverage, more cross-type edges
2. **Law graph augmentation helps**: B vs. C — expect higher regulatory entity coverage, more law-linked edges
3. **Diminishing but nonzero returns**: convergence curve shows most gain in iterations 1–3, but iterations 4–5 still discover new entities (especially relational/cross-entity ones)
4. **Statistical reliability**: bootstrap CIs show effects are consistent across runs

---

## 9. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Runs take too long (>12h total) | Drop to num_runs=2, or reduce max_iterations to 3 |
| LLM variance too high (noisy results) | Report individual runs + bootstrap CI, propagate Ollama seed |
| No visible difference A vs B | Show qualitative analysis: what types of entities/relations later iterations find that iteration 1 misses |
| Pipeline crashes mid-experiment | Checkpoint after each run (already implemented via run_metadata.json) |
| Ontology too small for meaningful coverage metric | Report absolute counts alongside percentages |
