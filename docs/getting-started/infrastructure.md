# Infrastructure

All services run via Docker Compose:

```bash
docker-compose up -d
```

## Services

| Service | Port | Purpose | Image |
|---------|------|---------|-------|
| **Neo4j** | 7474 (HTTP) / 7687 (Bolt) | Knowledge graph storage (Cypher) | `neo4j:5-community` |
| **Qdrant** | 6333 (HTTP) / 6334 (gRPC) | Vector similarity search (384-dim) | `qdrant/qdrant` |
| **Fuseki** | 3030 | RDF/SPARQL ontology store | `stain/jena-fuseki` |
| **Ollama** | 11434 | Local LLM and embedding inference | `ollama/ollama` |

## Health Checks

```bash
# Neo4j
curl -s http://localhost:7474 | head -1

# Qdrant
curl -s http://localhost:6333/collections | python -m json.tool

# Fuseki
curl -s http://localhost:3030/$/ping

# Ollama
curl -s http://localhost:11434/api/tags | python -m json.tool
```

## Data Persistence

Docker volumes store persistent data:

- `neo4j_data` -- Neo4j graph database
- `qdrant_data` -- Qdrant vector collections
- `fuseki_data` -- Fuseki RDF datasets

## SHACL2FOL (Optional)

For static SHACL validation via first-order logic (Vampire theorem prover):

```bash
./scripts/setup_shacl2fol.sh
```

This downloads the SHACL2FOL JAR and Vampire binary into `lib/`.
