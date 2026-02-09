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

# or smoke test
python scripts/full_kg_pipeline.py --smoke-test
```

### CLI Options

```
python scripts/full_kg_pipeline.py --help

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
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     KG CONSTRUCTION PIPELINE                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. DOCUMENT INGESTION          2. RETRIEVAL & EXTRACTION            │
│  ┌──────────────────────┐       ┌─────────────────────────┐         │
│  │ PDF/DOCX/PPTX load   │       │ BM25 + Dense fusion     │         │
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

---

## Current Status

**Pipeline**: Fully operational on 33 German nuclear decommissioning PDFs (~126 MB).

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
├── document/              # Document loading (PDF/DOCX/PPTX) & chunking
│   ├── loaders/           #   Format-specific loaders
│   └── chunking/          #   Chunking strategies (fixed, semantic)
├── embedding/             # Embedding generation (Ollama)
├── extraction/            # Entity & relation extraction
│   ├── entity.py          #   LLM entity extractor
│   ├── relation.py        #   LLM relation extractor
│   ├── synthesizer.py     #   Findings deduplication & merge
│   ├── rules.py           #   Rule-based extractors
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
| `full_kg_pipeline.py` | End-to-end pipeline (primary entry point) |
| `run_single_experiment.py` | Single experiment with metrics |
| `run_kg_pipeline_on_documents.py` | Discovery pipeline on document set |
| `manage_versions.py` | KG version management CLI |
| `validate_kg_complete.py` | Standalone KG validation |
| `load_ontology_to_fuseki.py` | Load ontology into Fuseki |
| `download_ontology.py` | Download/update ontology files |

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

- **Ontology**: `data/ontology/plan-ontology-v1.0.owl` (28 KB)
- **Documents**: `data/Decommissioning_Files/` — 33 German nuclear decommissioning PDFs (126 MB)

See [data/README.md](data/README.md) for details.

---

## Project Structure

```
KnowledgeGraphBuilder/
├── src/kgbuilder/          # Implementation (see Module Overview)
├── tests/                  # Unit & integration tests
├── scripts/                # Pipeline scripts & utilities
├── data/                   # Ontologies & source documents
├── Planning/               # Architecture, interfaces, backlog (published)
│   ├── 01_ACADEMIC_OVERVIEW.md
│   ├── 02_ARCHITECTURE.md
│   ├── 03_INTERFACES.md
│   ├── 04_ISSUES_BACKLOG.md
│   ├── 05_SMOKE_TEST_RESULTS.md
│   ├── 06_VERSIONING_GUIDE.md
│   ├── 12_SEMANTIC_ENHANCEMENT.md
│   ├── C1_*.md             # OntologyExtender blueprints
│   └── C3_*.md             # GraphQAAgent blueprints
├── local-docs/             # Session notes (local only, not published)
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
