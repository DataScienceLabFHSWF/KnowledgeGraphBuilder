# Next Steps — Implementation Plan

> Generated: 2026-02-11 | Branch: `feat/law-graph`  
> Purpose: Delegatable task list for smaller LLM coding assistants

---

## Current State Summary

### Decommissioning KG (Baseline)
- **387 nodes** across 24 label types (Facility, DomainConstant, Action, Plan, etc.)
- **~800 edges** across 40+ relationship types
- Built from 33 German nuclear decommissioning PDFs (~126 MB)
- Stored in Neo4j + Qdrant (`discovery_test` collection, 16 vectors indexed)

### Law Graph (Phase A Complete)
- **858 nodes**: 719 Paragraf, 134 Abschnitt, 5 Gesetzbuch
- **3,684 edges**: referenziert (2,965) + teilVon (719)
- **717 paragraph embeddings** in Qdrant (`lawgraph` collection, dim=4096)
- **5 laws**: AtG, BBergG, BImSchG, KrWG, StrlSchG
- Custom OWL ontology: `data/ontology/law/law-ontology-v1.0.owl`

### Integration Status
- `LawGraphRetriever` — **fully implemented** (vector + graph queries)
- `LegalRuleBasedExtractor` — **fully implemented** (regex patterns for German law)
- Pipeline wiring — **done** (`LAW_GRAPH_ENABLED=true` flag)
- `LegalLLMExtractor` — **stub** (prompts defined, methods raise NotImplementedError)
- `LegalEnsembleExtractor` — **stub** (config defined, merge logic not implemented)

### Cross-Reference: wiki_alisa_kiko Issues
The colleague's repo (hennkar) has relevant open tasks that align with our work:
- **#100** "Extend usage of Ontologies" — subclassing, ODPs, annotation-based exclusion from schema
- **#101** "Use reasoning after KG construction" — OWL-RL inference (**we already have this!**)
- **#54** "Semi-Automatic Ontology Module Selection" — match entities to ontology concepts
- **#58** "Graph Persistence" — TBox/ABox/Lexical Graph layers (**we already have Neo4j + Fuseki**)
- **#2** "KG Construction & Integration" — comprehensive KG with TBox + ABox + Lexical Graph
- **#130** "Build Q-A system for ontology-based RDF graphs" — entity recognition + graph query

**What they're exploring that we already implement (better)**:
| Their Issue | Our Implementation | Notes |
|-------------|-------------------|-------|
| #101 OWL-RL reasoning | `analytics/` module with SemanticInferenceEngine | We do RDFS+OWL-RL inference, SKOS enrichment, graph metrics |
| #58 Graph persistence | Neo4j + Qdrant + Fuseki | Full triple store + property graph + vector DB |
| #56 Triple generation via ontology | `extraction/entity.py` + `extraction/relation.py` | Pydantic-constrained LLM output, ontology-guided prompts |
| #128 Ground truth + SHACL | `validation/` module | SHACL validator, rules engine, consistency checker |
| #121 RDF store comparison | Apache Fuseki chosen | Already integrated with SPARQL + reasoning support |

**What they're exploring that we should adopt/integrate**:
| Their Issue | Gap in Our System | Priority |
|-------------|------------------|----------|
| #100 Ontology subclassing | Our ontology is flat (3 classes). Need richer hierarchy | HIGH |
| #54 Ontology module selection | We use single ontology. Multi-module selection would improve extraction | MEDIUM |
| #2 Lexical Graph layer | We don't maintain provenance from text → entity. No sibling/hierarchical structure | LOW (nice-to-have) |

---

## Task Breakdown for Delegation

### TASK 1: KG Quality Comparison Script ⏱️ ~2h
> **Assignee**: Any coding assistant  
> **Branch**: `feat/law-graph`  
> **Priority**: 🔴 IMMEDIATE (can run now)

**Goal**: Create `scripts/compare_kg_quality.py` that runs the pipeline twice (with/without law graph) and produces a comparison report.

**Input files to read**:
- `scripts/full_kg_pipeline.py` — understand `PipelineConfig`, `--smoke-test`, `LAW_GRAPH_ENABLED`
- `src/kgbuilder/agents/discovery_loop.py` — see `context_provider` usage
- `src/kgbuilder/storage/law_retrieval.py` — understand `LawGraphRetriever`
- `data/evaluation/competency_questions.json` — CQ format for discovery

**Acceptance criteria**:
- [ ] Script runs the pipeline with `LAW_GRAPH_ENABLED=false` on a fresh Neo4j namespace
- [ ] Then runs with `LAW_GRAPH_ENABLED=true`
- [ ] Exports metrics: entity count, edge count, unique entity types, unique relation types
- [ ] Exports per-CQ extraction results (which entities found for which question)
- [ ] Outputs side-by-side comparison markdown table
- [ ] Tracks W&B run with `experiment_type: "law_graph_comparison"`

**Alternative (simpler)**: Can just export the current Neo4j KG state as baseline JSON, then run with law graph and diff.

---

### TASK 2: Implement `LegalLLMExtractor` ⏱️ ~4h
> **Assignee**: LLM coding assistant with structured-output experience  
> **Branch**: `feat/law-graph`  
> **Priority**: 🟡 HIGH

**Goal**: Implement the stubbed methods in `src/kgbuilder/extraction/legal_llm.py`.

**Input files to read**:
- `src/kgbuilder/extraction/legal_llm.py` — **the target file** (200 lines, prompts already defined)
- `src/kgbuilder/extraction/entity.py` — reference implementation for `LLMEntityExtractor`
- `src/kgbuilder/extraction/relation.py` — reference implementation for `LLMRelationExtractor`
- `src/kgbuilder/embedding/ollama.py` — `OllamaProvider.generate_structured()` API
- `src/kgbuilder/core/models.py` — `ExtractedEntity`, `ExtractedRelation` dataclasses

**What to implement** (each method currently raises `NotImplementedError`):
1. `extract(text, ontology_classes)` → calls `extract_entities()` + `extract_relations()`
2. `extract_entities(text, ontology_classes)`:
   - Build prompt using `_build_entity_prompt()` with German legal templates
   - Call `self._llm.generate_structured()` with Pydantic schema
   - Parse response via `_parse_entity_response()`
   - Validate against ontology via `_validate_against_ontology()`
3. `extract_relations(text, entities, ontology_relations)`:
   - Build prompt using `_build_relation_prompt()`
   - Call `self._llm.generate_structured()`
   - Parse and validate
4. Helper methods: `_build_entity_prompt()`, `_build_relation_prompt()`, `_format_class_definitions()`, `_format_relation_definitions()`, `_parse_entity_response()`, `_parse_relation_response()`, `_validate_against_ontology()`

**Constraints**:
- Follow patterns from `entity.py` and `relation.py` exactly
- Use `OllamaProvider.generate_structured(prompt, schema_class)` for JSON output
- German-language prompts (templates already in file)
- Return `list[ExtractedEntity]` and `list[ExtractedRelation]`
- Add confidence scores based on LLM response metadata

**Tests to write** (`tests/extraction/test_legal_llm.py`):
- Mock `OllamaProvider` with deterministic JSON responses
- Test entity extraction from sample German legal text
- Test relation extraction with pre-extracted entities
- Test ontology validation filtering

---

### TASK 3: Implement `LegalEnsembleExtractor` ⏱️ ~2h
> **Assignee**: Any coding assistant  
> **Branch**: `feat/law-graph`  
> **Depends on**: TASK 2

**Goal**: Implement merge logic in `src/kgbuilder/extraction/legal_ensemble.py`.

**Input files to read**:
- `src/kgbuilder/extraction/legal_ensemble.py` — **target file** (100 lines, config defined)
- `src/kgbuilder/extraction/ensemble.py` — reference `TieredExtractor` implementation
- `src/kgbuilder/extraction/legal_rules.py` — rule-based extractor (already implemented)
- `src/kgbuilder/extraction/legal_llm.py` — LLM extractor (from TASK 2)

**What to implement**:
1. `extract(text, ontology_classes)` → run rules extractor, then LLM extractor, then merge
2. `_merge_entities(rule_entities, llm_entities)`:
   - Match by normalized label + entity_type
   - Weighted confidence: `rules * rule_weight + llm * llm_weight`
   - Rule entities get boost if also found by LLM
   - Conflict resolution: prefer rule-based for known patterns, LLM for novel entities
3. `_merge_relations(rule_relations, llm_relations)`:
   - Match by (source, target, relation_type)
   - Similar weighted confidence merge
4. `_entities_match(e1, e2)` → fuzzy label matching (Levenshtein or contains)
5. `_relations_match(r1, r2)` → exact (source, target, type) matching

**Tests**: `tests/extraction/test_legal_ensemble.py`

---

### TASK 4: Enrich Decommissioning Ontology ⏱️ ~3h
> **Assignee**: Ontology/knowledge engineering assistant  
> **Branch**: `feat/law-graph`  
> **Priority**: 🟡 HIGH

**Goal**: Extend `plan-ontology-v1.0.owl` from 3 flat classes to a proper hierarchy.

**Context**: Current ontology has only `Activity`, `Component`, `Facility`. The KG already discovered 24+ node types (DomainConstant, Action, Plan, State, Organization, etc.) that are NOT in the ontology. This limits extraction quality.

**Input files**:
- `data/ontology/domain/plan-ontology-v1.0.owl` — current ontology
- Neo4j label distribution (see "Current State" above) — what the pipeline actually extracts
- `data/evaluation/competency_questions.json` — what the KG needs to answer
- wiki_alisa_kiko #100 — subclassing patterns to adopt

**Deliverables**:
- [ ] Updated OWL file: `data/ontology/domain/plan-ontology-v2.0.owl`
- [ ] Add classes: `Organization`, `Regulation`, `Process`, `WasteCategory`, `Permit`, `SafetySystem`, `Documentation`, `LegalProvision`, `NuclearMaterial`, `Transport`
- [ ] Add subclass hierarchy (e.g., `KernkraftwerkFacility rdfs:subClassOf Facility`)
- [ ] Add object properties: `governedBy`, `requires`, `produces`, `referencesLaw`, `issuedBy`
- [ ] Add SHACL shapes for the new classes
- [ ] Load into Fuseki and verify SPARQL queries

---

### TASK 5: Law Graph Phase B — Semantic Extraction ⏱️ ~4h
> **Assignee**: LLM coding assistant  
> **Branch**: `feat/law-graph`  
> **Depends on**: TASK 2, TASK 3

**Goal**: Run the legal LLM extractor on law text to extract semantic concepts (obligations, definitions, permissions) beyond structural XML parsing.

**What to implement**:
1. Update `scripts/build_law_graph.py` to add Phase B after structural import
2. For each Paragraf text: run `LegalEnsembleExtractor` to extract:
   - `Obligation` entities (Pflicht, muss, hat zu...)
   - `Definition` entities ("im Sinne dieses Gesetzes")
   - `Permission` entities (darf, kann, ist berechtigt)
   - `LegalActor` entities (Betreiber, Genehmigungsinhaber, Aufsichtsbehörde)
3. Store semantic entities as new nodes linked to their source Paragraf
4. Create cross-domain links: when a legal entity mentions a decommissioning concept

**Acceptance criteria**:
- [ ] Phase B extracts at least 50 semantic entities from AtG
- [ ] Entities linked to source Paragraf via `DEFINIERT_IN` relation
- [ ] Cross-references resolved to existing Paragraf nodes
- [ ] Results exported to JSON

---

### TASK 6: Cross-Domain KG Linking ⏱️ ~3h
> **Assignee**: Graph/NLP assistant  
> **Branch**: `feat/law-graph`  
> **Depends on**: TASK 5, TASK 4

**Goal**: Create explicit links between decommissioning KG entities and law graph entities.

**Approach**:
1. For each decommissioning entity, use `LawGraphRetriever.retrieve_for_entity()` to find relevant law paragraphs
2. Create `GOVERNED_BY` edges: `(Kernkraftwerk)-[:GOVERNED_BY]->(AtG §7)`
3. Create `DEFINED_IN` edges: `(Kernbrennstoff)-[:DEFINED_IN]->(AtG §2)`
4. Use embedding similarity for fuzzy matching (threshold ≥ 0.5)
5. Create `REFERENCES` edges for document mentions of law codes

**Deliverables**:
- [ ] Script `scripts/link_kg_to_laws.py`
- [ ] At least 20 cross-domain edges created
- [ ] Visualization query for Neo4j Browser

---

### TASK 7: Experiment Framework for A/B Comparison ⏱️ ~2h
> **Assignee**: Any coding assistant  
> **Branch**: `feat/law-graph`  
> **Priority**: 🟡 HIGH

**Goal**: Formalize the comparison between baseline KG and law-augmented KG.

**Metrics to capture** (per experiment run):
- Entity count by type
- Relationship count by type
- Ontology class coverage (% of ontology classes with ≥1 instance)
- Competency question answer rate
- Entity confidence distribution (mean, std, percentiles)
- New entities discovered only with law context
- Duplicate reduction rate

**Deliverable**: JSON report + markdown summary comparing:
1. **Baseline**: `LAW_GRAPH_ENABLED=false` — extract from documents only
2. **Law-Augmented**: `LAW_GRAPH_ENABLED=true` — extract with law context
3. **Law-Augmented + Extended Ontology**: with `plan-ontology-v2.0.owl`

---

## Execution Order

```
WEEK 1 (immediate):
  TASK 1 → Run comparison experiment NOW with current code
  TASK 4 → Enrich ontology (parallel, independent)

WEEK 2:
  TASK 2 → Implement LegalLLMExtractor
  TASK 3 → Implement LegalEnsembleExtractor (after TASK 2)

WEEK 3:
  TASK 5 → Phase B semantic extraction (after TASK 2+3)
  TASK 6 → Cross-domain linking (after TASK 5)
  TASK 7 → Full A/B comparison with all variants
```

---

## Environment Setup (for any assistant)

```bash
# Clone and setup
git clone git@github.com:DataScienceLabFHSWF/KnowledgeGraphBuilder.git
cd KnowledgeGraphBuilder
git checkout feat/law-graph
pip install -e ".[dev]"

# Start infrastructure
docker-compose up -d neo4j qdrant fuseki ollama

# Verify services
curl http://localhost:7474  # Neo4j
curl http://localhost:6333  # Qdrant
curl http://localhost:3030  # Fuseki
curl http://localhost:18134/api/tags  # Ollama

# Run tests
PYTHONPATH=src pytest tests/ -x -q

# Key environment variables
export NEO4J_PASSWORD=changeme
export OLLAMA_URL=http://localhost:18134
export OLLAMA_LLM_MODEL=qwen3:8b
export OLLAMA_EMBED_MODEL=qwen3-embedding:latest
export PYTHONPATH=$PWD/src:$PYTHONPATH
```
