# Phase 1 — Statistical Metrics: Implementation Guide

> Module: `src/kgbuilder/analytics/statistical.py` (IMPLEMENTED)  
> Tests: `tests/unit/test_statistical.py` (IMPLEMENTED)  
> Status: **All 6 metrics implemented and wired into `run_structural_analysis`**

---

## What Was Built

### New Module: `statistical.py`

Six scientific rigor metrics, each as a standalone function + dataclass result:

| # | Function | Result Dataclass | Purpose |
|---|----------|-----------------|---------|
| 1 | `power_law_test(G)` | `PowerLawResult` | KS goodness-of-fit for degree distribution |
| 2 | `community_ontology_nmi(G, mapping)` | `NMIResult` | How well communities match ontology types |
| 3 | `baseline_modularity(G, partition)` | `BaselineModularityResult` | Modularity vs configuration-model random |
| 4 | `small_world_sigma(G)` | `SmallWorldResult` | σ = (C/C_rand) / (L/L_rand) |
| 5 | `bootstrap_ci(G, metric_fn)` | `BootstrapCI` | Confidence intervals via edge resampling |
| 6 | `per_type_degree_stats(G)` | `PerTypeDegreeStats` | Degree distribution per entity type |
| — | `run_statistical_analysis(G, ...)` | `StatisticalAnalysis` | Runs all 6 in one call |

### Integration

- `run_structural_analysis()` now calls `run_statistical_analysis()` automatically
- `StructuralAnalysis.statistical` holds the full `StatisticalAnalysis` result
- `TopologyResult` gains `power_law_ks_p` and `power_law_plausible` fields
- `small_world_sigma` is now actually computed (was declared but empty)

---

## Architecture

```
structural.py                    statistical.py
─────────────                    ──────────────
run_structural_analysis()  ──►  run_statistical_analysis()
  ├─ compute_topology()           ├─ power_law_test()
  ├─ compute_centralities()       ├─ community_ontology_nmi()
  ├─ detect_communities()         ├─ baseline_modularity()
  ├─ find_bridges()               ├─ small_world_sigma()
  └─ (feeds community data) ──►  ├─ bootstrap_ci() × N metrics
                                  └─ per_type_degree_stats()
```

All functions are **pure** (take a NetworkX graph, return a dataclass)
and can be called independently.

---

## Metric Details

### 1. Power-Law KS Test (`power_law_test`)

**What:** Uses the Clauset–Shalizi–Newman (2009) method via the `powerlaw`
package. Provides MLE α, xmin, KS distance, and comparison vs log-normal.

**Key fields:**
```python
result.alpha           # MLE exponent (expect 2.0–3.0 for scale-free)
result.xmin            # Lower bound for power-law behaviour
result.ks_statistic    # KS distance (lower = better fit)
result.p_value         # p ≥ 0.1 → can't reject power-law
result.plausible       # True if p ≥ 0.1
result.comparison_lognormal_R  # R > 0 → power-law better than log-normal
```

**Thesis usage:** "The degree distribution has α = {alpha} (xmin = {xmin}),
with KS p = {p_value:.3f}. The power-law hypothesis is {plausible ? 'not rejected' : 'rejected'}
at the 0.1 significance level. Against the log-normal alternative,
R = {comparison_lognormal_R:.2f} (p = {comparison_lognormal_p:.3f})."

**Dependency:** `pip install powerlaw`

---

### 2. NMI Community–Ontology (`community_ontology_nmi`)

**What:** Normalised Mutual Information between Louvain communities and
`node_type` attribute. NMI = 1.0 means communities perfectly recover
ontology classes.

**Key fields:**
```python
result.nmi                 # [0, 1] — 1 = perfect alignment
result.num_communities     # from community detection
result.num_types           # distinct ontology classes
result.contingency_table   # {type: {community_id: count}}
```

**Thesis usage:** "Communities detected by Louvain align with ontology
classes with NMI = {nmi:.3f}, indicating {high/moderate/low} structural–semantic
correspondence."

**Dependency:** `scikit-learn` (already installed)

---

### 3. Baseline Modularity (`baseline_modularity`)

**What:** Generates N configuration-model random graphs (same degree
sequence), runs Louvain on each, and compares the resulting modularity
distribution against the observed modularity. Reports z-score and
empirical p-value.

**Key fields:**
```python
result.observed_modularity  # Q from the real graph
result.baseline_mean        # mean Q from random graphs
result.baseline_std         # std of random Q
result.z_score              # (observed - mean) / std
result.p_value              # fraction of random ≥ observed
result.significant          # p < 0.05
```

**Thesis usage:** "The observed modularity Q = {observed:.3f} significantly
exceeds the configuration-model baseline (Q_rand = {mean:.3f} ± {std:.3f},
z = {z:.1f}, p = {p:.4f}), confirming that the community structure is not
an artefact of degree heterogeneity."

---

### 4. Small-World σ (`small_world_sigma`)

**What:** Computes σ = (C/C_rand) / (L/L_rand) where C = average clustering
and L = average shortest path. σ > 1 indicates small-world topology
(high clustering + short paths). Uses Erdős–Rényi random graphs.

**Key fields:**
```python
result.sigma       # > 1 → small-world
result.C_observed  # avg clustering of real graph
result.C_random    # avg clustering of random graphs
result.L_observed  # avg path length of real graph
result.L_random    # avg path length of random graphs
```

**Thesis usage:** "The graph exhibits small-world topology (σ = {sigma:.2f}),
with clustering {C_obs/C_rand:.1f}× higher than random while maintaining
paths only {L_obs/L_rand:.1f}× longer."

---

### 5. Bootstrap CIs (`bootstrap_ci`)

**What:** Edge-resampling bootstrap: samples edges with replacement to
create N bootstrap graphs, evaluates a metric on each, and returns the
percentile confidence interval.

**Default metrics bootstrapped:** density, avg_clustering, transitivity.

**Key fields:**
```python
result.observed          # point estimate
result.ci_lower          # 2.5th percentile
result.ci_upper          # 97.5th percentile
result.confidence_level  # 0.95
result.std_error         # bootstrap SE
```

**Thesis usage:** "Average clustering = {observed:.3f}
(95% CI [{ci_lower:.3f}, {ci_upper:.3f}], SE = {se:.4f})."

**Custom metrics:** Pass `bootstrap_metrics={"my_metric": my_fn}` to
`run_statistical_analysis()`.

---

### 6. Per-Type Degree Stats (`per_type_degree_stats`)

**What:** Splits degree distribution by `node_type`. Reveals whether
some entity types are hubs vs periphery.

**Key fields per type:**
```python
stats.type_name            # e.g. "Paragraf"
stats.count                # 858 nodes of this type
stats.mean_degree          # average degree for this type
stats.median_degree        # typical node degree
stats.std_degree           # spread
stats.degree_distribution  # {degree: count}
```

**Thesis usage:** "Paragraf nodes average degree {mean:.1f} (median {median}),
while Facility nodes average {mean:.1f} — reflecting the denser internal
structure of the law subgraph."

---

## How To Run

### All statistical metrics (via structural analysis):
```python
from kgbuilder.analytics.structural import run_structural_analysis

# Assumes `store` is your Neo4jGraphStore or InMemoryGraphStore
analysis = run_structural_analysis(store)

# Access statistical results:
stat = analysis.statistical
print(f"Power-law α = {stat.power_law.alpha}, plausible = {stat.power_law.plausible}")
print(f"NMI = {stat.nmi.nmi}")
print(f"Modularity z-score = {stat.baseline_modularity.z_score}")
print(f"Small-world σ = {stat.small_world.sigma}")

for ci in stat.confidence_intervals:
    print(f"{ci.metric_name}: {ci.observed:.4f} [{ci.ci_lower:.4f}, {ci.ci_upper:.4f}]")

for td in stat.per_type_degrees:
    print(f"{td.type_name}: n={td.count}, mean_deg={td.mean_degree:.1f}")
```

### Individual metrics:
```python
from kgbuilder.analytics.statistical import (
    power_law_test,
    community_ontology_nmi,
    baseline_modularity,
    small_world_sigma,
    bootstrap_ci,
    per_type_degree_stats,
)
import networkx as nx

G = ...  # your NetworkX graph

# 1. Power-law
pl = power_law_test(G)

# 2. NMI (needs community mapping from Louvain)
partition = nx.community.louvain_communities(G.to_undirected(), seed=42)
mapping = {n: i for i, comm in enumerate(partition) for n in comm}
nmi = community_ontology_nmi(G, mapping)

# 3. Baseline modularity
bm = baseline_modularity(G, list(partition), n_trials=100)

# 4. Small-world
sw = small_world_sigma(G)

# 5. Bootstrap CI for any metric
ci = bootstrap_ci(G, nx.average_clustering, metric_name="avg_clustering")

# 6. Per-type degrees
ptd = per_type_degree_stats(G)
```

### Run tests:
```bash
PYTHONPATH=src pytest tests/unit/test_statistical.py -v
```

---

## What's Still TODO (For You / Colleagues)

### Visualisation (extend `plots.py` or `interactive_plots.py`)

The statistical results are computed but not yet plotted. Good additions:

```python
# Stub: add to interactive_plots.py
def interactive_power_law_fit(topology: TopologyResult, statistical: StatisticalAnalysis):
    """Log-log degree distribution with fitted power-law overlay.
    
    Show empirical CCDF, fitted power-law line (α, xmin),
    and shaded region below xmin.
    """
    raise NotImplementedError  # TODO: implement with Plotly

def interactive_nmi_heatmap(nmi_result: NMIResult):
    """Heatmap of the community × type contingency table.
    
    Rows = ontology types, columns = community IDs, cells = node counts.
    """
    raise NotImplementedError  # TODO: implement with Plotly

def interactive_modularity_comparison(baseline: BaselineModularityResult):
    """Histogram of random modularity distribution with observed line.
    
    Show random distribution, observed value as vertical line,
    z-score annotation, and shaded rejection region.
    """
    raise NotImplementedError  # TODO: implement with Plotly

def interactive_per_type_degree(stats: list[PerTypeDegreeStats]):
    """Box plot or violin plot of degree distributions by type.
    
    One violin per entity type, annotated with mean/median.
    """
    raise NotImplementedError  # TODO: implement with Plotly
```

### Analytics Runner Script Update

Update `scripts/run_analytics.py` (if it exists) or the analytics section
of `scripts/full_kg_pipeline.py` to output the new statistical results
alongside existing metrics.

### Reporting

Add a `format_statistical_report(stat: StatisticalAnalysis) -> str` function
that produces a Markdown summary suitable for pasting into the thesis.

---

## Remaining Gaps (Phases 2–6)

These are documented in [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md)
and [CONTRIBUTION_GUIDE.md](CONTRIBUTION_GUIDE.md):

- **Phase 2:** SHACL shapes (colleague deliverable)
- **Phase 3:** Gold standard dataset (colleague deliverable)
- **Phase 4:** Embedding-based entity resolution
- **Phase 5:** Wire orchestrator stubs
- **Phase 6:** CI/CD + test coverage

---

## Dependencies Added

| Package | Version | Purpose |
|---------|---------|---------|
| `powerlaw` | 2.0.0 | KS goodness-of-fit for power-law distributions |
| `scikit-learn` | (existing) | `normalized_mutual_info_score` for NMI |
| `scipy` | (existing) | Statistical functions |
| `networkx` | (existing) | Graph algorithms + random graph generators |
