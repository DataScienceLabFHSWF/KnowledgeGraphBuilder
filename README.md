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
pip install -r requirements.txt

# Start services
docker-compose up -d neo4j qdrant fuseki
```

### 2. Ingest Documents
```bash
# Process all documents: load → chunk → embed → index
# Handles PDF parsing, VLM extraction, embedding with Ollama, vector storage
python scripts/ingest.py

# Logs available at: tail -f /tmp/ingest.log
```

### 3. Load Ontology to Fuseki
```bash
# Load ontology (plan-ontology-v1.0.owl) into Fuseki RDF store
python scripts/load_ontology_to_fuseki.py

# Ontology provides entity type constraints and relation definitions
```

### 4. Data Processing Pipeline
The ingestion pipeline automatically:
- **Loads**: PDF documents from `data/Decommissioning_Files/`
- **Parses**: Extracts text with optional VLM support (qwen3)
- **Chunks**: 512-token chunks with 50-token overlap
- **Embeds**: Uses Ollama (qwen3-embedding, 4096-dim vectors)
- **Indexes**: Stores in Qdrant vector DB (kgbuilder collection)
- **Caches**: Document processing with automatic cache invalidation

All results logged with structured logging (JSON format)

---

## Current Status

### ✅ Release 0.1.0: Document Ingestion & Ontology Loading
- Full document ingestion pipeline (33 German decommissioning PDFs)
- PDF parsing with VLM extraction (qwen3)
- Semantic chunking (512 tokens, 50 overlap)
- Embedding with Ollama (qwen3-embedding, 4096-dim vectors)
- Vector indexing in Qdrant
- Ontology loading to Fuseki RDF store (342 triples)

### ✅ Release 0.2.0: FusionRAG Retrieval & Entity/Relation Extraction
- RAG-based retrieval from vector database
- LLM-guided entity extraction with confidence scoring
- Relation extraction with type validation
- Iterative refinement loop for improved accuracy

### ✅ Release 0.3.0: Knowledge Graph Assembly & Validation
- Entity deduplication and synthesis
- Relation validation and conflict resolution
- Neo4j knowledge graph construction
- RDF/JSON-LD export support

### ✅ Release 0.4.0: Autonomous Discovery Pipeline
- **QuestionGenerationAgent**: Generates strategic research questions from ontology
- **IterativeDiscoveryLoop**: Autonomously discovers entities matching each question
- **FindingsSynthesizer**: Deduplicates and merges discovered findings
- **SimpleKGAssembler**: Assembles findings into Neo4j knowledge graph

**Phase 4 Test Results**:
- 89 total tests across 4 components
- 87% average coverage
- 100% pass rate
- End-to-end pipeline validated against live Neo4j
- Successfully generated KG with 5 nodes and 2 relationships

**Storage Backends**:
- **Qdrant**: Vector similarity search (kgbuilder collection, 4096-dim)
- **Fuseki**: RDF triple store with ontology (kgbuilder dataset)
- **Neo4j**: Knowledge graph with entity relationships (port 7687)
- **Ollama**: Local LLM and embedding models

### 🔄 Next: Release 0.5.0 (Query Interface & Visualization)

- Ontology-guided entity extraction using LLM
- Semantic relation extraction from chunks
- Knowledge graph assembly in Neo4j
- Hybrid retrieval (vector + semantic + KG)
- Query execution and validation

---

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
