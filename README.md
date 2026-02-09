# KnowledgeGraphBuilder

**Ontology-driven Knowledge Graph Construction Pipeline**

Build, validate, and manage knowledge graphs from unstructured documents with autonomous discovery and confidence tuning.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Current Status](#current-status)
- [Architecture Overview](#architecture-overview)
- [Implementation Progress](#implementation-progress)
- [Usage Examples](#usage-examples)
- [Storage Backends](#storage-backends)
- [Project Roadmap](#project-roadmap)

---

## Quick Start

### 1. Setup

```bash
# Copy environment config
cp .env.example .env

# Install dependencies
pip install -r requirements.txt

# Start services (requires Docker)
docker-compose up -d neo4j qdrant fuseki ollama
```

### 2. Run Full Pipeline (All Documents)

```bash
# Run in background with proper venv activation and PYTHONPATH
cd /home/fneubuerger/KnowledgeGraphBuilder

nohup bash -c 'source .venv/bin/activate && \
export PYTHONPATH=/home/fneubuerger/KnowledgeGraphBuilder/src:$PYTHONPATH && \
python scripts/full_kg_pipeline.py --max-iterations 1' \
> /tmp/kg_pipeline_$(date +%Y%m%d_%H%M%S).log 2>&1 &

# Or use the saved script
bash scripts/run_pipeline_bg.sh

# Monitor progress
tail -f /tmp/kg_pipeline_*.log
```

### 2b. Run Smoke Test

```bash
# Quick test on minimal subset
python scripts/full_kg_pipeline.py --smoke-test
```

### 3. Run Discovery Pipeline

```bash
# Generate questions and discover entities autonomously
python scripts/run_kg_pipeline_on_documents.py

# Results: Neo4j KG with extracted entities and relationships
```

### CLI Options

The full pipeline supports many configuration options:

```bash
python scripts/full_kg_pipeline.py --help

# Key options:
# --max-iterations N          : Discovery loop iterations (default: 3)
# --skip-discovery            : Skip discovery phase
# --skip-enrichment           : Skip enrichment phase
# --skip-validation           : Skip validation
# --enrich-only + --checkpoint : Re-enrich from checkpoint
# --smoke-test                : Run on test collections only
# --wandb-enabled             : Enable W&B experiment tracking
# --documents PATH            : Input documents directory
# --output PATH               : Output directory
# --ontology-url URL          : Fuseki endpoint (default: http://localhost:3030)
```

---

## Recent Fixes & Updates (2026-02-09)

### ✅ CRITICAL BUG FIXED: Entity ID Collision Resolution

**Problem**: Entity ID collisions causing 99.5% data loss during discovery loop
- Root cause: Sequential IDs assigned per-chunk without deterministic content hashing
- Impact: Entity deduplication keyed on entity.id was merging all instances
- Result: Only ~15 final entities instead of hundreds

**Solution**: 
- Implemented deterministic content-based entity IDs (format: `ent_<12-char-hex>`)
- MD5 hash of entity label + type ensures same entity always gets same ID
- Changed dedup key from `entity.id` → tuple `(label.lower(), entity_type.lower())`
- Updated both `LLMEntityExtractor` and `RuleBasedExtractor` to use `generate_entity_id()`
- Added backward-compatible evidence tracking

**Verification**:
- All 17 existing tests pass (no regressions)
- Expected impact: 10-30x more entities on re-run (hundreds instead of ~15)

**Files Modified**:
- `src/kgbuilder/extraction/entity.py` – Entity ID generation & deduplication
- `src/kgbuilder/extraction/relation.py` – Relation extraction updates
- `src/kgbuilder/agents/discovery_loop.py` – Discovery loop dedup logic

### ✅ Parameter Fix: Neo4jInferenceEngine Initialization

**Problem**: Pipeline initialization error - unexpected keyword argument `storage`

```
TypeError: Neo4jInferenceEngine.__init__() got an unexpected keyword argument 'storage'
```

**Solution**: Corrected parameter name in pipeline initialization
- Changed: `Neo4jInferenceEngine(storage=self.graph_store, ...)`
- To: `Neo4jInferenceEngine(graph_store=self.graph_store, ...)`

**File Modified**:
- `scripts/full_kg_pipeline.py` (line 246)

**Result**: Pipeline now initializes successfully on all 33 documents

---

## Current Status

### Release History

| Release | Phase | Status | Key Features |
|---------|-------|--------|--------------|
| **0.1.0** | 1 | ✅ Complete | Document loading, chunking, embedding, vector indexing |
| **0.2.0** | 2 | ✅ Complete | RAG retrieval, entity/relation extraction with confidence |
| **0.3.0** | 3 | ✅ Complete | KG assembly, validation, deduplication, Neo4j export |
| **0.4.0** | 4 | ✅ Complete | Autonomous discovery (questions, entity extraction, synthesis) |
| **0.5.0** | 5.1-5.3 | ✅ Complete | Confidence analysis, boosting, coreference resolution |
| **0.6.0** | 5.4-5.6 | 🟡 In Progress | Calibration, consensus voting, quality filtering |

### Phase 5: Entity Confidence Tuning (0.5.0)

**Status**: ✅ **Tasks 1-3 COMPLETE** | 22/22 tests passing | 98%+ code coverage

#### Task 5.1: Confidence Analyzer ✅

Analyzes confidence score distributions across extracted entities.

**Features**:
- Statistical analysis (mean, std dev, percentiles)
- Per-entity-type breakdown
- Anomaly detection (IQR method)
- Automatic threshold recommendation

**Usage**:
```python
from kgbuilder.confidence import ConfidenceAnalyzer

analyzer = ConfidenceAnalyzer()
report = analyzer.analyze(entities)
print(f"Mean confidence: {report.mean:.2%}")
print(f"Anomalies detected: {len(report.anomalies)}")
```

#### Task 5.2: Confidence Booster ✅

Increases confidence scores based on evidence quality and entity type.

**Features**:
- Multi-source boost (+7.5% per additional source, max +15%)
- Type-based prior (+5% for Action/Parameter)
- Intelligent capping at 0.99

**Usage**:
```python
from kgbuilder.confidence import ConfidenceBooster

booster = ConfidenceBooster()
boosted_entities = booster.boost_batch(entities)
```

#### Task 5.3: Coreference Resolver ✅

Identifies and merges duplicate/coreferent entities.

**Features**:
- Fuzzy string matching (SequenceMatcher)
- Greedy clustering algorithm
- Same-type grouping (no cross-type clustering)
- Intelligent merge (longest label, averaged confidence, combined evidence)

**Usage**:
```python
from kgbuilder.confidence import CoreferenceResolver

resolver = CoreferenceResolver()
clusters = resolver.find_clusters(entities, similarity_threshold=0.85)
for cluster in clusters:
    merged = resolver.merge_cluster(cluster, {e.id: e for e in entities})
```

---

## Architecture Overview

### Pipeline Stages

```
┌─────────────────────────────────────────────────────────────────┐
│                     KG CONSTRUCTION PIPELINE                     │
└─────────────────────────────────────────────────────────────────┘

PHASE 1: DOCUMENT INGESTION
  Document Loading (PDF/DOCX/PPTX)
         ↓
  Semantic Chunking (512 tokens, 50% overlap)
         ↓
  Embedding Generation (Ollama qwen3-embedding, 4096-dim)
         ↓
  Vector Indexing (Qdrant)

PHASE 2: RETRIEVAL & EXTRACTION  
  Query → RAG Retrieval (BM25 + Dense, 0.6:0.4 fusion)
         ↓
  LLM Entity Extraction (Ollama qwen, with confidence)
         ↓
  LLM Relation Extraction (with type validation)

PHASE 3: VALIDATION & ASSEMBLY
  SHACL Shape Validation
         ↓
  Ontology Constraint Checking
         ↓
  Simple KG Assembly (Neo4j)

PHASE 4: AUTONOMOUS DISCOVERY
  Question Generation (from ontology gaps)
         ↓
  Iterative Discovery Loop (multiple questions)
         ↓
  Findings Synthesis (deduplication & merging)
         ↓
  Neo4j Knowledge Graph

PHASE 5: CONFIDENCE TUNING (NEW!)
  Confidence Analysis (statistics, anomalies)
         ↓
  Confidence Boosting (multi-source, type-based)
         ↓
  Coreference Resolution (entity deduplication)
         ↓
  [Pending 5.4-5.6] Calibration, Consensus, Filtering
```

### Module Organization

```
src/kgbuilder/
├── core/                       # Shared abstractions
│   ├── protocols.py            # Protocol definitions
│   ├── models.py               # Data models
│   ├── exceptions.py           # Exception hierarchy
│   └── config.py               # Configuration
├── document/                   # Document processing
│   ├── loaders/               # PDF, DOCX, PPTX loaders
│   └── chunking/              # Chunking strategies
├── embedding/                  # Embedding generation
│   └── ollama.py              # Ollama integration
├── extraction/                 # Entity/Relation extraction
│   ├── entity.py              # Entity extraction
│   ├── relation.py            # Relation extraction
│   ├── chains.py              # LLM chains
│   └── synthesizer.py         # Deduplication & synthesis
├── storage/                    # Data persistence
│   ├── vector.py              # Qdrant integration
│   ├── graph.py               # Neo4j integration
│   └── rdf.py                 # Fuseki RDF store
├── assembly/                   # KG construction
│   └── core.py                # SimpleKGAssembler
├── validation/                 # Multi-level validation
│   └── validators.py          # SHACL, ontology, competency validation
├── confidence/                 # NEW! Confidence tuning
│   ├── __init__.py            # Data models
│   ├── analyzer.py            # Task 5.1 ✅
│   ├── booster.py             # Task 5.2 ✅
│   ├── coreference.py         # Task 5.3 ✅
│   ├── calibrator.py          # Task 5.4 (pending)
│   ├── voter.py               # Task 5.5 (pending)
│   └── filter.py              # Task 5.6 (pending)
├── agents/                     # Agent orchestration
│   ├── question_generator.py  # Phase 4a
│   └── discovery_loop.py      # Phase 4b
└── retrieval/                  # RAG & retrieval
    └── phase2.py              # BM25 + dense fusion
```

---

## Implementation Progress

### Completed Features

#### Phase 1: Document Ingestion ✅
- [x] PDF/DOCX/PPTX loading
- [x] Semantic chunking (512-token, 50% overlap)
- [x] VLM text extraction (qwen3)
- [x] Metadata extraction (title, author, page count)
- [x] MD5-based caching

**Stats**:
- 33 German decommissioning PDFs processed
- ~1,200 chunks created
- 4,096-dimensional embeddings

#### Phase 2: RAG & Extraction ✅
- [x] Vector similarity retrieval
- [x] BM25 sparse retrieval
- [x] Fusion scoring (0.6 dense + 0.4 sparse)
- [x] LLM entity extraction with confidence scoring
- [x] LLM relation extraction with type validation
- [x] Iterative refinement loop

**Stats**:
- Entity extraction: ~66+ raw entities
- Relation extraction: type validation against ontology
- Confidence scores: 0.5-0.95 range

#### Phase 3: Assembly & Validation ✅
- [x] SHACL shape validation
- [x] Ontology constraint checking
- [x] Simple KG assembly (Neo4j)
- [x] RDF/JSON-LD export

**Stats**:
- Neo4j KG: 5-50 nodes typical
- Ontology: 342 RDF triples loaded
- Export formats: JSON-LD, RDF

#### Phase 4: Autonomous Discovery ✅
- [x] Question generation from ontology
- [x] Iterative discovery loop
- [x] Entity deduplication (FindingsSynthesizer)
- [x] Neo4j knowledge graph assembly

**Stats**:
- Questions generated: 5-10 per session
- Discovered entities: 60-100+ per question
- Merge rate: 40-60% (good deduplication)
- Test coverage: 89 tests, 87% average, 100% pass rate

#### Phase 5: Confidence Tuning (5.1-5.3) ✅
- [x] Confidence statistical analysis
- [x] Confidence score boosting
- [x] Coreference entity resolution

**Stats**:
- 22 unit tests, 100% pass rate
- 98%+ code coverage on confidence module
- 436 lines implementation, 324 lines tests

### Pending Features

#### Phase 5: Tasks 5.4-5.6 🟡
- [ ] **Task 5.4: ConfidenceCalibrator** (1.5h)
  - Per-type confidence calibration curves
  - Isotonic regression for reliability mapping
  
- [ ] **Task 5.5: ConsensusVoter** (1.5h)
  - LLM-based second opinions
  - Voting logic with tie-breaking
  
- [ ] **Task 5.6: EntityQualityFilter** (1h)
  - Final quality filtering
  - Markdown + JSON output report
  
- [ ] **Integration & Testing** (2h)
  - End-to-end pipeline test
  - Comprehensive documentation

#### Phase 6-12: Advanced Features (TBD)
- [ ] Relation confidence tuning
- [ ] Semantic consistency checking
- [ ] Interactive disambiguation
- [ ] Continuous learning loop
- [ ] Cloud deployment
- [ ] Web API
- [ ] QA system on KG

---

## Usage Examples

### Complete Pipeline

```python
from pathlib import Path
from kgbuilder.document.loaders import DocumentLoaderFactory
from kgbuilder.embedding.ollama import OllamaEmbeddingProvider
from kgbuilder.storage.vector import QdrantStore
from kgbuilder.extraction.entity import LLMEntityExtractor
from kgbuilder.confidence import (
    ConfidenceAnalyzer,
    ConfidenceBooster,
    CoreferenceResolver,
)

# 1. Load document
loader = DocumentLoaderFactory.get_loader(Path("document.pdf"))
doc = loader.load(Path("document.pdf"))

# 2. Chunk and embed
from kgbuilder.document.chunking.strategies import FixedSizeChunker
chunker = FixedSizeChunker(chunk_size=512)
chunks = chunker.chunk(doc)

embedding_provider = OllamaEmbeddingProvider(model="qwen3-embedding")
embeddings = [embedding_provider.embed(chunk.content) for chunk in chunks]

# 3. Store vectors
qdrant = QdrantStore("http://localhost:6333")
qdrant.store(chunks, embeddings)

# 4. Extract entities
extractor = LLMEntityExtractor(llm_model="qwen")
entities = extractor.extract(doc.content)

# 5. Analyze confidence
analyzer = ConfidenceAnalyzer()
report = analyzer.analyze(entities)
print(f"Mean confidence: {report.mean:.2%}")
print(f"Recommended threshold: {report.recommended_threshold:.2%}")

# 6. Boost confidence
booster = ConfidenceBooster()
boosted = booster.boost_batch(entities)

# 7. Resolve coreferences
resolver = CoreferenceResolver()
clusters = resolver.find_clusters(boosted, similarity_threshold=0.85)
for cluster in clusters:
    merged = resolver.merge_cluster(cluster, {e.id: e for e in boosted})
    print(f"Merged: {merged.label}")

# Result: High-quality, deduplicated entity set
print(f"Final entities: {len(entities)} (deduplicated)")
```

### Confidence Analysis Only

```python
from kgbuilder.confidence import ConfidenceAnalyzer, ConfidenceReport

analyzer = ConfidenceAnalyzer()

# Analyze existing entities
report = analyzer.analyze(my_entities)

# Get statistics
print(f"Mean: {report.mean:.2f}")
print(f"Median: {report.percentiles[50]:.2f}")
print(f"Std Dev: {report.std:.2f}")

# Per-type analysis
for entity_type, stats in report.per_type_stats.items():
    print(f"{entity_type}: {stats.count} entities, mean={stats.mean:.2f}")

# Find outliers
print(f"Anomalies: {report.anomalies}")

# Recommend filtering threshold
threshold = analyzer.recommend_threshold(my_entities, target_precision=0.90)
filtered = [e for e in my_entities if e.confidence >= threshold]
print(f"Filtered: {len(my_entities)} → {len(filtered)} (precision target 90%)")
```

### Entity Deduplication

```python
from kgbuilder.confidence import CoreferenceResolver

resolver = CoreferenceResolver()

# Find duplicate clusters
clusters = resolver.find_clusters(
    entities,
    similarity_threshold=0.85  # Fuzzy match threshold
)

print(f"Found {len(clusters)} clusters of duplicates")

# Merge each cluster
merged_entities = []
for cluster in clusters:
    merged = resolver.merge_cluster(
        cluster,
        {e.id: e for e in entities}
    )
    merged_entities.append(merged)
    print(f"Merged {len(cluster.entities)} entities → {merged.label}")

# Result: Deduplicated entity set with combined evidence
print(f"Before: {len(entities)}, After: {len(merged_entities)}")
```

---

## Storage Backends

### Qdrant (Vector Store)

**Purpose**: Semantic similarity search  
**Config**: `data/qdrant/`  
**Collection**: `kgbuilder` (4,096-dim vectors)

```python
from kgbuilder.storage.vector import QdrantStore

qdrant = QdrantStore("http://localhost:6333")

# Store embeddings
qdrant.store(chunks, embeddings)

# Search
results = qdrant.search(query_embedding, top_k=5)
```

### Neo4j (Knowledge Graph)

**Purpose**: Entity and relation storage  
**Config**: `bolt://localhost:7687`  
**Auth**: No authentication (local)

```python
from kgbuilder.storage.graph import Neo4jStore

neo4j = Neo4jStore("bolt://localhost:7687", auth=None)

# Create nodes
neo4j.create_node(entity_type="Organization", properties={...})

# Create relationships
neo4j.create_relationship(source_id, target_id, relation_type)

# Query
results = neo4j.query("MATCH (e:Entity) RETURN e LIMIT 10")
```

### Fuseki (RDF Store)

**Purpose**: Ontology and semantic triples  
**Config**: `http://localhost:3030/kgbuilder`  
**Dataset**: `kgbuilder`

```python
from kgbuilder.storage.rdf import FusekiStore

fuseki = FusekiStore("http://localhost:3030/kgbuilder")

# Load ontology
fuseki.load_rdf(ontology_file)

# Query ontology
results = fuseki.sparql_query("""
    SELECT ?class ?label WHERE {
        ?class rdfs:label ?label
    }
""")
```

---

## Project Roadmap

### Completed (Phases 1-5.3)
- ✅ Document ingestion and processing
- ✅ RAG-based retrieval
- ✅ Entity and relation extraction
- ✅ Knowledge graph assembly
- ✅ Autonomous discovery pipeline
- ✅ Confidence analysis and tuning (partial)

### In Progress (Phase 5.4-5.6)
- 🟡 Confidence calibration
- 🟡 Consensus voting
- 🟡 Quality filtering

### Planned (Phases 6-12)
- [ ] Relation confidence tuning
- [ ] Semantic consistency validation
- [ ] Interactive entity disambiguation
- [ ] Continuous learning loop
- [ ] REST API
- [ ] Web UI
- [ ] Cloud deployment

---

## Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.10+ |
| LLM | Ollama | qwen3, qwen3-embedding |
| Vector DB | Qdrant | Latest |
| Knowledge Graph | Neo4j | 5.x |
| RDF Store | Apache Fuseki | 4.x |
| Type Hints | Built-in | Python 3.9+ |
| Testing | pytest | Latest |
| Linting | ruff | Latest |
| Type Checking | mypy | Latest |
| Formatting | black | Latest |

---

## Contributing

See `.github/copilot-instructions.md` for development guidelines.

**Code Style**:
- Follow PEP 8 (100-char line length)
- Complete type hints on all functions
- Google-style docstrings
- 85%+ test coverage

**Testing**:
```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/confidence/test_analyzer.py

# With coverage
pytest tests/ --cov=src/kgbuilder
```

---

## License

MIT License - See [LICENSE](LICENSE) file

---

## Project Links

- **Documentation**: [local-docs/](local-docs/)
- **Planning**: [Planning/](Planning/)
- **Issues**: [Planning/ISSUES_BACKLOG.md](Planning/ISSUES_BACKLOG.md)
- **Architecture**: [Planning/ARCHITECTURE.md](Planning/ARCHITECTURE.md)

---

**Last Updated**: 2026-02-09  
**Maintained By**: Knowledge Graph Team  
**Status**: Active Development ✅ Entity ID bug fixed, pipeline running on all 33 docs
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
