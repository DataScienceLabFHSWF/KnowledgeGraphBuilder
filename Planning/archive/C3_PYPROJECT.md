# C3. KG-RAG QA Agent — pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "kg-rag-agent"
version = "0.1.0"
description = "Ontology-informed GraphRAG QA Agent consuming Knowledge Graphs"
readme = "README.md"
license = "MIT"
requires-python = ">=3.11"
authors = [
    { name = "Florian Neubürger" },
]

dependencies = [
    # --- Core ---
    "pydantic>=2.5,<3",
    "pydantic-settings>=2.1,<3",
    "structlog>=24.1",
    "httpx>=0.27",                  # Async HTTP for Ollama + Fuseki

    # --- Storage Connectors (read-only) ---
    "neo4j>=5.15,<6",              # Neo4j driver for KG queries
    "qdrant-client>=1.7,<2",      # Qdrant for vector search

    # --- Embeddings & Reranking ---
    "numpy>=1.26,<2",
    "sentence-transformers>=3.0",   # Cross-encoder reranking

    # --- LLM ---
    "ollama>=0.4",                  # Ollama Python client

    # --- Text Processing ---
    "rapidfuzz>=3.5",               # Fuzzy entity linking

    # --- API (optional) ---
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",

    # --- Experiment Tracking ---
    "wandb>=0.16",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.1",
    "ruff>=0.4",
    "mypy>=1.9",
    "pre-commit>=3.6",
]
eval = [
    # Extra deps for evaluation only
    "rouge-score>=0.1.2",           # ROUGE metrics
    "nltk>=3.8",                    # Tokenization for F1
    "matplotlib>=3.8",              # Report plots
    "jinja2>=3.1",                  # HTML report templates
]

[project.scripts]
kgrag = "kgrag.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/kgrag"]

# --- Ruff ---
[tool.ruff]
target-version = "py311"
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "RUF", "B", "A", "SIM", "TCH"]
ignore = ["E501"]

[tool.ruff.lint.isort]
known-first-party = ["kgrag"]

# --- Mypy ---
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
plugins = ["pydantic.mypy"]

[[tool.mypy.overrides]]
module = [
    "neo4j.*",
    "qdrant_client.*",
    "sentence_transformers.*",
    "ollama.*",
    "rapidfuzz.*",
    "wandb.*",
]
ignore_missing_imports = true

# --- Pytest ---
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = [
    "integration: requires running Neo4j/Qdrant/Fuseki",
    "slow: long-running evaluation tests",
]
```

## Key Dependency Decisions

| Dependency | Rationale |
|-----------|-----------|
| `httpx` | Async HTTP for Ollama API + Fuseki SPARQL endpoint (replaces requests) |
| `neo4j` | Official Neo4j Python driver — KGB uses same driver |
| `qdrant-client` | Same client KGB uses — ensures collection format compatibility |
| `sentence-transformers` | Cross-encoder reranking (C3.3) — small model, runs locally |
| `rapidfuzz` | Fast fuzzy string matching for entity linking |
| `ollama` | Python client wrapping Ollama REST API — same instance as KGB |
| `wandb` | Experiment tracking for retrieval strategy comparison (C3.5) |

## NOT Included (and why)

| Package | Why excluded |
|---------|-------------|
| `langchain` / `llama-index` | Too much abstraction; we need fine control over retrieval |
| `rdflib` | Fuseki handles RDF; agent only needs SPARQL via httpx |
| `transformers` | sentence-transformers wraps what we need; no custom model training |
| `torch` | Pulled in by sentence-transformers; no explicit dependency needed |
