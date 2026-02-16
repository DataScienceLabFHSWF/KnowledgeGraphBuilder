# Quick Start

## Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Git

## Installation

```bash
# Clone and install
git clone https://github.com/DataScienceLabFHSWF/KnowledgeGraphBuilder.git
cd KnowledgeGraphBuilder
cp .env.example .env          # configure endpoints
pip install -e ".[dev]"
```

## Start Infrastructure

```bash
docker-compose up -d neo4j qdrant fuseki ollama
```

| Service | Port | Purpose |
|---------|------|---------|
| Neo4j | 7474 / 7687 | Knowledge graph storage |
| Qdrant | 6333 | Vector similarity search |
| Fuseki | 3030 | RDF/SPARQL ontology store |
| Ollama | 11434 | Local LLM inference |

## Run the Pipeline

```bash
source .venv/bin/activate
export PYTHONPATH=$PWD/src:$PYTHONPATH

# Single iteration for quick test
python scripts/full_kg_pipeline.py --max-iterations 1

# With law graph context augmentation
LAW_GRAPH_ENABLED=true python scripts/full_kg_pipeline.py --max-iterations 1
```

## CLI Options

```bash
python scripts/full_kg_pipeline.py --help
```

Key options:

| Flag | Description |
|------|-------------|
| `--max-iterations N` | Limit discovery loop iterations |
| `--enrich-only` | Re-run enrichment from checkpoint |
| `--skip-enrichment` | Skip enrichment phase |
| `--skip-analytics` | Skip analytics phase |
| `--checkpoint PATH` | Load from specific checkpoint |
| `--dry-run` | Parse and extract without writing to databases |

## Next Steps

- [Infrastructure details](infrastructure.md)
- [Configuration](configuration.md)
- [Architecture overview](../architecture/overview.md)
- [Law Graph quickstart](../guide/law-graph.md)
