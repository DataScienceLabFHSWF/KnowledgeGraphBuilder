# KnowledgeGraphBuilder

Ontology-driven knowledge graph construction pipeline.  Ingests unstructured
documents (PDF, DOCX, PPTX, XML), extracts entities and relations guided by an
OWL ontology, assembles a validated knowledge graph in Neo4j, and exports it in
multiple standard formats (JSON-LD, RDF/Turtle, YARRRML, Cypher).

Part of a three-repository research ecosystem:

| Repository | Purpose |
|-----------|---------|
| **KnowledgeGraphBuilder** (this repo) | KG construction, validation, and export |
| [GraphQAAgent](https://github.com/DataScienceLabFHSWF/GraphQAAgent) | Ontology-informed GraphRAG QA agent |
| [OntologyExtender](https://github.com/DataScienceLabFHSWF/OntologyExtender) | Human-in-the-loop ontology extension |

---

## What This Repository Does

1. **Document ingestion** — loads PDFs, DOCX, PPTX, and German law XML;
   chunks them semantically; embeds them into Qdrant for hybrid retrieval.
2. **Ontology-guided extraction** — generates LLM prompts from OWL class and
   property definitions; extracts entities and relations with confidence
   scores.
3. **Autonomous discovery** — iteratively generates competency questions,
   retrieves relevant chunks, and extracts additional facts until coverage
   converges.
4. **Confidence tuning** — statistical analysis, multi-source boosting,
   coreference resolution, LLM consensus voting, and quality filtering.
5. **KG assembly & validation** — assembles nodes and edges in Neo4j;
   validates against SHACL shapes generated from the ontology; runs pySHACL
   and (optionally) SHACL2FOL/Vampire static checks.
6. **Analytics & export** — OWL-RL inference, SKOS enrichment, graph metrics;
   exports to JSON-LD, RDF/Turtle, Cypher, GraphML, and plain JSON.
7. **Experiment framework** — manages multi-variant runs with W&B logging,
   checkpointing, and automated SHACL quality scoring per run.

The pipeline is **ontology-agnostic**: it reads whatever OWL ontology is
provided and auto-generates extraction prompts, SHACL shapes, and validation
rules from it.  Different knowledge domains share the same code — only the
ontology and document loaders change.

---

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/DataScienceLabFHSWF/KnowledgeGraphBuilder.git
cd KnowledgeGraphBuilder
cp .env.example .env          # configure endpoints
pip install -e ".[dev]"

# 2. Start infrastructure
docker-compose up -d neo4j qdrant fuseki ollama

# 3. Run the full pipeline
source .venv/bin/activate
export PYTHONPATH=$PWD/src:$PYTHONPATH
python scripts/full_kg_pipeline.py --max-iterations 1

# With law graph context augmentation
LAW_GRAPH_ENABLED=true python scripts/full_kg_pipeline.py --max-iterations 1
```

See `python scripts/full_kg_pipeline.py --help` for all CLI options.

---

## Infrastructure

All services run via Docker Compose:

```bash
docker-compose up -d
```

| Service | Port | Purpose |
|---------|------|---------|
| Neo4j | 7474 / 7687 | Knowledge graph storage (Cypher) |
| Qdrant | 6333 | Vector similarity search |
| Fuseki | 3030 | RDF/SPARQL ontology store |
| Ollama | 11434 | Local LLM and embeddings |

---

## Project Structure

```
src/kgbuilder/
  core/           Protocols, data models, exceptions, config
  document/       Document loaders (PDF, DOCX, law XML) and chunking
  embedding/      Embedding generation (Ollama)
  extraction/     Entity and relation extraction (LLM + rule-based)
  confidence/     Confidence tuning (analyzer, booster, coreference, voter)
  enrichment/     Post-extraction enrichment pipeline
  assembly/       KG assembly (SimpleKGAssembler, KGBuilder)
  validation/     SHACL shapes, pySHACL validator, SHACL2FOL, scorer
  storage/        Neo4j, Qdrant, Fuseki, RDF store, export
  analytics/      OWL-RL inference, SKOS enrichment, graph metrics
  retrieval/      BM25 + dense fusion retrieval
  agents/         Discovery loop, question generator
  experiment/     Experiment manager, checkpoint, plotter, reporter
  pipeline/       Orchestrators (confidence tuning, stopping criterion)
  versioning/     KG snapshot, restore, diff

scripts/          Pipeline entry points and utilities
tests/            Unit and integration tests
data/
  ontology/       OWL ontologies (domain, legal, generated shapes)
  profiles/       Pipeline config overlays
Planning/         Architecture docs, interface specs, evaluation notes
```

---

## Validation & Quality Scoring

Every KG build is scored automatically.  The scorer generates SHACL shapes
from the OWL ontology, runs pySHACL against the Neo4j graph, and computes a
weighted quality score combining:

- **Consistency** (SHACL2FOL satisfiability)
- **Acceptance** (sampled action validation)
- **Class coverage** (ontology classes present in the graph)
- **SHACL conformance** (pySHACL violation count)

Run the scorer standalone:

```bash
PYTHONPATH=src python scripts/run_kg_scoring.py
```

See [Planning/VALIDATION_PLAN.md](Planning/VALIDATION_PLAN.md) for details.

---

## Key Scripts

| Script | Purpose |
|--------|---------|
| `full_kg_pipeline.py` | End-to-end KG pipeline (all domains) |
| `build_law_graph.py` | German federal law KG (structure-first) |
| `run_kg_scoring.py` | Standalone SHACL quality scoring |
| `run_single_experiment.py` | Single experiment with metrics |
| `validate_kg_complete.py` | Full KG validation suite |
| `manage_versions.py` | KG snapshot/restore CLI |

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11+ |
| LLM | Ollama (qwen3:8b, qwen3-embedding) |
| Graph DB | Neo4j 5.x |
| Vector DB | Qdrant |
| RDF Store | Apache Fuseki 4.x |
| Validation | pySHACL, SHACL2FOL + Vampire |
| Experiments | Weights & Biases |
| Testing | pytest |
| Linting | ruff, mypy, black |

---

## Documentation

| Document | Contents |
|----------|----------|
| [Planning/01_ACADEMIC_OVERVIEW.md](Planning/01_ACADEMIC_OVERVIEW.md) | Research context and motivation |
| [Planning/02_ARCHITECTURE.md](Planning/02_ARCHITECTURE.md) | Pipeline architecture and design decisions |
| [Planning/03_INTERFACES.md](Planning/03_INTERFACES.md) | Protocol definitions and interface contracts |
| [Planning/VALIDATION_PLAN.md](Planning/VALIDATION_PLAN.md) | SHACL validation and scoring plan |
| [Planning/LANGEXTRACT_EVAL.md](Planning/LANGEXTRACT_EVAL.md) | Evaluation of Google LangExtract |
| [Planning/LAW_GRAPH_PLAN.md](Planning/LAW_GRAPH_PLAN.md) | Law graph construction plan |
| [Planning/LAW_ONTOLOGY_SOURCES.md](Planning/LAW_ONTOLOGY_SOURCES.md) | Legal ontology citations (LKIF-Core, ELI) |
| [data/README.md](data/README.md) | Data directory layout and sources |

---

## Development

```bash
# Code style: PEP 8, 100-char lines, full type hints, Google-style docstrings
# Run tests
pytest tests/

# With coverage
pytest tests/ --cov=src/kgbuilder

# Lint
ruff check src/ tests/
mypy src/ --strict
```

See [.github/copilot-instructions.md](.github/copilot-instructions.md) for
complete coding guidelines.

---

## Related Work

- **SHACL2FOL** — Ahmetaj et al., "SHACL Validation under Graph Updates"
  (static validation of SHACL shapes via first-order logic translation)
- **pySHACL** — RDFLib-based SHACL validation engine
- **LKIF-Core** — Legal Knowledge Interchange Format ontology
- **ELI** — European Legislation Identifier ontology
- **LangExtract** — Google's few-shot structured extraction library
  ([evaluation](Planning/LANGEXTRACT_EVAL.md))

---

## License

MIT — see [LICENSE](LICENSE)
