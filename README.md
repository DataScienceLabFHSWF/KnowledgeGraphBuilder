# KnowledgeGraphBuilder

Ontology-driven Knowledge Graph Construction Pipeline

---

## What is this?

**KnowledgeGraphBuilder** is a modular, ontology-guided pipeline for building, validating, and versioning knowledge graphs from unstructured documents (PDF, DOCX, PPTX, etc.).

- **Ingests documents** (PDF, DOCX, PPTX, TXT, Markdown)
- **Extracts entities and relations** using an ontology
- **Builds and validates** a Knowledge Graph (KG)
- **Exports** KG in multiple formats (JSON-LD, YARRRML, RDF)
- **Tracks experiments and KG versions** for research and reproducibility

---

## Quick Start

### 1. Setup
```bash
# Copy environment config
cp .env.example .env

# Install dependencies
pip install -r pyproject.toml

# Start services
docker-compose up -d neo4j qdrant
```

### 2. Load Data
```python
from pathlib import Path
from kgbuilder.document import DocumentLoaderFactory

# Load documents
loader = DocumentLoaderFactory.get_loader("pdf")
docs = [loader.load(f) for f in Path("data/Decommissioning_Files").glob("*.pdf")]

# Load ontology
from rdflib import Graph
ontology = Graph()
ontology.parse("data/ontology/plan-ontology-v1.0.owl", format="xml")
```

### 3. Process Documents
```python
from kgbuilder.document.chunking import FixedSizeChunker

# Chunk documents
chunker = FixedSizeChunker(chunk_size=512, overlap=50)
chunks = []
for doc in docs[:3]:  # Start with 3 docs
    chunks.extend(chunker.chunk(doc))
```

### 4. Extract & Store
```python
# Extract entities & relations (after LLM integration)
# from kgbuilder.extraction import LLMEntityExtractor, LLMRelationExtractor

# Store in backends
from kgbuilder.storage import Neo4jStore, QdrantStore
graph_store = Neo4jStore(uri="bolt://localhost:7687")
vector_store = QdrantStore(url="http://localhost:6333")
```

---

## Data

- **Ontology**: `data/ontology/plan-ontology-v1.0.owl` (28 KB) – AI Planning Ontology
- **Documents**: `data/Decommissioning_Files/` – 33 German nuclear decommissioning PDFs (126 MB)
- **Scripts**: `scripts/download_ontology.py` – Manage ontology versions

See [data/README.md](data/README.md) for details.

---

## Research Questions

This project is designed to answer key research questions in ontology-driven KG construction:

- **How does ontology guidance impact the quality and coverage of KGs built from unstructured documents?**
- **How do different ontology/CQ versions affect KG structure, validation, and downstream QA/RAG performance?**
- **What are the trade-offs between classic vector-based, hybrid, and KG-only RAG architectures?**
- **How can we systematically track, compare, and reproduce KG building experiments for academic evaluation?**

## Research Contributions

- A modular, protocol-based Python framework for KG construction and validation
- Full experiment tracking, versioning, and metrics for reproducible research
- Support for ontology/CQ evolution and ablation studies
- Extensible architecture for integrating new document types, chunking, extraction, and storage backends
- Export and validation in multiple KG formats (JSON-LD, YARRRML, RDF)

---

## Architecture

- [src/](src/) – Implementation (document processing, extraction, storage, validation)
- [Planning/ARCHITECTURE.md](Planning/ARCHITECTURE.md) – System design & diagrams
- [Planning/INTERFACES.md](Planning/INTERFACES.md) – Protocol/interface definitions
- [.github/copilot-instructions.md](.github/copilot-instructions.md) – Code style guidelines

---

## Documentation

**Public Documentation** (repository ready):
- [README.md](README.md) – This file
- [data/README.md](data/README.md) – Data directory guide
- [Planning/](Planning/) – Specs, architecture, and design docs

**Local Documentation** (development only, not published):
- `local-docs/` – Phase summaries, implementation guides, completion checklists
  - Use `local-docs/IMPLEMENTATION_GUIDE.md` for full development reference

---

## Repo Organization
- [src/](src/) – Implementation code
- [tests/](tests/) – Unit tests
- [scripts/](scripts/) – Utilities (e.g., ontology download)
- [Planning/](Planning/) – Specs, architecture, design (published)
- [local-docs/](local-docs/) – Session notes, checklists (local only, not published)
- [data/](data/) – Ontologies and source documents
- Root: only essentials ([README.md](README.md), [docker-compose.yml](docker-compose.yml), [pyproject.toml](pyproject.toml), etc.)

---

## License
MIT
