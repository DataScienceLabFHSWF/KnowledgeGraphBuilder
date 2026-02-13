# Architecture & Methods

## Ontology-Driven Iterative Knowledge Graph Construction

**Last Updated**: February 6, 2026

---

## 1. Core Idea

The system constructs a Knowledge Graph through **iterative, ontology-guided discovery**. Rather than making a single extraction pass, the pipeline generates research questions from the ontology, retrieves relevant document chunks, extracts entities and relations, measures coverage, and generates follow-up questions — repeating until the KG sufficiently covers the ontology.

```
                    ┌──────────────────────────────┐
                    │         OWL Ontology          │
                    │  Classes, Relations, CQs      │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │     Question Generation       │
                    │  "What Facilities exist?"     │
                    │  "What Actions are mentioned?"│
                    └──────────────┬───────────────┘
                                   │
                 ┌─────────────────┼──────────────────────┐
                 │           DISCOVERY LOOP               │
                 │                 │                       │
                 │                 ▼                       │
                 │  ┌──────────────────────────────┐      │
                 │  │    Retrieve Chunks            │      │
                 │  │    (Qdrant vector search)     │      │
                 │  └──────────────┬───────────────┘      │
                 │                 │                       │
                 │                 ▼                       │
                 │  ┌──────────────────────────────┐      │
                 │  │    Extract Entities           │      │
                 │  │    (Tiered: Heuristic -> LLM) │      │
                 │  └──────────────┬───────────────┘      │
                 │                 │                       │
                 │                 ▼                       │
                 │  ┌──────────────────────────────┐      │
                 │  │    Extract Relations          │      │
                 │  │    (Tiered: Heuristic -> LLM) │      │
                 │  └──────────────┬───────────────┘      │
                 │                 │                       │
                 │                 ▼                       │
                 │  ┌──────────────────────────────┐      │
                 │  │    Update Findings            │      │
                 │  │    (dedup, merge, confidence) │      │
                 │  └──────────────┬───────────────┘      │
                 │                 │                       │
                 │                 ▼                       │
                 │  ┌──────────────────────────────┐      │
                 │  │    Measure Coverage           │      │
                 │  │    entity_types ∩ classes     │      │
                 │  │    ─────────────────────      │      │
                 │  │    total ontology classes     │      │
                 │  └──────────────┬───────────────┘      │
                 │          YES ╱     ╲ NO                 │
                 │       coverage     coverage             │
                 │       ≥ target     < target             │
                 │            │          │                  │
                 │            │          ▼                  │
                 │            │ ┌──────────────────────┐   │
                 │            │ │ Generate Follow-Up Qs│   │
                 │            │ │ (under-covered       │   │
                 │            │ │  classes)             │───┘
                 │            │ └──────────────────────┘
                 │            │
                 └────────────┼───────────────────────────┘
                              │
                              ▼
                    ┌──────────────────────────────┐
                    │     Synthesize & Checkpoint   │
                    │  Merge entities, resolve,     │
                    │  save to JSON checkpoint      │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │     Enrich & Persist          │
                    │  Descriptions, embeddings,    │
                    │  CQs → Neo4j, Qdrant, RDF    │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │     Validate                  │
                    │  SHACL, semantic rules,       │
                    │  consistency checking         │
                    └──────────────────────────────┘
```

---

## 2. The Iterative Discovery Loop

This is the heart of the system. The `IterativeDiscoveryLoop` class (in `src/kgbuilder/agents/discovery_loop.py`) orchestrates a cycle of question-driven extraction that progressively builds the KG.

### 2.1 How It Works

**Input**: An OWL ontology loaded from Fuseki defining the classes (entity types) and relations the KG should contain.

**Step 1 — Question Generation**

The `QuestionGenerationAgent` examines which ontology classes are under-covered and generates targeted research questions:

- For each ontology class with few or no discovered entities, generate an existence question: *"What [ClassName] instances are mentioned in the documents?"*
- For classes with some entities but missing relations, generate expansion questions: *"What relationships exist between [ClassA] and [ClassB]?"*
- Questions are prioritized by: hierarchy level (broad classes first, weight 0.5), relation connectivity (hub classes, weight 0.3), and current deficit (weight 0.2)

**Step 2 — Retrieve**

For each question, query the vector store (Qdrant) for the top-K most relevant document chunks (default K=10). The chunks were pre-embedded during document ingestion using 384-dim embeddings via Ollama.

**Step 3 — Extract Entities**

For each retrieved chunk, call the LLM with an ontology-guided prompt:

```
Given these entity types from the domain ontology:
  - Facility: A physical facility involved in decommissioning
  - Action: An activity or process step
  - Phase: A temporal stage of the project
  ...

Extract all entities from the following text.
Return ONLY valid JSON matching this schema: { entities: [...] }
```

The LLM returns structured JSON validated against `EntityExtractionOutput` (Pydantic). Retry logic re-prompts up to 3 times with validation error feedback if the output is malformed.

Each entity gets:
- `label` — the extracted name
- `entity_type` — mapped to an ontology class
- `confidence` — LLM's self-assessed certainty (0–1)
- `evidence` — source chunk ID + text span for provenance

**Step 4 — Extract Relations**

Within the same chunk, extract relations between the entities just found:

```
Given these entities: [Facility:KKW-1, Action:Rückbau, Phase:Phase-3]
And these relation types from the ontology:
  - hasPhase (Facility → Phase)
  - performsAction (Facility → Action)
  ...

Extract all relations. Validate: source type ∈ domain, target type ∈ range.
```

Relations are validated against ontology constraints:
- **Domain/range**: source entity type must be in the relation's domain, target in its range
- **Cardinality**: functional properties (e.g., `hasCurrentPhase`) allow at most one object per subject
- **Deduplication**: keyed by `(source_id, predicate, target_id)`

**Step 5 — Update Findings**

New entities are merged into the accumulated findings dictionary (keyed by entity ID). If a duplicate is found:
- Keep the entry with the higher confidence score
- Track provenance: which document IDs contributed to this entity

**Step 6 — Measure Coverage**

```
coverage = |discovered_entity_types ∩ ontology_classes| / |ontology_classes|
```

If coverage ≥ target (default 0.85), stop. Otherwise, continue.

**Step 7 — Generate Follow-Up Questions**

The question generator identifies which ontology classes are still under-represented and creates new questions targeting those gaps. It also generates relation-focused questions for newly discovered entity types. The loop repeats from Step 2 with these new questions.

**Stopping conditions** (any one triggers termination):
- Coverage target reached
- Maximum iterations reached (default: 5)
- No more follow-up questions generated

### 2.2 Why Iterative?

A single extraction pass misses entities because:
- Not all chunks are relevant to all ontology classes
- The first set of retrieval queries may not cover the full ontology
- Confidence improves when entities are re-discovered across multiple chunks
- Relations require entities from both sides to already exist

Iteration addresses all of these. Early iterations discover broad, high-level entities; later iterations focus on gaps in coverage and fill in relations between already-known entities.

### 2.3 Discovery Loop Data Flow

```
Iteration 1:
  Questions: [q_facility, q_action, q_phase, q_state, ...]  (18 questions from ontology)
  Per question:
    → retrieve 10 chunks from Qdrant
    → per chunk: extract entities (LLM) → extract relations (LLM)
  → 180 chunks processed, ~120 entities found, ~40 relations
  → coverage: 0.61 (11 of 18 classes populated)

Iteration 2:
  Follow-up questions target: Material, Regulation, Equipment, ...  (7 under-covered classes)
  → 70 chunks processed, ~80 new entities, ~50 relations
  → coverage: 0.83

Iteration 3:
  Follow-up questions target: remaining 3 classes + relation expansion
  → 30 chunks processed, ~40 new entities, ~30 relations
  → coverage: 0.89 ≥ 0.85 target → STOP

Total: ~280 entities, ~156 relations, 3 iterations, ~6.8h
```

---

## 3. Entity Extraction in Detail

The `LLMEntityExtractor` (in `src/kgbuilder/extraction/entity.py`) converts unstructured text into typed entities using ontology-guided prompting.

### 3.1 Prompt Construction

The prompt includes:
1. **Ontology class definitions** — URI, label, description, examples, properties per class
2. **Extraction guidelines** — confidence scale, output format, deduplication hints
3. **Existing entities** — already-discovered entities so the LLM can avoid duplicates and can reference them in relations
4. **Source text** — the document chunk to extract from

### 3.2 Structured Output Enforcement

The `OllamaProvider.generate_structured()` method enforces valid output:

1. Append JSON schema to prompt
2. Call LLM (Ollama REST API)
3. Extract JSON from response (strip markdown code blocks, find first `{` to last `}`)
4. Validate with `schema.model_validate_json()` (Pydantic)
5. On validation failure: retry up to 3 times, feeding the specific field errors back into the prompt
6. On JSON parse failure: attempt recovery (brace balancing, truncation, incomplete field removal)

### 3.3 Post-Processing

- **Position finding**: Locate the entity text span in the source (exact → case-insensitive → first-word fallback)
- **Evidence attachment**: Create `Evidence` objects linking entity → chunk + text span
- **Deduplication**: Group by `(label.lower(), entity_type)`, keep highest confidence entry
- **Confidence filtering**: Drop entities below threshold (default 0.5)

---

## 4. Relation Extraction in Detail

The `LLMRelationExtractor` (in `src/kgbuilder/extraction/relation.py`) identifies typed relationships between entities.

### 4.1 Ontology-Guided Extraction

Each ontology relation definition (`OntologyRelationDef`) specifies:
- `domain`: which entity types can be the source
- `range`: which entity types can be the target
- `is_functional`: at most one object per subject
- `is_inverse_functional`: at most one subject per object
- `is_transitive`, `is_symmetric`: logical properties

The LLM receives the entity list and relation definitions, then extracts matching relations from the text.

### 4.2 Constraint Validation

Every extracted relation is validated:

1. **Entity resolution** — Find source and target entities by ID
2. **Domain check** — Source entity's type must appear in the relation's domain list
3. **Range check** — Target entity's type must appear in the relation's range list
4. **Cardinality enforcement** — For functional properties, keep only the highest-confidence relation per subject; for inverse-functional, one subject per object

### 4.3 Cross-Document Relations

After entity synthesis, relations can span across documents:

```
For entity pair (e_i, e_j) from different documents:
    Query retriever for chunks mentioning both entities
    If co-occurrence evidence found:
        Extract relations from those evidence chunks
        Validate constraints and deduplicate
```

This captures relationships that no single document states explicitly but that emerge from the combined corpus.

---

## 5. Findings Synthesis

The `FindingsSynthesizer` (in `src/kgbuilder/extraction/synthesizer.py`) merges entities and relations from all extraction passes into a clean, deduplicated set.

### 5.1 Entity Deduplication

1. Group entities by `entity_type`
2. Within each group, greedy clustering by similarity:
   - `similarity = 0.7 × SequenceMatcher(label_a, label_b) + 0.3 × type_match`
   - Cluster threshold: 0.75
3. Merge each cluster: keep highest-confidence entity, merge evidence lists, boost confidence (+0.05 per additional merge, capped at +0.10)

### 5.2 Relation Consolidation

Group relations by `(source_entity_id, predicate, target_entity_id)`. For duplicate triples, aggregate confidence scores.

### 5.3 Conflict Detection

Identify contradictory descriptions for the same entity (same label, different descriptions with low textual similarity). These are flagged for manual review.

---

## 6. Confidence Tuning

After synthesis, the confidence pipeline refines entity scores:

| Component | What It Does |
|-----------|-------------|
| `ConfidenceAnalyzer` | Statistical analysis: mean/std/percentiles per type, IQR-based anomaly detection |
| `ConfidenceBooster` | +0.15 per additional unique source document, +0.05 for high-confidence types, cap 0.99 |
| `ConfidenceCalibrator` | Normalize confidence across different extraction passes |
| `CoreferenceResolver` | Merge entities that refer to the same real-world object (different mentions) |
| `ConfidenceFilter` | Drop entities below an adaptive threshold (based on target precision) |
| `ConsensusVoter` | Multi-source voting for entity type disambiguation |

---

## 7. Three-Layer Processing Model

The full pipeline separates into three layers with distinct cost profiles, enabling efficient iteration:

```
┌─────────────────────────────────────────────────────────┐
│  LAYER 1: EXTRACTION (Expensive — ~6.8h for 33 docs)   │
│                                                          │
│  Ontology → Questions → Retrieve → LLM Extract          │
│  → Synthesize → Confidence Tune                          │
│                                                          │
│  Output: checkpoint.json (entities + relations + meta)   │
├─────────────────────────────────────────────────────────┤
│  LAYER 2: ENRICHMENT (Fast — ~15min)                    │
│                                                          │
│  Load checkpoint → LLM Descriptions → Embeddings        │
│  → Competency Questions → Aliases → Type Constraints    │
│                                                          │
│  Output: enriched entities + relations with embeddings   │
├─────────────────────────────────────────────────────────┤
│  LAYER 3: PERSISTENCE (Fast — ~5min)                    │
│                                                          │
│  Write Neo4j → Write Qdrant → Write RDF/Fuseki          │
│  → Generate exports (JSON-LD, Cypher, RDF)              │
│                                                          │
│  Output: populated stores + export files                 │
└─────────────────────────────────────────────────────────┘
```

**Key insight**: Extraction is the bottleneck (~6.8h). By checkpointing after extraction, enrichment and persistence can be re-run in ~15min without re-extracting (**94% time savings** on iterative refinement).

### Enrichment Phases

| Phase | Enricher | What It Adds |
|-------|----------|-------------|
| 1 | `DescriptionEnricher` | LLM-generated human-readable description per entity |
| 2 | `EmbeddingEnricher` | 384-dim semantic embedding (nomic-embed-text via Ollama) |
| 3 | `CompetencyQuestionEnricher` | 3-5 competency questions each entity helps answer |
| 4 | `TypeConstraintEnricher` | Semantic type compatibility scores from co-occurrence |
| 5 | `AliasEnricher` | Synonyms, abbreviations, alternate names |

---

## 8. KG Assembly & Persistence

The `KGBuilder` (in `src/kgbuilder/assembly/kg_builder.py`) writes enriched entities and relations to multiple stores with automatic query routing (SPARQL → Fuseki, Cypher → Neo4j).

| Store | Purpose | What Gets Written |
|-------|---------|-------------------|
| **Neo4j** | Graph queries, Cypher, visualization | Nodes + Edges with all properties |
| **Qdrant** | Vector similarity for RAG retrieval | 3 collections: `document_chunks`, `entity_semantics`, `relation_semantics` |
| **Fuseki** | SPARQL queries, ontology reasoning | RDF triples (TBox ontology + ABox instances) |

**Export formats**: JSON-LD, RDF/Turtle, Cypher, GraphML, N-Triples

---

## 9. Validation

Three validation layers run against the assembled KG:

### 9.1 SHACL Validation

Convert the graph to RDF and validate against SHACL shapes derived from the ontology. Reports violations with severity, focus node, and shape URI.

### 9.2 Semantic Rules Engine

| Rule | What It Checks |
|------|---------------|
| `DomainRangeRule` | Source type ∈ domain, target type ∈ range for all edges |
| `FunctionalPropertyRule` | At most one value per subject for functional properties |
| `InversePropertyRule` | If `rel(A,B)` exists, `inverse_rel(B,A)` must also exist |
| `TransitiveRule` | If `rel(A,B)` and `rel(B,C)`, then `rel(A,C)` should exist |

### 9.3 Consistency Checker

Detects: type conflicts, value conflicts, cardinality violations, duplicate entity sets. Returns a `ConsistencyReport` with conflict rate and recommendations.

---

## 10. Stopping Criteria

The `BuildPipeline` orchestrator (in `src/kgbuilder/pipeline/orchestrator.py`) can wrap the discovery loop with additional stopping criteria:

| Criterion | Default | Description |
|-----------|---------|-------------|
| `max_iterations` | 5 | Hard iteration limit |
| `min_cq_coverage` | 0.8 | Fraction of competency questions answerable |
| `min_validation_pass_rate` | 0.9 | SHACL/rule violation pass rate |
| `min_avg_confidence` | 0.6 | Mean entity confidence |
| `marginal_gain_threshold` | 0.01 | Stop if new entities per iteration < ε |
| `graph_stability_threshold` | 0.95 | Stop if graph structure change < δ |

Stopping mode can be `require_all` (all criteria must be met) or `require_any` (first criterion met triggers stop).

---

## 11. Infrastructure

### Docker Stack

| Service | Port | Role |
|---------|------|------|
| `ollama` | 11434 | LLM inference (Qwen3, Llama3.1) |
| `qdrant` | 6333 | Vector store (384-dim embeddings) |
| `neo4j` | 7474/7687 | Graph database |
| `fuseki` | 3030 | RDF/SPARQL store (ontology) |

### Module Layout

```
src/kgbuilder/
├── agents/             # IterativeDiscoveryLoop, QuestionGenerationAgent
├── extraction/         # LLMEntityExtractor, LLMRelationExtractor, FindingsSynthesizer
├── confidence/         # Analyzer, Booster, Calibrator, Coreference, Filter, Voter
├── assembly/           # KGBuilder (multi-store orchestrator)
├── validation/         # SHACLValidator, RulesEngine, ConsistencyChecker
├── evaluation/         # QA dataset, query executor, metrics
├── experiment/         # ExperimentManager, CheckpointManager, Analyzer, Plotter
├── embedding/          # OllamaProvider (LLM generation + embeddings)
├── pipeline/           # BuildPipeline orchestrator + StoppingCriterionChecker
├── document/           # Document loaders + chunking strategies
├── storage/            # Neo4j, Fuseki, Qdrant connectors
├── core/               # Protocols, data models, exceptions
└── cli.py              # Typer CLI entry point
```

### Performance (33 documents, nuclear decommissioning domain)

| Metric | Value |
|--------|-------|
| Chunks processed | ~3,004 |
| Unique entities | ~280 |
| Unique relations | ~156 (18 types) |
| Avg entity confidence | 0.82 |
| Avg relation confidence | 0.74 |
| Extraction time (Layer 1) | ~6.8h |
| Enrichment time (Layer 2) | ~15min |
| Persistence time (Layer 3) | ~5min |
| Estimated domain coverage | 92% |

---

## 12. Domain Pluggability

The pipeline is **ontology-agnostic**: `FullKGPipeline` reads whatever ontology is loaded
in Fuseki and generates extraction prompts from it. This means adding a new knowledge
domain does NOT require forking the pipeline — it requires providing domain-specific
components and a config profile.

### What the Pipeline Already Parameterizes

`PipelineConfig` (in `scripts/full_kg_pipeline.py`) exposes all domain-specific settings:

```python
class PipelineConfig(BaseModel):
    ontology_dataset: str      # Fuseki dataset name → separate ontology graph
    ontology_path: str         # Path to the OWL file
    document_dir: str          # Where source documents live
    document_extensions: list  # File types to ingest (.pdf, .xml, ...)
    vector_collection: str     # Qdrant collection → separate vector namespace
    output_dir: str            # Results output directory
    export_formats: list       # json-ld, cypher, turtle, ...
    max_iterations: int        # Discovery loop iterations
    ...
```

### Adding a New Domain

```
Step 1: Ontology
   Create/merge OWL ontology → load into Fuseki dataset

Step 2: Documents
   Place source files in data/<domain>/ or implement a custom loader

Step 3: Extractors (optional — LLM extractors already work generically)
   Add domain-specific rules:
     src/kgbuilder/extraction/<domain>_rules.py    — regex/gazetteers
     src/kgbuilder/extraction/<domain>_llm.py      — specialized prompts
     src/kgbuilder/extraction/<domain>_ensemble.py — rule + LLM merge

Step 4: Profile
   Create data/profiles/<domain>.json with PipelineConfig overrides

Step 5: Run
   python scripts/full_kg_pipeline.py --profile data/profiles/<domain>.json
```

### Example: Law Domain vs Decommissioning

```
                    ┌─────────────────────────────────────────────────┐
                    │              FullKGPipeline                      │
                    │  (shared: discovery, confidence, validation,     │
                    │   assembly, export, versioning)                  │
                    ├────────────────────┬────────────────────────────┤
                    │ DECOMMISSIONING    │ GERMAN LAW                 │
                    ├────────────────────┼────────────────────────────┤
                    │ Ontology:          │ Ontology:                  │
                    │  plan-ontology     │  law-ontology (LKIF+ELI)   │
                    │  (Fuseki: "plan")  │  (Fuseki: "lawgraph")      │
                    ├────────────────────┼────────────────────────────┤
                    │ Documents:         │ Documents:                 │
                    │  PDF loader        │  XML loader (law_xml.py)   │
                    │  33 PDFs           │  ~6,800 BJNR*.xml files    │
                    ├────────────────────┼────────────────────────────┤
                    │ Rules:             │ Rules:                     │
                    │  rules.py          │  legal_rules.py            │
                    │  (facility codes,  │  (§-references, law IDs,   │
                    │   isotopes, dates) │   abbreviations, dates)    │
                    ├────────────────────┼────────────────────────────┤
                    │ Special:           │ Special:                   │
                    │  n/a               │  Phase A structural import │
                    │                    │  (no LLM, XML → Neo4j)     │
                    └────────────────────┴────────────────────────────┘
```

### Phase A: Law-Specific Structural Import

German law XML has rich structure (`<norm>`, `<metadaten>`, `<textdaten>`) that can be
imported deterministically without any LLM. `build_law_graph.py` runs this as Phase A
before entering the standard pipeline (Phase B) for ontology-guided semantic extraction.

This is the only part that is truly law-specific and cannot be expressed as a
`PipelineConfig` swap. All other phases (discovery, extraction, confidence tuning,
assembly, validation, export) work identically across domains.

### Ontology Loading Flow

```
LKIF-Core (11 modules) ──┐
                          ├─→ merge_legal_ontologies.py ──→ legal-foundations-merged.owl
ELI (eli.owl)    ────────┘                                          │
                                                                    ▼
                                                build_law_ontology.py
                                                    (adds domain classes)
                                                          │
                                                          ▼
                                                law-ontology-v1.0.owl
                                                          │
                                                          ▼
                                        load_ontology_to_fuseki.py
                                            (POST to Fuseki "lawgraph")
                                                          │
                                                          ▼
                                               FusekiOntologyService
                                            (SPARQL → extraction prompts)
```

Fuseki's `load_ontology()` takes a single RDF string (auto-detects RDF/XML vs Turtle).
LKIF-Core's 11 separate OWL modules with `owl:imports` must be merged first. The
cherry-pick mode in `merge_legal_ontologies.py` extracts only ~30 classes/properties
needed for our pipeline (out of hundreds in the full ontologies).
