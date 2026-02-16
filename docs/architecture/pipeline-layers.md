# Pipeline Layers

## Layer 1: Extraction

The most expensive phase (~6.8 hours for 33 documents). Produces a
checkpoint file with all entities and relations.

### Components

| Component | Module | Purpose |
|-----------|--------|---------|
| Question Generator | `agents/question_generator.py` | Generate ontology-driven research questions |
| Discovery Loop | `agents/discovery_loop.py` | Iterative retrieve-extract-measure cycle |
| Rule-Based Extractor | `extraction/rules.py` | Deterministic heuristic extraction |
| LLM Entity Extractor | `extraction/entity.py` | Ontology-guided LLM entity extraction |
| LLM Relation Extractor | `extraction/relation.py` | Relation extraction with constraint validation |
| Tiered Extractor | `extraction/ensemble.py` | Rules-first, LLM-fallback strategy |
| Ensemble Extractor | `extraction/ensemble.py` | Multi-extractor merge with confidence boosting |
| Text Aligner | `extraction/aligner.py` | Source-text span verification |
| Findings Synthesizer | `extraction/synthesizer.py` | Cross-document deduplication |
| Response Cache | `extraction/cache.py` | Persistent LLM response caching |

### Confidence Tuning

Six-stage pipeline applied after extraction:

| Stage | Module | What It Does |
|-------|--------|-------------|
| 1. Analyze | `confidence/analyzer.py` | Statistical profiling per entity type |
| 2. Boost | `confidence/booster.py` | Multi-source evidence boosting |
| 3. Calibrate | `confidence/calibrator.py` | Cross-pass normalization |
| 4. Coreference | `confidence/coreference.py` | Merge co-referent entities |
| 5. Vote | `confidence/voter.py` | Consensus-based type disambiguation |
| 6. Filter | `confidence/filter.py` | Adaptive threshold filtering |

## Layer 2: Enrichment

Fast phase (~15 min). Adds semantic metadata to extracted entities.

| Phase | Enricher | What It Adds |
|-------|----------|-------------|
| 1 | `DescriptionEnricher` | LLM-generated human-readable descriptions |
| 2 | `EmbeddingEnricher` | 384-dim semantic embeddings |
| 3 | `CompetencyQuestionEnricher` | 3-5 competency questions per entity |
| 4 | `TypeConstraintEnricher` | Semantic type compatibility scores |
| 5 | `AliasEnricher` | Synonyms, abbreviations, alternate names |

## Layer 3: Persistence

Fast phase (~5 min). Writes to stores and generates exports.

| Store | Module | What Gets Written |
|-------|--------|-------------------|
| Neo4j | `storage/neo4j_store.py` | Nodes + edges with all properties |
| Qdrant | `storage/vector.py` | 3 collections: chunks, entities, relations |
| Fuseki | `storage/rdf_store.py` | RDF triples (TBox + ABox) |

### Post-Persistence

- **SHACL validation** -- auto-generated shapes from ontology
- **Quality scoring** -- weighted composite score
- **Analytics** -- OWL-RL inference, SKOS enrichment, graph metrics
- **Export** -- JSON-LD, RDF/Turtle, Cypher, GraphML, N-Triples
