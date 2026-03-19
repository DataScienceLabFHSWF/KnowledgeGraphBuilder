# Benchmarking Status & Results Tracker

**Experiment**: Nuclear Decommissioning KG — Paper Benchmark  
**Started**: ___________  
**Last updated**: ___________

---

## Pre-Run Checklist

### Ontology Review

- [ ] Review `data/ontology/domain/plan-ontology-v2.0.owl` — sufficient classes for decommissioning?
- [ ] List of ontology classes checked:
  - [ ] Facility / NuclearFacility
  - [ ] Process / DecommissioningProcess
  - [ ] Permit / Genehmigung
  - [ ] SafetySystem
  - [ ] NuclearMaterial / WasteCategory
  - [ ] Activity / Stilllegung / Abbau / Rückbau
  - [ ] (add more as needed)
- [ ] Missing classes identified: ___________
- [ ] Ontology updated if needed? YES / NO / N/A

### Law Graph Build

- [ ] All 17 laws built into Neo4j (not just the 6 in the linker)
  - Currently downloaded in `data/law_html/`:
    AO, AtG, BBergG, BGB, BImSchG, BauGB, KrWG, OWiG, SprengG,
    StPO, StandAG, StrlSchG, StrlSchV, UVPG, VVG, VwGO, VwVfG
  - Currently in `law_linker.py` patterns: AtG, BBergG, BImSchG, KrWG, StrlSchG, StrlSchV
- [ ] Run: `python scripts/build_law_graph.py --laws ALL`
- [ ] Verify in Neo4j: node count for Paragraf, Gesetzbuch, Abschnitt
- [ ] Update `law_linker.py` keywords for new laws if needed? ___________

### Infrastructure

- [ ] Docker services running (Ollama, Neo4j, Qdrant, Fuseki)
- [ ] Ollama model pulled: `qwen3:8b`
- [ ] Documents ingested into Qdrant: 33 decommissioning PDFs
- [ ] Ontology loaded into Fuseki
- [ ] FusionRAGRetriever smoke test passed (G2 fix verified)

### Implementation Gaps

- [ ] **G1**: Per-iteration metrics logging implemented
- [ ] **G2**: FusionRAGRetriever param bug fixed & smoke tested
- [ ] **G4**: Experiment config JSON created
- [ ] **G5**: Full law graph built (17 laws)
- [ ] *(optional)* G6: Gold standard annotations (3–5 docs)
- [ ] *(optional)* G7: Convergence plot script
- [ ] *(optional)* G8: Statistical comparison script
- [ ] *(optional)* G9: Ollama seed propagation

---

## Experiment Runs

### Condition A — Single-pass baseline (max_iterations=1, no law graph)

| Run | Status | Duration | Entities | Relations | Ontology Cov. % | Relation Cov. % | Avg Confidence | CQ Answerable | Graph Density | Components | Notes |
|-----|--------|----------|----------|-----------|-----------------|-----------------|----------------|---------------|---------------|------------|-------|
| A-1 | ⬜ | | | | | | | | | | |
| A-2 | ⬜ | | | | | | | | | | |
| A-3 | ⬜ | | | | | | | | | | |
| **Mean ± std** | | | | | | | | | | | |

### Condition B — Multi-pass (max_iterations=5, no law graph)

| Run | Status | Duration | Entities | Relations | Ontology Cov. % | Relation Cov. % | Avg Confidence | CQ Answerable | Graph Density | Components | Notes |
|-----|--------|----------|----------|-----------|-----------------|-----------------|----------------|---------------|---------------|------------|-------|
| B-1 | ⬜ | | | | | | | | | | |
| B-2 | ⬜ | | | | | | | | | | |
| B-3 | ⬜ | | | | | | | | | | |
| **Mean ± std** | | | | | | | | | | | |

### Condition C — Multi-pass + law graph (max_iterations=5, law graph ON)

| Run | Status | Duration | Entities | Relations | Ontology Cov. % | Relation Cov. % | Avg Confidence | CQ Answerable | Graph Density | Components | Notes |
|-----|--------|----------|----------|-----------|-----------------|-----------------|----------------|---------------|---------------|------------|-------|
| C-1 | ⬜ | | | | | | | | | | |
| C-2 | ⬜ | | | | | | | | | | |
| C-3 | ⬜ | | | | | | | | | | |
| **Mean ± std** | | | | | | | | | | | |

**Status legend**: ⬜ not started · 🔄 running · ✅ completed · ❌ failed

---

## Per-Iteration Convergence Data (from best run of B & C)

### Condition B — per iteration

| Iter | Cumul. Entities | New Entities | Cumul. Relations | New Relations | Ontology Cov. % | Δ Coverage |
|------|----------------|-------------|-----------------|--------------|-----------------|-----------|
| 1 | | | | | | — |
| 2 | | | | | | |
| 3 | | | | | | |
| 4 | | | | | | |
| 5 | | | | | | |

### Condition C — per iteration

| Iter | Cumul. Entities | New Entities | Cumul. Relations | New Relations | Ontology Cov. % | Δ Coverage |
|------|----------------|-------------|-----------------|--------------|-----------------|-----------|
| 1 | | | | | | — |
| 2 | | | | | | |
| 3 | | | | | | |
| 4 | | | | | | |
| 5 | | | | | | |

---

## Law Graph Impact (C vs B)

| Metric | B (no law) | C (with law) | Δ | Effect Size (Cohen's d) |
|--------|-----------|-------------|---|------------------------|
| Ontology class coverage % | | | | |
| Relation coverage % | | | | |
| Total entities | | | | |
| Total edges | | | | |
| Law-linked edges | — | | | — |
| Avg confidence | | | | |
| CQ answerability (of 9) | | | | |
| Build time (s) | | | | |

---

## Statistical Summary

### Bootstrap 95% CIs (1000 resamples)

| Metric | A | B | C |
|--------|---|---|---|
| Ontology coverage | [__, __] | [__, __] | [__, __] |
| Entity count | [__, __] | [__, __] | [__, __] |
| Avg confidence | [__, __] | [__, __] | [__, __] |

### Pairwise Comparisons

| Comparison | Metric | Δ mean | Cohen's d | Wilcoxon p | Significant? |
|------------|--------|--------|-----------|------------|-------------|
| A vs B | Ontology cov. | | | | |
| A vs B | Entity count | | | | |
| B vs C | Ontology cov. | | | | |
| B vs C | Entity count | | | | |
| B vs C | Law-linked edges | | | | |

---

## Graph Structural Metrics

| Metric | A (mean) | B (mean) | C (mean) |
|--------|---------|---------|---------|
| Nodes | | | |
| Edges | | | |
| Density | | | |
| Connected components | | | |
| Largest component % | | | |
| Avg degree | | | |
| Clustering coefficient | | | |
| Small-world σ | | | |

---

## Competency Questions Breakdown

| CQ ID | Question (short) | A | B | C |
|-------|-----------------|---|---|---|
| CQ_001 | Freigabe vs. Freisetzung | ⬜ | ⬜ | ⬜ |
| CQ_002 | AtG vs. EURATOM definitions | ⬜ | ⬜ | ⬜ |
| CQ_003 | § 9 vs. § 7 AtG permits | ⬜ | ⬜ | ⬜ |
| CQ_004 | Liability for transport | ⬜ | ⬜ | ⬜ |
| CQ_005 | § 7 AtG vs. § 12 StrlSchG | ⬜ | ⬜ | ⬜ |
| CQ_006 | | ⬜ | ⬜ | ⬜ |
| CQ_007 | | ⬜ | ⬜ | ⬜ |
| CQ_008 | | ⬜ | ⬜ | ⬜ |
| CQ_009 | | ⬜ | ⬜ | ⬜ |
| **Total answerable** | | /9 | /9 | /9 |

**Legend**: ✅ answerable · ⬜ not answerable · ⚠️ partial

---

## Issues & Observations

| # | Date | Issue | Resolution |
|---|------|-------|------------|
| | | | |

---

## Final Results Summary (for paper)

> **Fill this after all runs complete.**

**Key findings**:
1. Multi-pass vs. single-pass: ___________
2. Law graph augmentation: ___________
3. Convergence behavior: ___________
4. Statistical significance: ___________
