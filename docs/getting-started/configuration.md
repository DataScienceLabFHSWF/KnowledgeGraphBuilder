# Configuration

## Environment Variables

Pipeline configuration uses Pydantic models with environment variable support.
Copy `.env.example` to `.env` and adjust:

```bash
# LLM and embedding service
OLLAMA_URL=http://localhost:18134

# Graph database
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=kgbuilder

# Vector database
QDRANT_URL=http://localhost:6333

# RDF/SPARQL store
FUSEKI_URL=http://localhost:3030

# Law graph (optional)
LAW_GRAPH_ENABLED=false
LAW_DATA_DIR=data/law_html
LAW_OUTPUT_DIR=output/law_results
```

## Domain Profiles

Per-domain configuration overrides live in `data/profiles/` as JSON files:

```bash
python scripts/full_kg_pipeline.py --profile data/profiles/legal.json
```

A profile overrides fields in `PipelineConfig`:

```json
{
  "ontology_dataset": "lawgraph",
  "ontology_path": "data/ontology/law/law-ontology-v1.0.owl",
  "document_dir": "data/law_html",
  "document_extensions": [".xml"],
  "vector_collection": "lawgraph",
  "output_dir": "output/law_results",
  "max_iterations": 3
}
```

## Configuration Models

The main configuration classes are defined in `src/kgbuilder/core/config.py`:

- **`LLMConfig`** -- model name, base URL, temperature, max tokens
- **`EmbeddingConfig`** -- embedding model, dimensions
- **`Neo4jConfig`** -- connection URI, credentials
- **`QdrantConfig`** -- connection URL, collection settings

See the [API Reference](../reference/kgbuilder/core/config.md) for full details.
