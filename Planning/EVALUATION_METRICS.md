# Evaluation Metrics for the KG Construction Paper

> **Purpose**: Define, justify, and locate every metric reported in the paper's
> evaluation section.  All metrics are collected automatically — no manual
> annotation is required unless explicitly noted.

---

## 1. Metric Taxonomy

```
Evaluation Metrics
├── 1. KG Completeness       – how much of the target schema got populated
├── 2. KG Richness           – structural diversity & connectivity
├── 3. KG Quality            – conformance to ontology constraints
├── 4. Convergence           – how the loop improves KG with each iteration
└── 5. Efficiency            – compute cost
```

---

## 2. Completeness Metrics

| Metric | Symbol | Definition | Range | ↑/↓ better | Source |
|---|---|---|---|---|---|
| **Ontology class coverage** | $C_{\text{class}}$ | % of 18 ontology classes with ≥ 1 extracted instance | 0–100 % | ↑ | `kg_metrics.graph_richness.ontology_class_coverage_pct` |
| **Ontology relation coverage** | $C_{\text{rel}}$ | % of 26 ontology relation types used at least once | 0–100 % | ↑ | `kg_metrics.graph_richness.ontology_relation_coverage_pct` |
| **Final discovery coverage** | $C_{\text{disc}}$ | Coverage reported by the IterativeDiscoveryLoop at termination (internal loop metric, same denominator as class coverage) | 0–1 | ↑ | `kg_metrics.final_coverage` |

**Paper argument**: Multi-pass (B) and law-augmented (C) conditions should
reach significantly higher $C_{\text{class}}$ and $C_{\text{rel}}$ than
single-pass (A), directly validating the deep-research-loop hypothesis.

---

## 3. Richness / Structural Metrics

| Metric | Symbol | Definition | Range | ↑/↓ better | Source |
|---|---|---|---|---|---|
| **Entity count** | $\|V\|$ | Total nodes created in Neo4j for this run | ≥ 0 | ↑ | `kg_metrics.nodes` |
| **Relation count** | $\|E\|$ | Total edges created in Neo4j for this run | ≥ 0 | ↑ | `kg_metrics.edges` |
| **Entity type distribution** | — | Instance count per ontology class | — | — | `kg_metrics.graph_richness.entity_type_distribution` |
| **Entity type entropy** | $H_{\text{type}}$ | Shannon entropy of entity type distribution: $-\sum p_i \log_2 p_i$ | 0–$\log_2 18 \approx 4.17$ bits | ↑ | `kg_metrics.graph_richness.entity_type_entropy` |
| **Unique relation types used** | $T_{\text{rel}}$ | Number of distinct edge labels in the extracted graph | 0–26 | ↑ | `kg_metrics.graph_richness.unique_relation_types` |
| **Relation type distribution** | — | Edge count per predicate type | — | — | `kg_metrics.graph_richness.relation_type_distribution` |
| **Relation density** | $\rho$ | $\|E\| / \|V\|$ — edges per node | ≥ 0 | ↑ | `kg_metrics.graph_richness.relation_density` |
| **Average node degree** | $\bar{d}$ | Mean (in + out) degree across all nodes | ≥ 0 | ↑ | `kg_metrics.graph_richness.avg_degree` |
| **Orphan rate** | $r_{\text{orphan}}$ | % nodes with degree 0 (isolated, unconnected) | 0–1 | ↓ | `kg_metrics.graph_richness.orphan_rate` |

**Interpretation matrix for the paper**:

| Condition | Expected pattern |
|---|---|
| A_single_pass — Single-pass (gemma4:e2b) | Low counts, high orphan rate, low entropy (few classes covered) |
| B_multipass — Multi-pass (gemma4:e2b) | Higher counts, lower orphan rate, higher entropy |
| C_multipass_law — Multi-pass + Law (gemma4:e2b) | Highest class/relation coverage; law entities reduce orphan rate |
| D_gemma4b — Multi-pass (gemma4:e4b) | Medium model: between A and E |
| E_gemma31b — Multi-pass (gemma4:31b) | Large model: approaches or exceeds e2b |
| F_nemotron_ablation — Multi-pass (nemotron-nano) | Architecture ablation: different model family |

---

## 4. Quality / Conformance Metrics

| Metric | Symbol | Definition | Range | ↑/↓ better | Source |
|---|---|---|---|---|---|
| **SHACL combined score** | $Q_{\text{SHACL}}$ | Composite score from `KGQualityScorer` (weighted: SHACL conformance + consistency) | 0–1 | ↑ | `kg_metrics.shacl.combined_score` |
| **SHACL violation count** | $n_{\text{viol}}$ | Raw SHACL violations reported against the OWL ontology | ≥ 0 | ↓ | `kg_metrics.shacl.violations` |
| **SHACL class coverage** | — | % of ontology classes with at least one conforming instance | 0–1 | ↑ | `kg_metrics.shacl.class_coverage` |
| **SHACL consistency** | — | Internal consistency score from scorer | 0–1 | ↑ | `kg_metrics.shacl.consistency` |

> **Note**: SHACL evaluation uses `data/ontology/law/law-ontology-v1.0.owl` and
> a sample of up to 500 nodes.  Full-graph SHACL validation is possible via
> `scripts/run_shacl_validation.py` but is too expensive to run per-iteration.

---

## 5. Convergence Metrics

Captured per-iteration in `{run_dir}/iteration_metrics.json`.

| Metric | Definition | Notes |
|---|---|---|
| `entities_discovered_this_iter` | New entities found in this iteration (not previously seen) | Primary convergence signal |
| `total_entities_cumulative` | Running total entities since run start | Shows growth curve |
| `ontology_coverage` | Coverage at end of this iteration | Should plateau → convergence |
| `questions_processed` | Questions asked in this iteration | Measures exploration breadth |
| `new_entity_types` | Set of entity class labels newly instantiated this iteration | Shows schema exploration |
| `processing_time_sec` | Wall-clock time for this iteration | Efficiency per pass |

**Convergence criterion**: The loop terminates when `ontology_coverage ≥ 0.85` or
`max_iterations` is reached (see `benchmark_paper.json`: `max_iterations: 5`).

**Plot**: `scripts/plot_convergence.py` → `convergence_combined.png`,
`convergence_entities.png`, `convergence_coverage.png`

---

## 6. Efficiency Metrics

| Metric | Definition | Source |
|---|---|---|
| **Total build time** | Wall-clock seconds from first LLM call to KG written to Neo4j | `kg_metrics.build_time_seconds` |
| **Iterations to convergence** | Index of last iteration where `new_entity_types` was non-empty | Derived from `iteration_metrics.json` |
| **Entities per second** | `total_entities / build_time_seconds` | Computed at analysis time |

---

## 7. Statistical Comparison (Cross-Condition)

For each scalar metric above, compute across runs (n=3 per condition):

| Statistic | Use |
|---|---|
| **Mean ± std** | Point estimate + variance in all tables and bar charts |
| **Wilcoxon signed-rank test** | Pairwise significance (A vs B, A vs C, B vs C) — non-parametric, n=3 |
| **Cohen's d** | Effect size; $d = (\mu_2 - \mu_1) / \sigma_{\text{pooled}}$ |

See `scripts/statistical_comparison.py` (G8 — to be implemented).

Recommended primary comparisons for the paper:

- **A vs B** — effect of multi-pass loop (controls for model and law graph)
- **B vs C** — effect of law graph augmentation (controls for loop depth)
- **B vs D/E** — effect of model capability at same loop depth

---

## 8. Metrics NOT Used (and Why)

| Metric | Reason excluded |
|---|---|
| **Gold-standard P/R/F1** | Only 1 toy gold annotation file (`doc_001`). Would produce meaningless numbers. Requires 3–5 manually annotated real decommissioning chunks (~1–2 h annotation work). Add in a future revision. |
| **BLEU / ROUGE** | Not applicable — KG construction is not a generative text task. |
| **Link prediction AUC** | Would require holding out a fraction of the true graph; not feasible without ground truth. |
| **CQ-answerability (LLM-judge)** | 9 expert competency questions exist (`data/evaluation/competency_questions.json`). Currently not wired into the benchmark loop — all 9 require the KG to be queryable after construction. Add in a future revision. |

---

## 9. Plots Generated

| File | Script | Description |
|---|---|---|
| `convergence_combined.png` | `scripts/plot_convergence.py` | Coverage + entity growth per iteration, all conditions |
| `convergence_entities.png` | `scripts/plot_convergence.py` | Entity count per iteration |
| `convergence_coverage.png` | `scripts/plot_convergence.py` | Ontology coverage per iteration |
| `richness_bar_comparison.png` | `scripts/plot_richness_comparison.py` | Grouped bars: all richness metrics, conditions A–E |
| `richness_radar_comparison.png` | `scripts/plot_richness_comparison.py` | Spider/radar chart of normalised quality profile |

Run all plots after benchmark completes:

```bash
python scripts/plot_convergence.py \
    --results experiment_results/benchmark_paper \
    --output output/figures

python scripts/plot_richness_comparison.py \
    --results experiment_results/benchmark_paper \
    --output output/figures
```

---

## 10. Recommended Paper Table Layout

```
Table 2: Graph quality metrics across experimental conditions (mean ± std, n=3)

Metric                    A (single)   B (multi)    C (multi+law) D (nano:4b)  E (nano:30b)
─────────────────────────────────────────────────────────────────────────────────────────────
Class coverage (%)        xx.x±x.x    xx.x±x.x     xx.x±x.x      xx.x±x.x    xx.x±x.x
Relation coverage (%)     xx.x±x.x    xx.x±x.x     xx.x±x.x      xx.x±x.x    xx.x±x.x
Entity count              xxx±xx      xxx±xx        xxx±xx        xxx±xx       xxx±xx
Relation count            xxx±xx      xxx±xx        xxx±xx        xxx±xx       xxx±xx
Entity type entropy (bits) x.xx±x.x   x.xx±x.x     x.xx±x.x      x.xx±x.x    x.xx±x.x
Unique relation types     xx±x        xx±x          xx±x          xx±x         xx±x
Avg. degree               x.xx±x.x    x.xx±x.x     x.xx±x.x      x.xx±x.x    x.xx±x.x
Orphan rate               x.xx±x.x    x.xx±x.x     x.xx±x.x      x.xx±x.x    x.xx±x.x
SHACL score               x.xx±x.x    x.xx±x.x     x.xx±x.x      x.xx±x.x    x.xx±x.x
─────────────────────────────────────────────────────────────────────────────────────────────
Bold = best per metric.  ↑ = higher is better, ↓ = lower is better.
* p < 0.05 (Wilcoxon vs condition A);  ** p < 0.01
```
