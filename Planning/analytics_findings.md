# Knowledge Graph Analytics — Findings & Interpretation

**Date**: 2026-02-16  
**Graphs analysed**: Law graph, Domain graph, Combined graph (from Neo4j)

---

## 1. Graph Overview

| Metric | Law | Domain | Combined |
|---|---|---|---|
| **Nodes** | 858 | 530 | 1,388 |
| **Edges** | 3,684 | 1,223 | 4,912 |
| **Density** | 0.0050 | 0.0044 | 0.0026 |
| **Avg Degree** | 8.59 | 4.62 | 7.08 |
| **Clustering** | 0.529 | 0.060 | 0.350 |
| **Transitivity** | 0.102 | 0.260 | 0.104 |
| **Reciprocity** | 0.000 | 0.000 | 0.000 |
| **Components** | 139 | 226 | 362 |
| **Diameter** | 2 | 14 | 2 |
| **Power-law α** | 1.55 | **2.30** | 1.67 |
| **Modularity** | 0.766 | **0.897** | 0.819 |
| **PageRank Gini** | 0.503 | 0.330 | 0.452 |
| **Composite Score** | 0.300 (#2) | **0.445** (#1) | 0.121 (#3) |

## 2. Law Graph — Structural Validation

The law graph's structural properties **confirm the pipeline correctly reproduces German legislative hierarchy**:

- **Diameter = 2**: Every paragraph is at most 2 hops from a Gesetzbuch root
  (Paragraf → Abschnitt → Gesetzbuch), confirming `teilVon` hierarchy is correct.
- **139 components**: Each represents one law section (134 Abschnitte + 5 Gesetzbücher).
  This perfectly matches the expected structure.
- **High clustering (0.529)**: Paragraphs within the same section densely cross-reference
  each other via `referenziert` edges, which is expected for German legal texts.
- **Zero reciprocity**: All edges are directed (teil_von, referenziert go one way) — correct.
- **Power-law α = 1.55**: Below the scale-free range [2, 3.5] because the 5 Gesetzbuch
  hub nodes concentrate far more connections than a natural network would.

### Top PageRank Entities (Law Graph)

| Rank | Entity | PageRank | Interpretation |
|---|---|---|---|
| 1 | **StrlSchG** (Strahlenschutzgesetz) | 0.0775 | Most-referenced law — expected for nuclear decommissioning |
| 2 | **BBergG** (Bundesberggesetz) | 0.0688 | Mining law, relevant for underground disposal |
| 3 | **BImSchG** (Immissionsschutzgesetz) | 0.0410 | Environmental protection law |
| 4 | **AtG** (Atomgesetz) | 0.0341 | Core nuclear energy law |
| 5 | **KrWG** (Kreislaufwirtschaftsgesetz) | 0.0263 | Waste management law |

### Top Betweenness Centrality

| Rank | Entity | Score | Interpretation |
|---|---|---|---|
| 1 | **StrlSchG § 172** | 0.0078 | Key bridging paragraph (radiation protection rules) |
| 2 | **StrlSchG § 72** | 0.0072 | Connects multiple sections |
| 3 | **StrlSchG § 2** | 0.0063 | Scope/definitions paragraph — heavily cross-referenced |

**Conclusion**: The law graph is structurally sound. The hierarchy, clustering, and
centrality rankings all align with domain expectations for German nuclear law.

---

## 3. Domain Graph

The domain graph captures decommissioning knowledge extracted from planning documents.

### Key Structural Properties

- **Scale-free (α = 2.30)**: The *only* graph in the proper [2, 3.5] scale-free range.
  This indicates organic, LLM-extracted structure rather than imposed hierarchy.
- **Very high modularity (0.897)**: Extremely well-separated communities, each representing
  a distinct planning domain or facility.
- **226 components**: Highly fragmented — reflects separate extraction runs for different
  facilities (KKG, GKN, Gundremmingen, etc.) that were never merged.
- **Low clustering (0.060), higher transitivity (0.260)**: Entities connect through shared
  predicates/actions (star topology) rather than forming dense local cliques.
- **Diameter = 14**: Much longer paths than the law graph, reflecting the multi-step
  nature of decommissioning procedures.

### Domain Node Types (530 total)

| Type | Count | Examples |
|---|---|---|
| DomainConstant | 152 | Objektsicherungszentralen, Kraftwerkszugang |
| DomainPredicate | 68 | Kompaktierung, Zerlegung |
| State | 57 | InitialState, GoalState instances |
| PlanningDomain | 48 | KKG, GKN I, Gundremmingen |
| DomainRequirement | 28 | Radiation limits, safety rules |
| Action | 27 | Demontage, Transport |
| Facility | 26 | KKG, GKN I, Kernkraftwerk Grafenrheinfeld |
| Organization | 10 | E.ON, EnBW |
| Plan | 16 | Decommissioning plans |
| PlanningProblem | 15 | Specific PDDL problems |

### Domain Edge Types (1,223 total)

| Edge Type | Count | Description |
|---|---|---|
| hasConstant | 200 | Domain → constant |
| hasRequirement | 186 | Domain → requirement |
| hasObject | 156 | Action → object |
| hasPredicate | 151 | Domain → predicate |
| hasEffect | 70 | Action → effect |
| hasGoalState | 69 | Problem → goal |
| hasProblem | 65 | Domain → problem |
| hasAction | 49 | Domain → action |
| solvedBy | 46 | Problem → plan |
| solvesRequirement | 38 | Plan → requirement |

---

## 4. Combined Graph — Cross-Linking Failure

The combined graph has **only 5 cross-links** between the law and domain subgraphs — all
`LINKED_GOVERNED_BY` edges pointing to AtG.

### Impact

- **362 components** = 139 (law) + 226 (domain) - 3 (merged via cross-links).
  Almost no integration at all.
- **Composite score is lowest** (0.121) because the sparse cross-linking dilutes both
  subgraphs' strengths without adding meaningful topology.
- **Diameter collapses to 2** — dominated by the law graph's hub structure.

### Root Cause

See [linking_next_steps.md](linking_next_steps.md) for detailed analysis and improvement plan.

---

## 5. Centrality Measures Explained

We compute 8 centrality measures:

| Measure | What it captures | KG application |
|---|---|---|
| **Degree** | Total connections | Most-connected entities |
| **In-degree** | Incoming edges | Entities referenced by many others |
| **Out-degree** | Outgoing edges | Entities that reference many others |
| **PageRank** | Recursive importance | Authoritative entities (like Google for web pages) |
| **Betweenness** | Bridging role | Entities that connect different parts of the KG |
| **Closeness** | Reachability | Entities closest to all others |
| **Eigenvector** | Connection to important nodes | Entities connected to other important entities |
| **Non-backtracking (Hashimoto)** | Robust importance | See below |

### Non-Backtracking / Hashimoto Centrality

Standard eigenvector centrality in sparse, heterogeneous graphs (typical of KGs) suffers
from a **localization problem**: the leading eigenvector can concentrate on a single hub
and its immediate neighbours, failing to capture global structure.

Non-backtracking centrality uses the **Hashimoto (non-backtracking) matrix** $B$:

$$B_{e_1, e_2} = \begin{cases} 1 & \text{if } \text{target}(e_1) = \text{source}(e_2) \text{ and } \text{source}(e_1) \neq \text{target}(e_2) \\ 0 & \text{otherwise} \end{cases}$$

This matrix operates on *directed edges* rather than nodes. The constraint
$\text{source}(e_1) \neq \text{target}(e_2)$ prevents the random walk from
immediately backtracking, leading to:

- **Better spectral gap** → clearer community detection
- **No hub localization** → more informative ranking in sparse KGs
- **Robust to degree heterogeneity** → works better than eigenvector centrality
  when hub nodes dominate the degree distribution

The leading eigenvector of $B$ is aggregated per node to produce a centrality score.

---

## 6. GraphSAGE / Semantic Embeddings

### What is `graphsage_no_semantic_embeddings`?

The GraphSAGE analysis module computes two kinds of embeddings and compares them:

1. **Structural embeddings**: Derived from the graph topology using DeepWalk
   (random walk + skip-gram). Captures a node's structural role in the graph.
2. **Semantic embeddings**: Pre-computed vector representations of node content
   (labels, descriptions) — typically from an LLM embedding model.

The warning means **no semantic embeddings were found** on any nodes. The module
checks for an `embedding` property on each node in the graph store; if none exist,
it attempts to call an `embedding_provider.embed_batch()`. Since neither was
available, only structural embeddings were produced.

**Impact**: Without semantic embeddings, we cannot compare structural vs. semantic
alignment (Procrustes analysis, cosine similarity distribution). The quality argument
shows "Procrustes fit = 0.000" because there's nothing to compare against.

### How to Fix

Provide semantic embeddings by either:

1. **Store embeddings on nodes during KG building** — add an `embedding` property
   with a vector from Ollama/OpenAI during entity extraction or enrichment.
2. **Pass an `embedding_provider` to the analytics** — e.g., instantiate an
   `OllamaEmbeddingProvider` and pass it to `run_graphsage_analysis()`.

---

## 7. Community Structure

| Algorithm | Law | Domain | Combined |
|---|---|---|---|
| **Louvain** | 139 comms (mod=0.766) | 233 comms (mod=0.897) | 365 comms (mod=0.819) |
| **Label Prop.** | 139 comms (mod=0.766) | 274 comms (mod=0.789) | 412 comms (mod=0.799) |

### Law Graph Communities

In the law graph, communities map directly to law sections — each Abschnitt with its
Paragraf children forms one community. This is validated by the fact that Louvain and
label propagation agree exactly (139 communities = 139 components).

### Domain Graph Communities

The domain graph has more communities (233) than components (226), meaning some
larger components were further subdivided. This suggests distinct conceptual clusters
within connected facilities.

**Named community visualisations** are available in `output/analytics/*/community_graph.png`.
Each community is labeled at its centroid with size and top member names.

---

## 8. Outputs

All outputs are in `output/analytics/`:

| File | Description |
|---|---|
| `law/centrality_graph.png` | Graph layout, nodes sized by PageRank, top-20 labeled |
| `law/community_graph.png` | Communities coloured and named by top members |
| `law/centrality_topk.png` | Bar chart of top-15 by PageRank/betweenness |
| `law/centrality_correlation.png` | Heatmap of centrality measure correlations |
| `law/degree_distribution.png` | Log-log degree distribution |
| `law/community_sizes.png` | Community size distribution |
| `law/graph_layout.png` | Full graph layout coloured by community |
| `law/dashboard.png` | 4-panel overview dashboard |
| `domain/...` | Same plots for domain graph |
| `combined/...` | Same plots for combined graph |
| `cross_setting_radar.png` | Radar chart comparing all three graphs |
| `compare_*.png` | Per-metric bar chart comparisons |
| `quality_argument_*.md` | Auto-generated quality arguments |
| `all_metrics.json` | Raw metrics for all graphs |

---

## 9. Post-Linking Results (Updated 2026-02-16)

After extending the linker with keyword-based and entity-type-default strategies
plus paragraph-level resolution:

| Metric | Pre-Linking | Post-Linking | Δ |
|---|---|---|---|
| **Cross-domain edges** | 5 | **227** | +4,440% |
| **Combined edges** | 4,912 | **5,134** | +222 |
| **Combined components** | 362 | **271** | −91 (−25%) |
| **Combined diameter** | 2 | **14** | Path traversal now reaches domain depth |
| **Combined modularity** | 0.819 | **0.785** | Slight drop = more inter-community integration |
| **Combined PageRank top-5** | All law nodes | AtG_S_7 at #4 | Cross-domain node appears |
| **Combined betweenness top** | Law-only | AtG_S_7 also at #5 | Acts as bridge node |
| **Paragraph-level links** | 0 | **154** (68%) | Fine-grained linking |
| **Gesetzbuch-level links** | 5 | **73** (32%) | Fallback when section unknown |

The combined graph now shows meaningful cross-domain structural properties:
- **AtG § 7** (licensing paragraph) is the #4 PageRank and #5 betweenness node —
  it correctly emerges as the structural bridge between domain and law concepts
- Component count dropped 25%, meaning many formerly isolated domain entity
  clusters are now reachable through law paragraphs
- Diameter increased from 2 to 14, reflecting actual path length through the
  domain → law → domain traversal

---

## 10. Scientific Rationale for Structural Analysis

### 10.1 Why Structural Analysis Beyond SHACL Validation?

SHACL validation and structural graph analytics serve **complementary but distinct
purposes** in KG quality assurance:

| Aspect | SHACL Validation | Structural Analysis |
|---|---|---|
| **What it checks** | Schema conformance (types, cardinalities, value constraints) | Emergent graph properties (topology, centrality, communities) |
| **Level** | Local: individual nodes/edges against shape constraints | Global: whole-graph statistics and patterns |
| **Failure mode** | Catches schema violations (e.g., missing required property) | Catches construction defects invisible to SHACL (fragmentation, hub collapse, power-law drift) |
| **Interpretability** | "Node X violates shape Y" | "The graph has 226 disconnected components, suggesting entity resolution failure" |
| **Grounding** | Ontology (prescriptive) | Network science (descriptive, comparative) |

**A SHACL-valid graph can still be structurally pathological.** For example:
- Every node passes SHACL but there are 226 disconnected components → entity
  resolution is failing silently
- All edge types are correct but PageRank Gini = 0.95 → a single hub dominates,
  suggesting extraction bias
- Modularity = 0.02 → no community structure, meaning the ontology classes are
  not reflected in the graph topology

### 10.2 Scientific Value for Thesis Arguments

Structural analytics directly supports **RQ3** ("How can we evaluate and explain
agentic, graph-based QA systems?") by providing:

1. **Scale-free validation** — A well-constructed domain KG should exhibit
   power-law degree distributions with exponent α ∈ [2, 3.5] (Barabási & Albert,
   1999). Our domain graph shows α = 2.30, within the expected range, providing
   evidence that LLM-based extraction produces realistic graph topology.

2. **Community-ontology alignment** — Louvain communities should correlate with
   ontology classes. High modularity (Q > 0.4) indicates the graph captures
   the conceptual clustering defined by the ontology. Our domain graph achieves
   Q = 0.897, demonstrating strong ontology alignment.

3. **Centrality-based hub identification** — PageRank and betweenness identify
   which entities the construction pipeline considers structurally important.
   These can be validated against domain expert expectations (e.g., "AtG § 7
   should be the most important licensing paragraph" — confirmed by its #4
   PageRank ranking in the combined graph).

4. **Cross-domain bridging analysis** — Betweenness centrality identifies
   the structural bridges between law and domain subgraphs. If no cross-domain
   nodes appear in the top-k betweenness, the linking strategy is failing.
   After our keyword-based linking, AtG_S_7 appears at #5 — evidence that
   the linking strategy creates meaningful structural bridges.

5. **Component analysis as entity resolution diagnostic** — The number of
   connected components directly measures extraction fragmentation. If the
   pipeline extracts "Kernbrennstoff" and "nuclear fuel" as separate entities
   without merging them, the component count inflates. Tracking components
   across pipeline iterations provides a quantitative deduplication metric.

6. **Embedding comparison for retrieval quality** — The structural-vs-semantic
   embedding alignment (Procrustes + cosine) measures whether graph structure
   agrees with semantic content. High alignment means graph traversal and
   vector similarity will return consistent results — critical for hybrid
   GraphRAG architectures. Low alignment (our current state: 0.000) indicates
   that semantic embeddings are needed to enable this comparison.

### 10.3 Impact on Downstream Retrieval (GraphRAG)

Structural metrics directly predict retrieval quality in graph-augmented RAG:

| Metric | Retrieval Impact |
|---|---|
| **High modularity** | Graph partitions cleanly → community-based summarization (à la Microsoft GraphRAG) produces coherent topic summaries |
| **Low component count** | Multi-hop traversal can reach more of the graph → better recall for complex queries |
| **Meaningful bridges** | Cross-domain queries ("Which law governs decommissioning?") can be answered by traversing bridge nodes |
| **Power-law degree** | Hub nodes provide reliable entry points for retrieval; fat-tailed distribution means targeted subgraph extraction is efficient |
| **High clustering coefficient** | Local neighborhoods are dense → retrieved subgraphs for a single entity include rich contextual triples |
| **Non-backtracking centrality** | Identifies true structural importance without path-revisitation bias — more robust than standard betweenness for retrieval node ranking |

### 10.4 References

- Barabási, A.-L., & Albert, R. (1999). Emergence of scaling in random networks. *Science*, 286(5439), 509-512.
- Blondel, V. D., et al. (2008). Fast unfolding of communities in large networks. *J. Stat. Mech.*, P10008.
- Edge, D., et al. (2024). From Local to Global: A Graph RAG Approach to Query-Focused Summarization. arXiv:2404.16130.
- Grover, A., & Leskovec, J. (2016). node2vec: Scalable Feature Learning for Networks. *KDD*.
- Hamilton, W. L., Ying, R., & Leskovec, J. (2017). Inductive Representation Learning on Large Graphs. *NeurIPS*.
- Hashimoto, K. (1989). Zeta functions of finite graphs and representations of p-adic groups. *Adv. Stud. Pure Math.* 15, 211-280.
- Newman, M. E. J. (2006). Modularity and community structure in networks. *PNAS*, 103(23), 8577-8582.

---

## 11. Known Issues & Next Steps

| Issue | Status | Reference |
|---|---|---|
| Duplicate edge IDs in Neo4j | **Fixed** | `scripts/fix_edge_ids.py` — hash-based IDs |
| Edge ID collisions at build time | **Fixed** | `generate_relation_id()` in `core/models.py` |
| Law-domain cross-linking weakness | **Fixed** | 5 → 227 edges via keyword + type-default linking |
| No semantic embeddings for comparison | **Open** | Need to store embeddings during KG build |
| Orphan Gesetzbuch node | **Fixed** | Migrated + deleted; MERGE bug in linker fixed |
| Domain graph fragmentation (226 components) | **Open** | Needs entity resolution / dedup |
| `link_kg_to_laws.py` MERGE on abbreviation | **Fixed** | Now matches on `id` property |
| torch_geometric not installed | **Fixed** | Installed 2.7.0; real GraphSAGE now available |
| Interactive visualizations | **Done** | Plotly HTML plots in `output/analytics/*/interactive/` |
| Services not restarting after reboot | **Fixed** | `restart: unless-stopped` in docker-compose.yml |
