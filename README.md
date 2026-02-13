# KnowledgeGraphBuilder

**Ontology-driven Knowledge Graph construction pipeline** for building, validating, and exporting knowledge graphs from unstructured documents.

Part of a three-repo research ecosystem:

| Repository | Purpose |
|-----------|---------|
| **KnowledgeGraphBuilder** (this repo) | KG construction, validation, and export |
| [GraphQAAgent](https://github.com/DataScienceLabFHSWF/GraphQAAgent) | Ontology-informed GraphRAG QA agent |
| [OntologyExtender](https://github.com/DataScienceLabFHSWF/OntologyExtender) | Human-in-the-loop ontology extension |

---

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Current Status](#current-status)
- [Module Overview](#module-overview)
- [Usage](#usage)
- [Infrastructure](#infrastructure)
- [Project Structure](#project-structure)
- [Development](#development)
- [License](#license)

---

## Quick Start

### 1. Setup

```bash
cp .env.example .env      # configure endpoints
pip install -e ".[dev]"    # install with dev dependencies

# start infrastructure
docker-compose up -d neo4j qdrant fuseki ollama
```

### 2. Run the Full Pipeline

```bash
# activate venv + set PYTHONPATH
source .venv/bin/activate
export PYTHONPATH=$PWD/src:$PYTHONPATH

# full pipeline on all documents (background)
nohup python scripts/full_kg_pipeline.py --max-iterations 1 \
  > pipeline_$(date +%Y%m%d_%H%M%S).log 2>&1 &

# or with law graph context augmentation (recommended)
LAW_GRAPH_ENABLED=true nohup python scripts/full_kg_pipeline.py --max-iterations 1 \
  > pipeline_law_$(date +%Y%m%d_%H%M%S).log 2>&1 &

# or smoke test
python scripts/full_kg_pipeline.py --smoke-test
```

### 3. Build the Law Graph (new)

**Easy way (recommended):**
```bash
# Run the law graph pipeline (interactive)
./scripts/run_law_graph.sh

# Or run in background
./scripts/run_law_graph.sh --background

# Specific laws only
./scripts/run_law_graph.sh --laws AtG StrlSchG

# Dry run (no database writes)
./scripts/run_law_graph.sh --dry-run --skip-embed
```

**Manual way:**
```bash
# Activate virtual environment and set PYTHONPATH
source .venv/bin/activate
export PYTHONPATH=$PWD/src:$PYTHONPATH

# Run the dedicated law graph pipeline
python scripts/build_law_graph.py --laws AtG StrlSchG

# Or run in background with logging
nohup python scripts/build_law_graph.py > law_graph.log 2>&1 &
```

**What it does:**
- **Parses** German law XML files from `data/law_html/` (BJNR*.xml format)
- **Extracts** entities directly from XML structure (Gesetzbuch, Paragraf, Abschnitt)
- **Creates** relations from XML structure (teilVon, referenziert) — no LLM needed
- **Embeds** paragraph text into Qdrant for retrieval/QA
- **Stores** entities + relations in Neo4j
- **Exports** results to JSON files

**Key difference:** This is a **structure-first pipeline** that exploits the highly structured XML format. No competency questions or iterative discovery needed — the XML structure IS the knowledge graph!

### CLI Options

```bash
python scripts/full_kg_pipeline.py --help
```

Key flags:
  --max-iterations N        Discovery loop iterations (default: 3)
  --smoke-test              Quick test on minimal subset
  --skip-discovery          Skip discovery phase
  --skip-enrichment         Skip enrichment phase
  --skip-confidence-tuning  Skip confidence tuning phase
  --skip-analytics          Skip analytics/inference phase
  --skip-validation         Skip validation
  --enrich-only             Re-enrich from checkpoint
  --checkpoint PATH         Checkpoint file to resume from
  --wandb-enabled           Enable W&B experiment tracking
  --documents PATH          Input documents directory
  --output PATH             Output directory

Environment variables:
  LAW_GRAPH_ENABLED=true    Enable law graph context augmentation (default: false)
  LAW_GRAPH_COLLECTION=lawgraph  Qdrant collection name for law graph (default: lawgraph)
  LAW_GRAPH_MAX_RESULTS=3   Max law paragraphs to retrieve per chunk (default: 3)
```

---

## Architecture

The pipeline is **ontology-agnostic**: it reads whatever ontology is loaded in Fuseki and generates extraction prompts from it. Different knowledge domains (decommissioning, law, etc.) share the same pipeline — only the ontology, document loaders, and rule-based extractors change.

```
┌─────────────────────────────────────────────────────────────────────┐
│                     KG CONSTRUCTION PIPELINE                         │
│                     (shared across all domains)                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. DOCUMENT INGESTION          2. RETRIEVAL & EXTRACTION            │
│  ┌──────────────────────┐       ┌─────────────────────────┐         │
│  │ PDF/DOCX/PPTX/XML    │       │ BM25 + Dense fusion     │         │
│  │ Semantic chunking     │──────►│ LLM entity extraction   │         │
│  │ Embedding (Ollama)    │       │ LLM relation extraction │         │
│  │ Qdrant indexing       │       │ Ontology-guided prompts │         │
│  └──────────────────────┘       └────────────┬────────────┘         │
│                                               │                      │
│  3. AUTONOMOUS DISCOVERY        4. CONFIDENCE TUNING                 │
│  ┌──────────────────────┐       ┌─────────────────────────┐         │
│  │ Question generation   │       │ Statistical analysis    │         │
│  │ Iterative extraction  │◄─────►│ Multi-source boosting   │         │
│  │ Findings synthesis    │       │ Coreference resolution  │         │
│  │ Deduplication         │       │ Calibration & filtering │         │
│  └──────────────────────┘       └────────────┬────────────┘         │
│                                               │                      │
│  5. ENRICHMENT                  6. ASSEMBLY & VALIDATION             │
│  ┌──────────────────────┐       ┌─────────────────────────┐         │
│  │ LLM descriptions      │       │ Neo4j KG assembly       │         │
│  │ Embedding enrichment  │──────►│ SHACL validation        │         │
│  │ CQ enrichment         │       │ Rules engine            │         │
│  │ Type constraints      │       │ Consistency checking    │         │
│  └──────────────────────┘       └────────────┬────────────┘         │
│                                               │                      │
│  7. ANALYTICS & EXPORT          8. VERSIONING                        │
│  ┌──────────────────────┐       ┌─────────────────────────┐         │
│  │ OWL-RL inference      │       │ Snapshot creation       │         │
│  │ SKOS enrichment       │◄─────►│ Diff & restore          │         │
│  │ Graph metrics         │       │ Content hashing         │         │
│  │ JSON-LD / RDF export  │       │ Experiment tracking     │         │
│  └──────────────────────┘       └─────────────────────────┘         │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

For detailed design, see [Planning/02_ARCHITECTURE.md](Planning/02_ARCHITECTURE.md) and [Planning/03_INTERFACES.md](Planning/03_INTERFACES.md).

### How Domains Plug In

The pipeline is modular — adding a new knowledge domain requires:

| Component | What to provide | Shared? |
|-----------|----------------|--------|
| **Ontology** (OWL) | Domain-specific classes + relations | No — each domain has its own |
| **Document Loader** | Reads source format → KGB `Document` objects | Reusable (PDF, DOCX shared; XML loader for law) |
| **Rule-Based Extractor** | Domain regex patterns + gazetteers | No — domain-specific patterns |
| **LLM Extractor** | Ontology-guided (auto-generated prompts) | Yes — same code, different ontology |
| **Storage** | Fuseki dataset + Qdrant collection + Neo4j labels | Namespace-separated, same infra |

Currently supported domains:

| Domain | Ontology | Status |
|--------|----------|--------|
| **Nuclear Decommissioning** | `plan-ontology-v1.0.owl` | ✅ Production |
| **German Federal Law** | `law-ontology-v1.0.owl` (planned) | 🚧 Stubs + ontologies downloaded |

---

## Current Status

**Pipeline**: Fully operational on 33 German nuclear decommissioning PDFs (~126 MB).  
**Law Graph**: ✅ **Integrated** — Law graph now informs KG building with legal context augmentation.

### Law Graph Integration

The KG pipeline can now be **informed by legal context** from the German federal law graph. When enabled (`LAW_GRAPH_ENABLED=true`), the system:

- **Retrieves relevant legal paragraphs** for each document chunk being processed
- **Augments LLM prompts** with legal context (laws, regulations, obligations)
- **Improves entity extraction accuracy** by providing domain-specific legal knowledge
- **Maintains backward compatibility** — works with or without law graph

**Current State**: 
- ✅ Law graph built (858 entities, 3,797 relations, 717 embeddings)
- ✅ Law graph retrieval service implemented and tested
- ✅ Pipeline integration complete and verified
- 🔄 **Next**: Compare KG quality with vs. without law graph context

**Law Graph Stats**:
- **Entities**: 858 (719 Paragraf, 134 Abschnitt, 5 Gesetzbuch)
- **Relations**: 3,797 (structural + semantic)
- **Embeddings**: 717 paragraphs (Qdrant collection: `lawgraph`, dim=4096)
- **Coverage**: 5 nuclear-relevant laws (AtG, BBergG, BImSchG, KrWG, StrlSchG)

### KG Quality Comparison: With vs. Without Law Graph

We now have the capability to **compare KG quality** when informed by legal context:

**Current Baseline**: KG built from decommissioning documents only  
**Next Experiment**: KG built with law graph context augmentation

**Expected Impact**:
- **Higher precision** in legal entity recognition (permits, regulations, authorities)
- **Better relation extraction** for compliance and regulatory relationships  
- **Improved consistency** with German legal terminology and concepts
- **Enhanced domain accuracy** for nuclear decommissioning processes

**Comparison Metrics**:
- Entity extraction F1-score, precision, recall
- Relation extraction accuracy and completeness
- Ontology alignment and constraint satisfaction
- Legal concept coverage and terminology consistency

### Phases

| Phase | Name | Status | Description |
|-------|------|--------|-------------|
| 1 | Document Ingestion | ✅ Complete | PDF/DOCX/PPTX loading, semantic chunking, Qdrant indexing |
| 2 | Retrieval & Extraction | ✅ Complete | BM25 + dense fusion, LLM entity/relation extraction |
| 3 | KG Assembly & Validation | ✅ Complete | Neo4j assembly, SHACL validation, multi-format export |
| 4 | Autonomous Discovery | ✅ Complete | Question generation, iterative discovery loop, synthesis |
| 5 | Confidence Tuning | ✅ Complete | Analyzer, booster, calibrator, coreference, voter, filter |
| 6 | Relation Extraction | ✅ Complete | Cross-document relation extraction, domain/range validation |
| 7 | KG Storage & Export | ✅ Complete | Neo4j, Qdrant, Fuseki, 5-format export (JSON-LD, RDF, etc.) |
| 8 | Validation Pipeline | ✅ Complete | SHACL shapes, rules engine, consistency checker, reporter |
| 9 | QA Evaluation | ✅ Complete | QA datasets, query executor, metrics (F1, accuracy, coverage) |
| 10 | Experiment Framework | ✅ Complete | Manager, analyzer, plotter, reporter, checkpointing |
| 11 | High-Performance Opts | ✅ Complete | Response caching, tiered extraction, parallel processing |
| 12 | Semantic Enhancement | ✅ Complete | OWL-RL inference, SKOS enrichment, graph analytics |
| 13 | Law Graph Pipeline | ✅ **Integrated** | XML reader, legal extractors, law ontology, structural import, **KG context augmentation** |

### Codebase Stats

| Metric | Value |
|--------|-------|
| Python source files | 87 |
| Lines of code (src/) | ~25,700 |
| Test files | 30+ |
| Pipeline scripts | 16 |

---

## Module Overview

```
src/kgbuilder/
├── core/                  # Protocols, models, exceptions, config
├── document/              # Document loading & chunking
│   ├── loaders/           #   Format-specific loaders
│   │   ├── pdf.py         #     PDF documents
│   │   ├── office.py      #     DOCX/PPTX documents
│   │   ├── law_xml.py     #     German law XML (gesetze-im-internet.de)
│   │   └── law_adapter.py #     Law XML → KGB Document converter
│   └── chunking/          #   Chunking strategies (fixed, semantic)
├── embedding/             # Embedding generation (Ollama)
├── extraction/            # Entity & relation extraction
│   ├── entity.py          #   LLM entity extractor (generic)
│   ├── relation.py        #   LLM relation extractor (generic)
│   ├── rules.py           #   Rule-based extractors (decommissioning)
│   ├── legal_rules.py     #   Rule-based extractors (German law)
│   ├── legal_llm.py       #   LLM extractor (German law, ontology-guided)
│   ├── legal_ensemble.py  #   Ensemble merger (rule + LLM for law)
│   ├── ensemble.py        #   Tiered/ensemble extraction framework
│   ├── synthesizer.py     #   Findings deduplication & merge
│   └── benchmarking.py    #   Structured generation benchmarks
├── confidence/            # Confidence tuning (6 components)
│   ├── analyzer.py        #   Statistical analysis & anomaly detection
│   ├── booster.py         #   Multi-source confidence boosting
│   ├── coreference.py     #   Entity coreference resolution
│   ├── calibrator.py      #   Per-type calibration curves
│   ├── voter.py           #   LLM consensus voting
│   └── filter.py          #   Quality filtering
├── enrichment/            # Post-extraction enrichment pipeline
├── assembly/              # KG assembly (SimpleKGAssembler, KGBuilder)
├── validation/            # SHACL, rules engine, consistency checker
├── storage/               # Neo4j, Qdrant, Fuseki, RDF, export
├── analytics/             # OWL-RL inference, SKOS, graph metrics
├── evaluation/            # QA dataset, metrics, reports
├── experiment/            # Experiment management & checkpointing
├── retrieval/             # BM25 + dense fusion retrieval
├── agents/                # Discovery loop, question generator
├── pipeline/              # Orchestrators (confidence tuning, checkpoints)
├── versioning/            # KG snapshot/restore/diff service
├── logging_config.py      # Structured logging & LLM call tracking
└── cli.py                 # CLI entry point
```

---

## Usage

### Full Pipeline (recommended)

```bash
python scripts/full_kg_pipeline.py --max-iterations 1 --wandb-enabled
```

Runs: ingestion → discovery → confidence tuning → enrichment → assembly → analytics → validation → export → version snapshot.

### Individual Components

```python
from kgbuilder.extraction.entity import LLMEntityExtractor
from kgbuilder.confidence import ConfidenceAnalyzer, ConfidenceBooster, CoreferenceResolver
from kgbuilder.storage.graph import Neo4jGraphStore

# Extract entities
extractor = LLMEntityExtractor(llm=llm_provider, ontology_service=ontology)
entities = extractor.extract(text, ontology_classes)

# Tune confidence
analyzer = ConfidenceAnalyzer()
report = analyzer.analyze(entities)

booster = ConfidenceBooster()
boosted = booster.boost_batch(entities)

resolver = CoreferenceResolver()
clusters = resolver.find_clusters(boosted, similarity_threshold=0.85)

# Store in Neo4j
store = Neo4jGraphStore(uri="bolt://localhost:7687")
store.batch_create_nodes(entities)
```

### Scripts

| Script | Purpose |
|--------|---------|
| **Core Pipeline** | |
| `full_kg_pipeline.py` | End-to-end KG pipeline (primary entry point, all domains) |
| `run_single_experiment.py` | Single experiment with metrics |
| `run_kg_pipeline_on_documents.py` | Discovery pipeline on document set |
| `manage_versions.py` | KG version management CLI |
| `validate_kg_complete.py` | Standalone KG validation |
| `load_ontology_to_fuseki.py` | Load ontology into Fuseki |
| `download_ontology.py` | Download/update ontology files |
| **Law Graph** | |
| `build_law_graph.py` | Law KG builder — Phase A (structural) + Phase B (semantic) |
| `build_law_ontology.py` | Generate `law-ontology-v1.0.owl` aligned to LKIF-Core + ELI |
| `merge_legal_ontologies.py` | Merge/cherry-pick LKIF-Core + ELI into single OWL file |
| `full_law_pipeline.py` | Download all German law data (HTML + XML from gesetze-im-internet.de) |
| `crawl_law_index.py` | Crawl Teilliste pages → `law_index.json` (6,869 laws) |

---

## Infrastructure

All services run via Docker Compose:

```bash
docker-compose up -d
```

| Service | Port | Purpose |
|---------|------|---------|
| **Neo4j** | 7474 (web), 7687 (bolt) | Knowledge Graph storage |
| **Qdrant** | 6333 | Vector similarity search |
| **Fuseki** | 3030 | RDF/SPARQL ontology store |
| **Ollama** | 11434 | Local LLM (qwen3:8b) & embeddings (qwen3-embedding) |

### Data

**Decommissioning Domain**:
- **Ontology**: `data/ontology/domain/plan-ontology-v1.0.owl` (28 KB)
- **Documents**: `data/Decommissioning_Files/` — 33 German nuclear decommissioning PDFs (126 MB)

**Law Domain**:
- **Reference Ontologies**: `data/ontology/legal/` — LKIF-Core (11 OWL modules, ~200 KB) + ELI (~160 KB)
- **Custom Ontology**: `data/ontology/law/law-ontology-v1.0.owl` (to be generated)
- **Law XML**: `data/law_html/{LawAbbr}/BJNR*.xml` — downloaded at runtime, gitignored
- **Profile**: `data/profiles/legal.json` — config overlay for `full_kg_pipeline.py`

See [data/README.md](data/README.md) and [data/ontology/README.md](data/ontology/README.md) for details.

---

## Project Structure

```
KnowledgeGraphBuilder/
├── src/kgbuilder/          # Implementation (see Module Overview)
├── tests/                  # Unit & integration tests
├── scripts/                # Pipeline scripts & utilities
├── data/
│   ├── ontology/
│   │   ├── domain/         # Our domain ontologies (decommissioning)
│   │   ├── legal/          # Reference legal ontologies
│   │   │   ├── lkif-core/  #   LKIF-Core v1.1 (11 OWL modules)
│   │   │   └── eli/        #   ELI metadata ontology
│   │   └── law/            # Custom law ontology (generated)
│   ├── profiles/           # Pipeline config overlays (legal.json, ...)
│   ├── Decommissioning_Files/  # Source PDFs (gitignored)
│   └── law_html/           # Downloaded law XML (gitignored)
├── Planning/               # Architecture, interfaces, backlog
│   ├── 01_ACADEMIC_OVERVIEW.md
│   ├── 02_ARCHITECTURE.md
│   ├── 03_INTERFACES.md
│   ├── LAW_GRAPH_PLAN.md           # Law graph high-level plan
│   ├── LAW_GRAPH_IMPLEMENTATION.md # Detailed implementation plan
│   ├── LAW_ONTOLOGY_SOURCES.md     # Legal ontology citations
│   ├── C1_*.md             # OntologyExtender blueprints
│   └── C3_*.md             # GraphQAAgent blueprints
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
└── .env.example
```

### Sibling Repositories

- **[GraphQAAgent](https://github.com/DataScienceLabFHSWF/GraphQAAgent)** — Consumes the KGs built here for ontology-informed QA with FusionRAG retrieval. Blueprints: [Planning/C3_*.md](Planning/).
- **[OntologyExtender](https://github.com/DataScienceLabFHSWF/OntologyExtender)** — Human-in-the-loop ontology extension and refinement. Blueprints: [Planning/C1_*.md](Planning/).

---

## Development

### Code Style

- PEP 8, 100-char line length
- Complete type hints on all functions
- Google-style docstrings
- `ruff` for linting, `black` for formatting, `mypy` strict mode

See [.github/copilot-instructions.md](.github/copilot-instructions.md) for full guidelines.

### Testing

```bash
pytest tests/                              # all tests
pytest tests/confidence/                   # confidence module
pytest tests/ --cov=src/kgbuilder          # with coverage
```

### Technology Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11+ |
| LLM | Ollama (qwen3:8b, qwen3-embedding) |
| Vector DB | Qdrant |
| Knowledge Graph | Neo4j 5.x |
| RDF Store | Apache Fuseki 4.x |
| Experiment Tracking | Weights & Biases |
| Testing | pytest |
| Linting | ruff, mypy, black |

---

## License

MIT — See [LICENSE](LICENSE)
