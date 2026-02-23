# KnowledgeGraphBuilder

**Ontology-driven Knowledge Graph construction pipeline** for building validated,
traceable knowledge graphs from unstructured documents using local LLMs.

Ingests documents (PDF, DOCX, PPTX, XML), extracts entities and relations guided
by an OWL ontology, assembles a validated knowledge graph in Neo4j, and exports
it in multiple standard formats (JSON-LD, RDF/Turtle, YARRRML, Cypher).

A minimal sample dataset is available at `data/smoke_test/` (ontology + text
file) for quick local experiments and to exercise the `scripts/quickstart.py`
workflow.

Part of a three-repository research ecosystem:

| Repository | Purpose |
|-----------|---------|
| **KnowledgeGraphBuilder** (this repo) | KG construction, validation, and export |
| [GraphQAAgent](https://github.com/DataScienceLabFHSWF/GraphQAAgent) | Ontology-informed GraphRAG QA agent |
| [OntologyExtender](https://github.com/DataScienceLabFHSWF/OntologyExtender) | Human-in-the-loop ontology extension |

---

## Table of Contents

- [What This Repository Does](#what-this-repository-does)
- [Pipeline Architecture](#pipeline-architecture)
- [Quick Start](#quick-start)
- [Build a KG from Your Own Data](#build-a-kg-from-your-own-data)
- [Infrastructure](#infrastructure)
- [Project Structure](#project-structure)
- [Module Reference](#module-reference)
- [Domain Pluggability](#domain-pluggability)
- [Validation and Quality Scoring](#validation-and-quality-scoring)
- [Experiment Framework](#experiment-framework)
- [Key Scripts](#key-scripts)
- [Technology Stack](#technology-stack)
- [Configuration](#configuration)
- [Development](#development)
- [API Documentation](#api-documentation)
- [Documentation Index](#documentation-index)
- [Related Work](#related-work)
- [License](#license)

---

## What This Repository Does

1. **Document ingestion** -- loads PDFs, DOCX, PPTX, and German law XML;
   chunks them semantically; embeds them into Qdrant for hybrid retrieval.
2. **Ontology-guided extraction** -- generates LLM prompts from OWL class and
   property definitions; extracts entities and relations with confidence
   scores and provenance verification (via `TextAligner`, inspired by
   Google's [LangExtract](Planning/LANGEXTRACT_EVAL.md) library).
3. **Autonomous discovery** -- iteratively generates competency questions,
   retrieves relevant chunks, and extracts additional facts until coverage
   converges (see [Architecture](Planning/02_ARCHITECTURE.md) Section 2).
4. **Tiered extraction** -- deterministic rule-based heuristics run first
   (fast, high precision); the LLM extractor handles remaining items.
   An ensemble layer merges and deduplicates results with overlap-boosted
   confidence.
5. **Confidence tuning** -- statistical analysis, multi-source boosting,
   coreference resolution, LLM consensus voting, and quality filtering.
6. **Enrichment pipeline** -- five-phase post-extraction enrichment:
   LLM descriptions, semantic embeddings, competency questions, type
   constraints, and alias generation.
7. **KG assembly and validation** -- assembles nodes and edges in Neo4j;
   validates against SHACL shapes generated from the ontology; runs pySHACL
   and (optionally) SHACL2FOL/Vampire static checks; calculates automated
   quality scores.
8. **Analytics** -- OWL-RL inference, SKOS enrichment, graph metrics
   (centrality, connectivity, coverage).
9. **Export** -- JSON-LD, RDF/Turtle, Cypher, GraphML, N-Triples, and
   plain JSON.
10. **Experiment framework** -- manages multi-variant runs with W&B logging,
    checkpointing, automated SHACL quality scoring, and HTML reports.
11. **KG versioning** -- snapshot, restore, and diff operations for
    reproducible experiment tracking.

The pipeline is **ontology-agnostic**: it reads whatever OWL ontology is
provided and auto-generates extraction prompts, SHACL shapes, and validation
rules from it. Different knowledge domains share the same code -- only the
ontology and document loaders change.

---

## Pipeline Architecture

The system uses a **three-layer processing model** that separates the
expensive extraction phase from fast enrichment and persistence:

```
 LAYER 1: EXTRACTION  (~6.8 h for 33 docs)
 ──────────────────────────────────────────────────────
   OWL Ontology
     -> Question Generation (competency-question driven)
     -> Iterative Discovery Loop
          Retrieve chunks (Qdrant)  ->  Tiered Extraction
          (Rule-based heuristics -> LLM fallback)
          ->  Ensemble merge  ->  Synthesize & deduplicate
     -> Confidence Tuning (analyze, boost, calibrate,
        coreference, vote, filter)
   Output: checkpoint.json

 LAYER 2: ENRICHMENT  (~15 min)
 ──────────────────────────────────────────────────────
   Load checkpoint
     -> Phase 1: LLM descriptions per entity
     -> Phase 2: 384-dim semantic embeddings
     -> Phase 3: Competency questions per entity
     -> Phase 4: Type constraint scoring
     -> Phase 5: Alias / synonym generation
   Output: enriched entities + relations

 LAYER 3: PERSISTENCE  (~5 min)
 ──────────────────────────────────────────────────────
   Write Neo4j  ->  Write Qdrant  ->  Write RDF/Fuseki
     -> Generate exports (JSON-LD, Cypher, Turtle, ...)
     -> SHACL validation & quality scoring
     -> Analytics (OWL-RL inference, SKOS, graph metrics)
   Output: populated stores + export files + quality report
```

Extraction (Layer 1) is the bottleneck. By checkpointing after extraction,
enrichment and persistence can be re-run in ~20 min without re-extracting
(94% time savings on iterative refinement).

See [Planning/02_ARCHITECTURE.md](Planning/02_ARCHITECTURE.md) for the full
technical design including the iterative discovery loop, entity/relation
extraction details, and stopping criteria.

---

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/DataScienceLabFHSWF/KnowledgeGraphBuilder.git
cd KnowledgeGraphBuilder
cp .env.example .env          # configure endpoints
pip install -e ".[dev]"
./scripts/setup_shacl2fol.sh  # optional: download SHACL2FOL dependencies

# 2. Start infrastructure
docker-compose up -d neo4j qdrant fuseki ollama

# 3. Run the full pipeline (single iteration for quick test)
source .venv/bin/activate
export PYTHONPATH=$PWD/src:$PYTHONPATH
python scripts/full_kg_pipeline.py --max-iterations 1

# With law graph context augmentation
LAW_GRAPH_ENABLED=true python scripts/full_kg_pipeline.py --max-iterations 1
```

For law-specific pipeline setup, see [QUICKSTART_LAW_GRAPH.md](QUICKSTART_LAW_GRAPH.md).

See `python scripts/full_kg_pipeline.py --help` for all CLI options including
`--enrich-only`, `--skip-enrichment`, `--skip-analytics`, `--checkpoint`, and
`--dry-run`.

---

## Build a KG from Your Own Data

The pipeline is domain-agnostic. You need **three inputs** to build a Knowledge
Graph for any domain:

| Input | Format | Example |
|-------|--------|---------|
| **Ontology** | OWL / RDF / TTL file | `data/ontology/my-domain.owl` |
| **Documents** | PDF, DOCX, PPTX, TXT, MD | `data/my-domain-docs/` |
| **Competency Questions** *(optional)* | Plain text, one per line | `data/my-cqs.txt` |

### 1. Prepare your inputs

```
data/
  ontology/
    my-domain.owl            # your OWL ontology
  my-domain-docs/
    report-a.pdf             # your source documents
    manual-b.docx
    ...
  my-cqs.txt                 # optional: competency questions
```

**Ontology** -- an OWL file defining the classes and properties you want to
extract. The pipeline reads class labels and relation definitions from it to
guide entity and relation extraction.

**Documents** -- any number of PDFs, Word files, PowerPoint decks, or plain-text
files. These are chunked, embedded, and indexed into Qdrant for retrieval.

**Competency Questions** -- natural-language questions that your KG should be
able to answer (e.g. *"Which suppliers deliver hazardous materials?"*). They
steer the iterative discovery loop toward relevant entities.

### 2. Start infrastructure

```bash
docker-compose up -d neo4j qdrant fuseki ollama
```

### 3. Run the quickstart script

```bash
python scripts/quickstart.py \
    --ontology data/ontology/my-domain.owl \
    --documents data/my-domain-docs/ \
    --cqs data/my-cqs.txt \
    --max-iterations 2
```

The script runs all four stages automatically:

1. **Upload ontology** to Fuseki (creates a SPARQL dataset)
2. **Ingest documents** -- parse, chunk, embed, index into Qdrant
3. **Extract entities & relations** -- ontology-guided LLM extraction with
   iterative discovery loop
4. **Validate** -- SHACL conformance check and quality scoring

Results are written to `output/<domain>/` and persisted in Neo4j.

### CLI options

| Flag | Default | Description |
|------|---------|-------------|
| `--ontology` | *(required)* | OWL ontology file path |
| `--documents` | *(required)* | Directory with source documents |
| `--cqs` | none | Competency questions file |
| `--max-iterations` | `2` | Discovery loop iterations |
| `--questions-per-class` | `3` | Research questions per class |
| `--confidence-threshold` | `0.5` | Min entity confidence |
| `--top-k` | `10` | Chunks per retrieval query |
| `--extensions` | `.pdf .docx .pptx .txt .md` | File types to ingest |
| `--dry-run` | off | Extract without DB writes |
| `--skip-ingest` | off | Skip if docs already indexed |
| `--skip-validation` | off | Skip SHACL validation |

### 4. Explore the result

Open Neo4j Browser at <http://localhost:7474> and run:

```cypher
MATCH (n) WHERE n.graph_type = 'my-domain' RETURN n LIMIT 100
```

A JSON checkpoint with all entities and relations is also saved in
`output/<domain>/checkpoint.json`.

### Templates

- **Profile config**: [`data/profiles/template.json`](data/profiles/template.json)
- **CQ file template**: [`data/examples/competency_questions_template.txt`](data/examples/competency_questions_template.txt)

---

## Infrastructure

All services run via Docker Compose:

```bash
docker-compose up -d
```

| Service | Port | Purpose |
|---------|------|---------|
| Neo4j | 7474 / 7687 | Knowledge graph storage (Cypher queries) |
| Qdrant | 6333 | Vector similarity search (384-dim embeddings) |
| Fuseki | 3030 | RDF/SPARQL ontology store |
| Ollama | 11434 | Local LLM inference and embedding generation |

---

## Project Structure

```
src/kgbuilder/
  core/             Protocols, data models, exceptions, config
  document/         Document loaders (PDF, DOCX, PPTX, law XML) and chunking
  embedding/        Embedding generation + structured LLM output (Ollama)
  extraction/       Entity and relation extraction (LLM + rule-based + ensemble)
                    Text alignment (aligner.py), extraction chains, caching
  confidence/       Confidence tuning (analyzer, booster, calibrator,
                    coreference resolver, filter, consensus voter)
  enrichment/       Post-extraction enrichment pipeline (5 phases)
  assembly/         KG assembly (SimpleKGAssembler, multi-store KGBuilder)
  validation/       SHACL shape generation, pySHACL validator, SHACL2FOL
                    static validator, rules engine, consistency checker,
                    quality scorer, reporter
  storage/          Neo4j, Qdrant, Fuseki, RDF, export, law retrieval
  analytics/        OWL-RL inference, SKOS enrichment, graph metrics
  retrieval/        BM25 + dense fusion retrieval
  agents/           Iterative discovery loop, question generator
  experiment/       Experiment manager, checkpoint, analyzer, plotter, reporter
  pipeline/         Orchestrators (build pipeline, confidence tuning,
                    stopping criterion, checkpoint CLI)
  versioning/       KG snapshot, restore, diff
  telemetry/        Observability integrations (LangSmith)
  cli.py            Typer CLI entry point

scripts/            Pipeline entry points and utility scripts
tests/              Unit and integration tests
data/
  ontology/         OWL ontologies (domain, legal, generated shapes)
  profiles/         Pipeline config overlays (per-domain settings)
  law_html/         German law XML files (from gesetze-im-internet.de)
Planning/           Architecture docs, interface specs, evaluation notes
```

---

## Module Reference

### Core (`core/`)

| Module | Key Classes | Purpose |
|--------|------------|---------|
| `protocols.py` | `DocumentLoader`, `EntityExtractor`, `RelationExtractor`, `EmbeddingProvider`, `LLMProvider`, `GraphStore`, `OntologyService` | Protocol definitions (dependency injection interfaces) |
| `models.py` | `Document`, `Chunk`, `Evidence`, `ExtractedEntity`, `ExtractedRelation`, `OntologyClassDef`, `OntologyRelationDef` | Shared data models (dataclasses) |
| `exceptions.py` | `KGBuilderError`, `DocumentLoadError`, `ExtractionError`, `ValidationError`, `StorageError` | Domain-specific exception hierarchy |
| `config.py` | `LLMConfig`, `EmbeddingConfig`, `Neo4jConfig`, `QdrantConfig` | Pydantic configuration models with env var support |

### Document Processing (`document/`)

| Module | Key Classes | Purpose |
|--------|------------|---------|
| `loaders/pdf.py` | `PDFLoader` | PDF ingestion via pdfplumber |
| `loaders/office.py` | `DOCXLoader`, `PPTXLoader` | Office document ingestion |
| `loaders/law_xml.py` | `LawXMLReader`, `LawDocument`, `LawParagraph` | German law XML parser (gesetze-im-internet.de) |
| `loaders/law_adapter.py` | `LawDocumentAdapter` | Converts `LawDocument` to KGB `Document` format |
| `chunking/strategies.py` | `SentenceChunker`, `ParagraphChunker`, `SemanticChunker`, `FixedSizeChunker` | Four chunking strategies |

### Extraction (`extraction/`)

| Module | Key Classes | Purpose |
|--------|------------|---------|
| `entity.py` | `LLMEntityExtractor` | Ontology-guided entity extraction via LLM |
| `relation.py` | `LLMRelationExtractor` | Ontology-guided relation extraction with domain/range validation |
| `rules.py` | `RuleBasedExtractor` | Deterministic heuristic extraction (regex, gazetteers) |
| `ensemble.py` | `TieredExtractor`, `TieredRelationExtractor`, `EnsembleExtractor` | Tiered (rules then LLM) and ensemble merge strategies |
| `legal_rules.py` | `LegalRuleBasedExtractor` | Legal-domain rules (paragraph refs, authorities, deontic modalities) |
| `legal_llm.py` | `LegalLLMExtractor` | Legal-domain LLM extractor with German prompts |
| `legal_ensemble.py` | `LegalEnsembleExtractor` | Legal rule + LLM merger with weighted confidence |
| `aligner.py` | `TextAligner`, `AlignmentResult`, `AlignmentStatus` | Source-text verification (inspired by LangExtract `WordAligner`) |
| `synthesizer.py` | `FindingsSynthesizer` | Cross-document entity deduplication and relation consolidation |
| `chains.py` | `build_entity_chain`, `build_relation_chain` | LangChain-style extraction chain builders |
| `cache.py` | `OllamaResponseCache` | Persistent disk cache for LLM responses |
| `benchmarking.py` | `StructuredGenerationBenchmark` | Benchmark structured output success rate |

### Confidence (`confidence/`)

| Module | Key Classes | Purpose |
|--------|------------|---------|
| `analyzer.py` | `ConfidenceAnalyzer` | Statistical analysis (mean, std, percentiles, IQR anomaly detection) |
| `booster.py` | `ConfidenceBooster` | Multi-source boosting (+0.15 per additional document) |
| `calibrator.py` | `ConfidenceCalibrator` | Cross-pass confidence normalization |
| `coreference.py` | `CoreferenceResolver` | Merge entities referring to the same real-world object |
| `filter.py` | `ConfidenceFilter` | Adaptive threshold quality filtering |
| `voter.py` | `ConsensusVoter` | Multi-source voting for entity type disambiguation |

### Enrichment (`enrichment/`)

| Module | Key Classes | Purpose |
|--------|------------|---------|
| `pipeline.py` | `SemanticEnrichmentPipeline` | Five-phase enrichment orchestrator |
| `enrichers.py` | `DescriptionEnricher`, `EmbeddingEnricher`, `CompetencyQuestionEnricher`, `TypeConstraintEnricher`, `AliasEnricher` | Individual enrichment phases |
| `protocols.py` | `Enricher` | Protocol for enrichment plugins |

### Validation (`validation/`)

| Module | Key Classes | Purpose |
|--------|------------|---------|
| `shacl_generator.py` | `SHACLShapeGenerator` | Generate SHACL shapes from OWL ontology |
| `shacl_validator.py` | `SHACLValidator` | pySHACL validation with auto Neo4j-to-RDF conversion |
| `static_validator.py` | `StaticValidator` | SHACL2FOL + Vampire satisfiability checking |
| `rules_engine.py` | `RulesEngine`, `DomainRangeRule`, `FunctionalPropertyRule`, `TransitiveRule` | Semantic constraint rules |
| `consistency_checker.py` | `ConsistencyChecker` | Type/value conflict detection |
| `scorer.py` | `KGQualityScorer`, `KGQualityReport` | Weighted quality score (SHACL + coverage + consistency) |
| `reporter.py` | `ValidationReporter` | Markdown/HTML validation reports |

### Assembly and Storage (`assembly/`, `storage/`)

| Module | Key Classes | Purpose |
|--------|------------|---------|
| `assembly/kg_builder.py` | `KGBuilder` | Multi-store write orchestrator (Neo4j + Qdrant + Fuseki) |
| `assembly/simple_kg_assembler.py` | `SimpleKGAssembler` | Simplified assembler for single-store use |
| `storage/neo4j_store.py` | `Neo4jGraphStore` | Cypher-based graph CRUD operations |
| `storage/rdf_store.py` | `RDFStore` | RDF triple store (Fuseki SPARQL endpoint) |
| `storage/vector.py` | `QdrantVectorStore` | Vector similarity search operations |
| `storage/export.py` | `KGExporter` | Multi-format export (JSON-LD, Turtle, Cypher, GraphML) |
| `storage/law_retrieval.py` | `LawRetrievalService` | Law-graph-specific retrieval for hybrid QA |

### Analytics (`analytics/`)

| Module | Key Classes | Purpose |
|--------|------------|---------|
| `inference.py` | `Neo4jInferenceEngine` | OWL-RL inference (transitive closure, symmetry, inverse) |
| `skos.py` | `SKOSEnricher` | SKOS broader/narrower taxonomy enrichment |
| `metrics.py` | `GraphMetrics` | Node/edge counts, centrality, typed coverage analysis |
| `pipeline.py` | `AnalyticsPipeline` | Analytics orchestrator (inference + SKOS + metrics) |

### Experiment and Pipeline (`experiment/`, `pipeline/`)

| Module | Key Classes | Purpose |
|--------|------------|---------|
| `experiment/manager.py` | `ExperimentManager` | Multi-variant experiment orchestration with W&B |
| `experiment/checkpoint.py` | `CheckpointManager` | Checkpoint save/load for extraction results |
| `experiment/analyzer.py` | `ExperimentAnalyzer` | Cross-variant performance analysis |
| `experiment/plotter.py` | `ExperimentPlotter` | Convergence and comparison plots |
| `experiment/reporter.py` | `ExperimentReporter` | HTML experiment reports |
| `pipeline/orchestrator.py` | `BuildPipeline`, `BuildPipelineConfig` | Top-level pipeline with stopping criteria |
| `pipeline/stopping_criterion.py` | `StoppingCriterionChecker` | Coverage, confidence, stability checks |
| `pipeline/confidence_tuning.py` | `ConfidenceTuningPipeline` | Six-stage confidence refinement orchestrator |
| `pipeline/checkpoint_cli.py` | `enrich_from_checkpoint` | Standalone checkpoint re-enrichment |

---

## Domain Pluggability

The pipeline is **ontology-agnostic**. Adding a new knowledge domain requires
no code changes to the core pipeline -- provide domain-specific components
and a config profile:

```
Step 1: Ontology
   Create/adopt OWL ontology -> load into Fuseki dataset

Step 2: Documents
   Place source files in data/<domain>/
   (or implement a custom DocumentLoader)

Step 3: Extractors (optional)
   Add domain-specific rules:
     extraction/<domain>_rules.py    -- regex/gazetteers
     extraction/<domain>_llm.py      -- specialized prompts
     extraction/<domain>_ensemble.py -- rule + LLM merge

Step 4: Profile
   Create data/profiles/<domain>.json with config overrides

Step 5: Run
   python scripts/full_kg_pipeline.py --profile data/profiles/<domain>.json
```

### Implemented Domains

| Domain | Ontology | Documents | Extractors |
|--------|----------|-----------|------------|
| Nuclear Decommissioning | `plan-ontology` (Fuseki) | 33 PDFs | Generic LLM + rules |
| German Federal Law | `law-ontology-v1.0.owl` (LKIF-Core + ELI) | ~6,800 XML files | `legal_rules.py` + `legal_llm.py` + `legal_ensemble.py` |

See [Planning/02_ARCHITECTURE.md](Planning/02_ARCHITECTURE.md) Section 12 for
the full domain pluggability design.

---

## Validation and Quality Scoring

Every KG build is scored automatically. The scorer generates SHACL shapes
from the OWL ontology, runs pySHACL against the graph, and computes a
weighted quality score:

| Metric | Description |
|--------|-------------|
| **Consistency** | SHACL2FOL satisfiability (optional, requires Vampire) |
| **SHACL conformance** | pySHACL violation count (always runs) |
| **Class coverage** | Fraction of ontology classes present in the graph |
| **Combined score** | Weighted aggregate in [0, 1] |

Additional validation layers:
- **Semantic rules engine** -- domain/range, functional property, transitive
  and inverse property checks
- **Consistency checker** -- detects type conflicts, value conflicts,
  cardinality violations

Run standalone:
```bash
PYTHONPATH=src python scripts/run_kg_scoring.py
```

See [Planning/VALIDATION_PLAN.md](Planning/VALIDATION_PLAN.md) for the full
validation architecture.

---

## Experiment Framework

The experiment framework supports systematic, reproducible evaluation:

```bash
# Single experiment run with W&B logging
python scripts/run_single_experiment.py

# Run experiment from config file
python scripts/run_experiment.py --config examples/experiment_baseline.json
```

Features:
- **Multi-variant runs** with automatic checkpointing
- **W&B integration** for metric tracking and visualization
- **SHACL quality scoring** per run (auto-generated from ontology)
- **HTML reports** with convergence analysis and variant comparison
- **Checkpoint-based re-enrichment** (`--enrich-only` mode, 94% time savings)

See [examples/ABLATION_STUDY_GUIDE.md](examples/ABLATION_STUDY_GUIDE.md) for
ablation study setup.

---

## Key Scripts

| Script | Purpose |
|--------|---------|
| `quickstart.py` | **One-command KG build for any domain** (recommended entry point) |
| `full_kg_pipeline.py` | End-to-end KG construction pipeline (all domains) |
| `build_law_graph.py` | German federal law KG (structure-first, then semantic) |
| `build_law_ontology.py` | Generate the legal ontology OWL file |
| `run_kg_scoring.py` | Standalone SHACL quality scoring |
| `run_single_experiment.py` | Single experiment with W&B metrics |
| `run_experiment.py` | Experiment from JSON config |
| `validate_kg_complete.py` | Full KG validation suite |
| `manage_versions.py` | KG snapshot/restore/diff CLI |
| `enrich_checkpoint.py` | Standalone checkpoint enrichment |
| `load_ontology_to_fuseki.py` | Upload ontology to Fuseki SPARQL store |
| `merge_legal_ontologies.py` | Merge LKIF-Core + ELI into legal foundations |

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11+ |
| LLM | Ollama (qwen3:8b, llama3.1:8b) |
| Embeddings | Ollama (qwen3-embedding, nomic-embed-text, 384-dim) |
| Graph DB | Neo4j 5.x |
| Vector DB | Qdrant |
| RDF Store | Apache Fuseki 4.x |
| Validation | pySHACL, SHACL2FOL + Vampire |
| Experiments | Weights & Biases |
| Logging | structlog (structured JSON) |
| Testing | pytest (with coverage) |
| Linting | ruff, mypy (strict), black |

---

## Configuration

Pipeline configuration uses Pydantic models with environment variable support:

```bash
# .env file (or export directly)
OLLAMA_URL=http://localhost:18134
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=kgbuilder
QDRANT_URL=http://localhost:6333
FUSEKI_URL=http://localhost:3030
```

Per-domain overrides via JSON profiles in `data/profiles/`:
```bash
python scripts/full_kg_pipeline.py --profile data/profiles/legal.json
```

See [Planning/03_INTERFACES.md](Planning/03_INTERFACES.md) for all protocol
definitions and configuration models.

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run tests with coverage
pytest tests/ --cov=src/kgbuilder --cov-report=term-missing

# Lint and type check
ruff check src/ tests/
mypy src/ --strict

# Format
black src/ tests/ scripts/
```

Code style: PEP 8, 100-char line length, full type hints (Python 3.11+
annotations), Google-style docstrings.

See [.github/copilot-instructions.md](.github/copilot-instructions.md) for
complete coding guidelines.

---

## API Documentation

Auto-generated API documentation is available via MkDocs:

```bash
# Install docs dependencies
pip install -e ".[docs]"

# Serve documentation locally
mkdocs serve

# Build static site
mkdocs build
```

The documentation is generated from module docstrings using
[mkdocstrings](https://mkdocstrings.github.io/) and covers all public APIs.

---

## Documentation Index

| Document | Contents |
|----------|----------|
| [Planning/01_ACADEMIC_OVERVIEW.md](Planning/01_ACADEMIC_OVERVIEW.md) | Research context, motivation, and related work |
| [Planning/02_ARCHITECTURE.md](Planning/02_ARCHITECTURE.md) | Pipeline architecture, discovery loop, extraction details |
| [Planning/03_INTERFACES.md](Planning/03_INTERFACES.md) | Protocol definitions and interface contracts |
| [Planning/04_ISSUES_BACKLOG.md](Planning/04_ISSUES_BACKLOG.md) | Implementation status and roadmap |
| [Planning/VALIDATION_PLAN.md](Planning/VALIDATION_PLAN.md) | SHACL validation and scoring architecture |
| [Planning/LANGEXTRACT_EVAL.md](Planning/LANGEXTRACT_EVAL.md) | Evaluation of Google LangExtract (adopted patterns) |
| [Planning/IMPLEMENTATION_SUMMARY.md](Planning/IMPLEMENTATION_SUMMARY.md) | Law graph implementation summary |
| [Planning/LAW_ONTOLOGY_RATIONALE.md](Planning/LAW_ONTOLOGY_RATIONALE.md) | Legal ontology design decisions |
| [QUICKSTART_LAW_GRAPH.md](QUICKSTART_LAW_GRAPH.md) | Quick start for German law graph |
| [data/README.md](data/README.md) | Data directory layout and sources |
| [examples/ABLATION_STUDY_GUIDE.md](examples/ABLATION_STUDY_GUIDE.md) | Ablation study setup guide |

---

## Related Work

- **LLMs4OL** (Babaei Giglou et al., 2023) -- Zero-shot ontology learning
- **OntoAxiom** (Bakker et al., 2025) -- Benchmark for OWL axiom identification
- **OLLM** (Lo et al., 2024) -- End-to-end ontology induction with LLMs
- **SHACL2FOL** (Ahmetaj et al.) -- Static SHACL validation via first-order logic
- **pySHACL** -- RDFLib-based SHACL validation engine
- **LKIF-Core** -- Legal Knowledge Interchange Format ontology
- **ELI** -- European Legislation Identifier ontology
- **LangExtract** (Google) -- Few-shot structured extraction
  ([evaluation](Planning/LANGEXTRACT_EVAL.md))

---

## License

MIT -- see [LICENSE](LICENSE)
