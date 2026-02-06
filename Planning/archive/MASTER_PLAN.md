# KnowledgeGraphBuilder - Master Plan

> **Single Source of Truth** for all project planning, architecture, and implementation details.  
> **Last Updated**: February 3, 2026  
> **Project Status**: Phase 5 Complete | Phase 6 COMPLETE (Relation Extraction Integrated) | Phase 7 COMPLETE (Multi-Store Implementation)

---

## Table of Contents

1. [Project Vision](#1-project-vision)
2. [Architecture Overview](#2-architecture-overview)
3. [Technology Stack](#3-technology-stack)
4. [Phase Roadmap](#4-phase-roadmap)
5. [Current Status](#5-current-status)
6. [Detailed Phase Specifications](#6-detailed-phase-specifications)
7. [Implementation Guide](#7-implementation-guide)
8. [Testing Strategy](#8-testing-strategy)
9. [File Structure](#9-file-structure)
10. [Appendix: Data Models](#10-appendix-data-models)

---

## 1. Project Vision

### What We're Building

An **ontology-driven Knowledge Graph (KG) construction pipeline** that:

1. **Ingests** documents (PDF, DOCX, PPTX, etc.)
2. **Extracts** entities and relationships guided by domain ontology
3. **Builds** a validated Knowledge Graph with confidence scores
4. **Stores** in multiple backends (Neo4j, RDF/SPARQL)
5. **Exports** in standard formats (JSON-LD, RDF/Turtle, YARRRML)

### Core Principles

| Principle | Description |
|-----------|-------------|
| **Ontology-First** | All extraction guided by OWL ontology - entity types, relations, constraints |
| **Confidence-Scored** | Every entity/relation has confidence score with evidence provenance |
| **Evidence-Based** | All extracted facts traceable to source documents and chunks |
| **Iterative Refinement** | Multi-pass extraction with deduplication and quality filtering |
| **Multi-Model Consensus** | Use multiple LLMs to reduce bias and improve confidence |

### Target Outcomes

- **Entity Extraction F1**: >0.85
- **Relation Extraction F1**: >0.80
- **Entity Linking Accuracy**: >0.90
- **False Positive Rate**: <5%
- **Test Coverage**: >85%

---

## 2. Architecture Overview

### System Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INPUT LAYER                                     │
│    PDF │ DOCX │ PPTX │ TXT │ Markdown  →  DocumentLoaderFactory             │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DOCUMENT PROCESSING                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ Fixed Chunk  │  │ Semantic     │  │ Structural   │  │ Hierarchical │    │
│  │ (Tokens)     │  │ (Paragraph)  │  │ (Section)    │  │ (Nested)     │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
│                           ↓ Chunks with Metadata                            │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EMBEDDING LAYER                                    │
│  ┌─────────────────────┐        ┌─────────────────────────────────────┐    │
│  │ Ollama Embeddings   │   →    │ Qdrant Vector Database              │    │
│  │ (nomic/mxbai/qwen3) │        │ (4096-dim, hybrid search)           │    │
│  └─────────────────────┘        └─────────────────────────────────────┘    │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      KNOWLEDGE EXTRACTION LAYER                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    RAG-Guided Extraction                             │   │
│  │  1. Retrieve relevant chunks for ontology class                     │   │
│  │  2. LLM extracts entities with structured output                    │   │
│  │  3. Extract relations between entities                              │   │
│  │  4. Assign confidence scores with evidence                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                   Autonomous Discovery (Phase 4)                     │   │
│  │  Question Generation → Retrieval → Extraction → Synthesis           │   │
│  │  (3-5 iterations per question, 30-50 entities discovered)           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       CONFIDENCE TUNING LAYER (Phase 5)                      │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │ Analyzer   │→ │ Booster    │→ │ Coreference│→ │ Calibrator │            │
│  │ Statistics │  │ Evidence   │  │ Resolution │  │ Isotonic   │            │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘            │
│       ↓                                                                      │
│  ┌────────────┐  ┌────────────┐                                             │
│  │ Consensus  │→ │ Quality    │→  Filtered, High-Quality Entities          │
│  │ Voter      │  │ Filter     │                                             │
│  └────────────┘  └────────────┘                                             │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         KG ASSEMBLY LAYER (Phase 6)                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              GraphStore Protocol (Unified Interface)                 │   │
│  │  create_node() │ get_node() │ create_edge() │ query() │ export()    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       ↓                           ↓                           ↓             │
│  ┌──────────────┐        ┌──────────────┐        ┌──────────────────┐     │
│  │ Neo4jStore   │        │ RDFStore     │        │ KGExporter       │     │
│  │ (Cypher)     │        │ (SPARQL)     │        │ 5 formats        │     │
│  └──────────────┘        └──────────────┘        └──────────────────┘     │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              OUTPUT                                          │
│  Neo4j KG │ RDF Triplestore │ JSON-LD │ RDF/Turtle │ YARRRML │ GraphML     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | Module | Responsibility |
|-----------|--------|----------------|
| DocumentLoader | `document/loaders/` | Load PDF, DOCX, PPTX, etc. |
| ChunkingStrategy | `document/chunking/` | Split documents into chunks |
| EmbeddingProvider | `embedding/` | Generate vector embeddings |
| VectorStore | `storage/vector.py` | Store/search embeddings (Qdrant) |
| EntityExtractor | `extraction/entity.py` | Extract entities from text |
| RelationExtractor | `extraction/relation.py` | Extract relationships |
| ConfidenceAnalyzer | `confidence/analyzer.py` | Analyze confidence distributions |
| ConfidenceBooster | `confidence/booster.py` | Boost based on evidence |
| CoreferenceResolver | `confidence/coreference.py` | Merge duplicate entities |
| ConfidenceCalibrator | `confidence/calibrator.py` | Calibrate to actual precision |
| ConsensusVoter | `confidence/voter.py` | Multi-LLM consensus voting |
| EntityQualityFilter | `confidence/filter.py` | Filter low-quality entities |
| GraphStore | `storage/graph.py` | Store KG in Neo4j/RDF |
| KGExporter | `storage/export.py` | Export to various formats |

---

## 3. Technology Stack

### Core Stack

| Category | Technology | Purpose |
|----------|------------|---------|
| **Language** | Python 3.10+ | Primary implementation |
| **LLM** | Ollama (qwen3:8b, llama3.1) | Local LLM inference |
| **Embeddings** | Ollama (nomic-embed-text) | 4096-dim vectors |
| **Vector DB** | Qdrant | Semantic search, hybrid search |
| **Graph DB** | Neo4j | Property graph storage |
| **RDF Store** | Apache Fuseki | SPARQL queries, ontology |
| **Validation** | Pydantic 2.0+ | Data validation |
| **Testing** | pytest | Unit and integration tests |

### Development Tools

| Tool | Purpose |
|------|---------|
| ruff | Linting and formatting |
| mypy | Static type checking (strict) |
| black | Code formatting |
| structlog | Structured logging |
| pytest-cov | Coverage reporting |

### Infrastructure

```yaml
# docker-compose.yml services
services:
  neo4j:      # Graph database (bolt://localhost:7687)
  qdrant:     # Vector database (http://localhost:6333)
  fuseki:     # RDF/SPARQL store (http://localhost:3030)
  ollama:     # Local LLM server (http://localhost:11434)
```

---

## 4. Phase Roadmap

### Overview

| Phase | Name | Status | Tests | Description |
|-------|------|--------|-------|-------------|
| 1 | Core Infrastructure | ✅ Complete | N/A | Project setup, configs, Docker |
| 2 | Document Processing | ✅ Complete | 66 | Loaders, chunking, embedding |
| 3 | Entity Extraction | ✅ Complete | 89 | RAG, LLM extraction, validation |
| 4 | Autonomous Discovery | ✅ Complete | 70 | Question gen, discovery loop |
| 5 | Confidence Tuning | ✅ Complete | 86 | Analysis, calibration, filtering |
| **6** | **Relation Extraction** | **✅ COMPLETE** | **~40** | **Cross-doc relations, LLM extraction** |
| **7** | **KG Assembly & Multi-Store** | **✅ COMPLETE** | **36** | **Neo4j, RDF/SPARQL, KGBuilder** |
| 8 | Validation Pipeline | 🔴 Pending | - | SHACL, domain rules |
| 9 | Analytics & Evaluation | 🔴 Pending | - | Metrics, benchmarks |
| 10 | CLI & Orchestration | 🔴 Pending | - | User interface |
| 11 | Documentation & SDK | 🔴 Pending | - | API docs, tutorials |
| 12 | Experiment Tracking | 🔴 Pending | - | MLflow, comparison |

### Dependency Graph

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7
                                            ↓
                              ┌─────────────┼──────────────────┐
                              ↓             ↓                  ↓
                          Phase 8       Phase 10           Phase 11
                              ↓         (parallel)         (parallel)
                          Phase 9           ↓                  ↓
                              ↓             ↓                  ↓
                          Phase 12      Phase 12           Phase 12
```

### Time Estimates

| Phase | Estimate | Status |
|-------|----------|--------|
| Phases 1-6 | ~56h | ✅ Complete |
| Phase 7 | 20h | ✅ Complete |
| Phase 8 | 16h | 🟢 Starting |
| Phase 9 | 18h | Pending |
| Phase 10-12 | 50h | Pending (parallel) |
| **Total** | **~160h** | **~48% complete** |

---

## 5. Current Status

### What's Complete

#### Phase 6: Relation Extraction ✅

**COMPLETED** - Cross-document relation extraction fully integrated into `build_kg.py`:

| Component | File | Status |
|-----------|------|--------|
| LLMRelationExtractor | `src/kgbuilder/extraction/relation.py` | ✅ Complete |
| Relation Consolidation | `src/kgbuilder/extraction/synthesizer.py` | ✅ Complete |
| Pipeline Integration | `scripts/build_kg.py` | ✅ Complete |
| Cross-Document Retrieval | Helper functions in build_kg.py | ✅ Complete |

**Key Features**:
- ✅ LLM-based relation extraction with ontology constraints
- ✅ Domain/range validation per relation type
- ✅ Cardinality constraint enforcement (functional/inverse-functional)
- ✅ **Cross-document relation discovery** via retriever queries
- ✅ Relation confidence scoring with evidence
- ✅ Neo4j assembly with both nodes and edges

#### Phase 7: KG Assembly & Multi-Store ✅

**COMPLETED** - Multi-store knowledge graph architecture with unified GraphStore protocol:

| Task | Component | Lines | Tests | Coverage |
|------|-----------|-------|-------|----------|
| 7.1 | Neo4jGraphStore | 507 | 8 | 45% |
| 7.2 | RDFGraphStore | 561 | 8 | 46% |
| 7.3 | KGBuilder Orchestrator | 394 | 13 | 75% |
| 7.4 | build_kg.py Integration | 23 | - | Integrated |
| 7.5 | Testing & Documentation | 830 | 36 | 22% coverage |

**Key Capabilities**:
- ✅ **Neo4jGraphStore**: Full CRUD, Cypher queries, batch operations, statistics
- ✅ **RDFGraphStore**: SPARQL endpoint support, triple management, export to Turtle/JSON-LD
- ✅ **KGBuilder**: Multi-store coordination, auto query routing (SPARQL vs Cypher)
- ✅ **Dual-Write**: Synchronization between primary and secondary stores
- ✅ **Export Formats**: JSON-LD, RDF/Turtle, N-Triples, Cypher, GraphML
- ✅ **Error Handling**: Graceful degradation, retry logic, comprehensive logging
- ✅ **36 Tests**: All passing, covering Neo4j, RDF, and orchestrator
| 5.4 | ConfidenceCalibrator | 145 | 21 | 95%+ |
| 5.5 | ConsensusVoter | 242 | 17 | 88%+ |
| 5.6 | EntityQualityFilter | 287 | 26 | 92%+ |

**Key Capabilities**:
- Statistical analysis of confidence distributions
- Evidence-based confidence boosting
- Entity deduplication via coreference resolution
- Isotonic regression calibration per entity type
- Multi-LLM consensus voting for disputed entities
- Quality filtering with markdown/JSON reporting

#### Phase 6: Relation Extraction ✅

**COMPLETED** - Cross-document relation extraction fully integrated into `build_kg.py`:

| Component | File | Status |
|-----------|------|--------|
| LLMRelationExtractor | `src/kgbuilder/extraction/relation.py` | ✅ Complete |
| Relation Consolidation | `src/kgbuilder/extraction/synthesizer.py` | ✅ Complete |
| Pipeline Integration | `scripts/build_kg.py` | ✅ Complete |
| Cross-Document Retrieval | Helper functions in build_kg.py | ✅ Complete |

**Key Features**:
- ✅ LLM-based relation extraction with ontology constraints
- ✅ Domain/range validation per relation type
- ✅ Cardinality constraint enforcement (functional/inverse-functional)
- ✅ **Cross-document relation discovery** via retriever queries
- ✅ Relation confidence scoring with evidence
- ✅ Neo4j assembly with both nodes and edges
- ✅ Summary statistics including relation counts

**Architecture**:
```
PHASE 5: Relation Extraction (NEW)
  ├─ Build relation extractor
  ├─ Load ontology relations
  ├─ For each entity pair:
  │   ├─ Query retriever for co-occurrence chunks
  │   ├─ Extract relations from chunks (cross-document!)
  │   ├─ Validate against ontology constraints
  │   └─ Deduplicate by source→predicate→target
  └─ Return consolidated relations
```

See [CROSS_DOCUMENT_RELATIONS.md](./CROSS_DOCUMENT_RELATIONS.md) for detailed design.

### What's Next

#### Phase 7: KG Assembly & Multi-Store Integration (6-8h)

```
Phase 6 Entities + Relations → GraphStore Protocol → Neo4j/RDF Stores → 5 Export Formats
```

**Tasks**:
1. Enhanced KG Assembly Engine (2h)
2. GraphStore Protocol Definition (1.5h)
3. Neo4j Store Implementation (2h)
4. RDF/SPARQL Store Implementation (2h)
5. KG Export Framework (1.5h)
6. Multi-Store Integration (1.5h)

---

## 6. Detailed Phase Specifications

### Phase 6: KG Assembly & Multi-Store Integration

#### Task 6.1: Enhanced KG Assembly Engine

**Objective**: Upgrade SimpleKGAssembler to handle entity resolution and cross-document merging.

**Implementation**:

```python
# src/kgbuilder/assembly/kg_assembler.py

@dataclass
class AssemblyConfig:
    merge_threshold: float = 0.85
    batch_size: int = 100
    enable_provenance: bool = True

@dataclass  
class KGAssemblyResult:
    nodes_created: int
    edges_created: int
    nodes_merged: int
    conflicts_detected: int
    statistics: dict[str, Any]

class KGAssembler:
    def __init__(self, graph_store: GraphStore, config: AssemblyConfig | None = None):
        self._store = graph_store
        self._config = config or AssemblyConfig()
    
    def assemble(
        self,
        entities: list[SynthesizedEntity],
        relations: list[ExtractedRelation]
    ) -> KGAssemblyResult:
        """Assemble entities and relations into graph store."""
        # 1. Resolve entities against existing KG
        resolved = self._resolve_entities(entities)
        
        # 2. Create/update nodes in batch
        node_results = self._store.batch_create_nodes(resolved)
        
        # 3. Create edges with validation
        edge_results = self._create_edges(relations, node_results)
        
        # 4. Compute statistics
        return self._compute_result(node_results, edge_results)
    
    def assemble_incremental(
        self,
        entities: list[SynthesizedEntity],
        relations: list[ExtractedRelation]
    ) -> KGAssemblyResult:
        """Incrementally add to existing KG with deduplication."""
        # Query existing entities for matching
        existing = self._store.get_similar_nodes(entities)
        # Merge where similarity > threshold
        merged, new = self._merge_with_existing(entities, existing)
        ...
```

**Acceptance Criteria**:
- [ ] Entity resolution against existing KG
- [ ] Cross-document entity merging
- [ ] Incremental assembly support
- [ ] Batch operations for performance
- [ ] Statistics and provenance tracking

---

#### Task 6.2: GraphStore Protocol

**Objective**: Define unified interface for all graph storage backends.

**Implementation**:

```python
# src/kgbuilder/storage/protocol.py

from typing import Protocol, TypeVar, Any
from dataclasses import dataclass

@dataclass
class Node:
    id: str
    label: str
    node_type: str
    properties: dict[str, Any]
    
@dataclass
class Edge:
    id: str
    source_id: str
    target_id: str
    edge_type: str
    properties: dict[str, Any]

@dataclass
class QueryResult:
    records: list[dict[str, Any]]
    summary: dict[str, Any]

class GraphStore(Protocol):
    """Unified interface for graph storage backends."""
    
    # Node Operations
    def create_node(self, node: Node) -> str: ...
    def get_node(self, node_id: str) -> Node | None: ...
    def update_node(self, node_id: str, properties: dict) -> bool: ...
    def delete_node(self, node_id: str) -> bool: ...
    def get_similar_nodes(self, node: Node, threshold: float = 0.85) -> list[Node]: ...
    
    # Edge Operations  
    def create_edge(self, edge: Edge) -> str: ...
    def get_edge(self, edge_id: str) -> Edge | None: ...
    def get_edges_for_node(self, node_id: str) -> list[Edge]: ...
    
    # Batch Operations
    def batch_create_nodes(self, nodes: list[Node]) -> list[str]: ...
    def batch_create_edges(self, edges: list[Edge]) -> list[str]: ...
    
    # Query Operations
    def query(self, query: str, params: dict | None = None) -> QueryResult: ...
    def get_subgraph(self, node_ids: list[str], depth: int = 1) -> tuple[list[Node], list[Edge]]: ...
    
    # Transaction Support
    def begin_transaction(self) -> Any: ...
    def commit_transaction(self, tx: Any) -> None: ...
    def rollback_transaction(self, tx: Any) -> None: ...
    
    # Export
    def export(self, format: str) -> str | dict: ...
    
    # Health
    def health_check(self) -> bool: ...
    def get_statistics(self) -> dict[str, Any]: ...
```

**Acceptance Criteria**:
- [ ] Complete Protocol definition
- [ ] Node, Edge, QueryResult dataclasses
- [ ] Custom exceptions (GraphStoreError, NodeNotFoundError, etc.)
- [ ] Type stubs for IDE support
- [ ] 90%+ test coverage for protocol compliance

---

#### Task 6.3: Neo4j Store Implementation

**Objective**: Implement GraphStore for Neo4j backend.

**Implementation**:

```python
# src/kgbuilder/storage/neo4j_store.py

from neo4j import GraphDatabase, Driver
from .protocol import GraphStore, Node, Edge, QueryResult

class Neo4jGraphStore:
    """Neo4j implementation of GraphStore protocol."""
    
    def __init__(self, uri: str, user: str, password: str):
        self._driver: Driver = GraphDatabase.driver(uri, auth=(user, password))
        self._ensure_indices()
    
    def _ensure_indices(self) -> None:
        """Create indices for common queries."""
        with self._driver.session() as session:
            # Index on node ID
            session.run("CREATE INDEX node_id IF NOT EXISTS FOR (n:Entity) ON (n.id)")
            # Index on node type
            session.run("CREATE INDEX node_type IF NOT EXISTS FOR (n:Entity) ON (n.type)")
    
    def create_node(self, node: Node) -> str:
        query = """
        CREATE (n:Entity {id: $id, label: $label, type: $type})
        SET n += $properties
        RETURN n.id AS id
        """
        with self._driver.session() as session:
            result = session.run(query, id=node.id, label=node.label, 
                                type=node.node_type, properties=node.properties)
            return result.single()["id"]
    
    def query(self, query: str, params: dict | None = None) -> QueryResult:
        with self._driver.session() as session:
            result = session.run(query, params or {})
            records = [dict(record) for record in result]
            summary = result.consume()
            return QueryResult(
                records=records,
                summary={"counters": summary.counters.__dict__}
            )
    
    def export(self, format: str) -> str | dict:
        """Export graph in specified format."""
        if format == "cypher":
            return self._export_cypher()
        elif format == "graphml":
            return self._export_graphml()
        raise ValueError(f"Unsupported format: {format}")
```

**Acceptance Criteria**:
- [ ] All CRUD operations working
- [ ] Batch operations with transactions
- [ ] Index creation for performance
- [ ] Cypher query support
- [ ] Path finding and subgraph extraction
- [ ] 80%+ test coverage

---

#### Task 6.4: RDF/SPARQL Store Implementation

**Objective**: Implement GraphStore for Apache Fuseki RDF backend.

**Implementation**:

```python
# src/kgbuilder/storage/rdf_store.py

from SPARQLWrapper import SPARQLWrapper, JSON
from rdflib import Graph, Namespace, URIRef, Literal
from .protocol import GraphStore, Node, Edge, QueryResult

class RDFGraphStore:
    """RDF/SPARQL implementation of GraphStore protocol."""
    
    def __init__(self, sparql_endpoint: str, update_endpoint: str, graph_uri: str):
        self._query_endpoint = SPARQLWrapper(sparql_endpoint)
        self._update_endpoint = SPARQLWrapper(update_endpoint)
        self._graph_uri = graph_uri
        self._ns = Namespace("http://kgbuilder.io/ontology#")
    
    def create_node(self, node: Node) -> str:
        """Create node as RDF triples."""
        node_uri = URIRef(f"{self._ns}{node.id}")
        
        # Build INSERT query
        triples = [
            f"<{node_uri}> rdf:type <{self._ns}{node.node_type}> .",
            f"<{node_uri}> rdfs:label \"{node.label}\" .",
        ]
        for key, value in node.properties.items():
            triples.append(f"<{node_uri}> <{self._ns}{key}> \"{value}\" .")
        
        query = f"""
        INSERT DATA {{
            GRAPH <{self._graph_uri}> {{
                {chr(10).join(triples)}
            }}
        }}
        """
        self._execute_update(query)
        return node.id
    
    def query(self, query: str, params: dict | None = None) -> QueryResult:
        """Execute SPARQL query."""
        self._query_endpoint.setQuery(query)
        self._query_endpoint.setReturnFormat(JSON)
        results = self._query_endpoint.query().convert()
        
        records = []
        for binding in results["results"]["bindings"]:
            record = {k: v["value"] for k, v in binding.items()}
            records.append(record)
        
        return QueryResult(records=records, summary={"type": "sparql"})
    
    def export(self, format: str) -> str:
        """Export graph in RDF format."""
        if format == "turtle":
            return self._export_turtle()
        elif format == "jsonld":
            return self._export_jsonld()
        elif format == "ntriples":
            return self._export_ntriples()
        raise ValueError(f"Unsupported format: {format}")
```

**Acceptance Criteria**:
- [ ] Node/Edge to RDF triple mapping
- [ ] SPARQL query execution
- [ ] INSERT/DELETE operations
- [ ] Ontology integration (use existing classes)
- [ ] Export to Turtle, JSON-LD, N-Triples
- [ ] 75%+ test coverage

---

#### Task 6.5: KG Export Framework

**Objective**: Create unified export system supporting 5 formats.

**Implementation**:

```python
# src/kgbuilder/storage/export.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
import json

@dataclass
class ExportConfig:
    include_metadata: bool = True
    include_provenance: bool = True
    pretty_print: bool = True

class KGExporter:
    """Export knowledge graph to multiple formats."""
    
    def __init__(self, config: ExportConfig | None = None):
        self._config = config or ExportConfig()
    
    def export_jsonld(
        self,
        nodes: list[Node],
        edges: list[Edge],
        context: dict | None = None
    ) -> dict:
        """Export as JSON-LD."""
        default_context = {
            "@vocab": "http://kgbuilder.io/ontology#",
            "label": "rdfs:label",
            "type": "@type"
        }
        
        graph = []
        for node in nodes:
            graph.append({
                "@id": f"kg:{node.id}",
                "@type": node.node_type,
                "label": node.label,
                **node.properties
            })
        
        return {
            "@context": context or default_context,
            "@graph": graph
        }
    
    def export_rdf_turtle(self, nodes: list[Node], edges: list[Edge]) -> str:
        """Export as RDF/Turtle."""
        lines = [
            "@prefix kg: <http://kgbuilder.io/ontology#> .",
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
            ""
        ]
        
        for node in nodes:
            lines.append(f"kg:{node.id} a kg:{node.node_type} ;")
            lines.append(f'    rdfs:label "{node.label}" .')
        
        for edge in edges:
            lines.append(f"kg:{edge.source_id} kg:{edge.edge_type} kg:{edge.target_id} .")
        
        return "\n".join(lines)
    
    def export_yarrrml(self, nodes: list[Node], edges: list[Edge]) -> dict:
        """Export as YARRRML mapping rules."""
        return {
            "prefixes": {
                "kg": "http://kgbuilder.io/ontology#",
                "rdfs": "http://www.w3.org/2000/01/rdf-schema#"
            },
            "mappings": self._generate_yarrrml_mappings(nodes, edges)
        }
    
    def export_cypher(self, nodes: list[Node], edges: list[Edge]) -> str:
        """Export as Cypher CREATE statements."""
        statements = []
        
        for node in nodes:
            props = ", ".join(f"{k}: {json.dumps(v)}" for k, v in node.properties.items())
            statements.append(
                f"CREATE (n:{node.node_type} {{id: '{node.id}', label: '{node.label}', {props}}})"
            )
        
        for edge in edges:
            statements.append(
                f"MATCH (a {{id: '{edge.source_id}'}}), (b {{id: '{edge.target_id}'}}) "
                f"CREATE (a)-[:{edge.edge_type}]->(b)"
            )
        
        return ";\n".join(statements) + ";"
    
    def export_graphml(self, nodes: list[Node], edges: list[Edge]) -> str:
        """Export as GraphML XML."""
        # XML generation for GraphML format
        ...
```

**Export Formats**:

| Format | Use Case | Extension |
|--------|----------|-----------|
| JSON-LD | Linked Data interchange | `.jsonld` |
| RDF/Turtle | Semantic Web, SPARQL | `.ttl` |
| YARRRML | RDF mapping rules | `.yaml` |
| Cypher | Neo4j import | `.cypher` |
| GraphML | Graph visualization tools | `.graphml` |

**Acceptance Criteria**:
- [ ] All 5 formats implemented
- [ ] Validation for each format
- [ ] Selective export (entity types, subgraph)
- [ ] Metadata and provenance options
- [ ] 85%+ test coverage

---

#### Task 6.6: Multi-Store Integration

**Objective**: Create orchestration layer for multi-store coordination.

**Implementation**:

```python
# src/kgbuilder/assembly/kg_builder.py

from dataclasses import dataclass
from typing import Any

@dataclass
class StorageConfig:
    primary_store: str = "neo4j"  # neo4j | rdf | both
    enable_sync: bool = True
    export_formats: list[str] = field(default_factory=lambda: ["jsonld"])

class KGBuilder:
    """Main orchestrator for KG building with multi-store support."""
    
    def __init__(
        self,
        neo4j_store: Neo4jGraphStore | None = None,
        rdf_store: RDFGraphStore | None = None,
        config: StorageConfig | None = None
    ):
        self._neo4j = neo4j_store
        self._rdf = rdf_store
        self._config = config or StorageConfig()
        self._assembler = KGAssembler(self._get_primary_store())
        self._exporter = KGExporter()
    
    def build(
        self,
        entities: list[SynthesizedEntity],
        relations: list[ExtractedRelation]
    ) -> KGBuildResult:
        """Build KG from entities and relations."""
        # 1. Assemble to primary store
        assembly_result = self._assembler.assemble(entities, relations)
        
        # 2. Sync to secondary store if enabled
        if self._config.enable_sync and self._config.primary_store == "both":
            self._sync_stores()
        
        # 3. Generate exports
        exports = {}
        for fmt in self._config.export_formats:
            exports[fmt] = self._exporter.export(fmt, entities, relations)
        
        return KGBuildResult(
            assembly=assembly_result,
            exports=exports,
            stores_synced=self._config.enable_sync
        )
    
    def query(self, query: str, store: str = "auto") -> QueryResult:
        """Query KG using appropriate store."""
        if store == "auto":
            # Auto-detect: SPARQL → RDF, Cypher → Neo4j
            if query.strip().upper().startswith("SELECT"):
                return self._rdf.query(query)
            else:
                return self._neo4j.query(query)
        ...
    
    def health_check(self) -> dict[str, bool]:
        """Check health of all configured stores."""
        return {
            "neo4j": self._neo4j.health_check() if self._neo4j else False,
            "rdf": self._rdf.health_check() if self._rdf else False
        }
```

**Acceptance Criteria**:
- [ ] Multi-store coordination working
- [ ] Query routing (auto-detect or explicit)
- [ ] Store synchronization
- [ ] Health checking
- [ ] Configuration management
- [ ] 80%+ test coverage

---

### Phase 7: Relationship Extraction

**Objective**: Extract typed relationships between entities.

**Tasks**:
1. Relation Type Definition (from ontology)
2. Relation Extraction (LLM-based with prompting)
3. Relation Typing & Classification
4. Relation Confidence & Evidence
5. Cycle Detection

**Key Components**:

```python
class RelationExtractor:
    def extract_relations(
        self,
        text: str,
        entities: list[Entity],
        ontology: Ontology
    ) -> list[Relation]:
        """Extract relations guided by ontology constraints."""
        ...

class RelationTyper:
    def type_relation(
        self,
        relation: Relation,
        ontology: Ontology
    ) -> Relation:
        """Assign ontology-compliant type to relation."""
        ...
```

---

### Phase 8: Validation Pipeline

**Objective**: Validate KG against ontology and domain rules.

**Tasks**:
1. SHACL Shape Validation
2. Domain Rule Checking
3. Conflict Detection
4. Quality Metrics
5. Automatic Correction

**Validation Flow**:
```
KG → SHACL Validator → Domain Rules → Conflict Check → Report
```

---

### Phase 9-12: Future Phases

See [ROADMAP_PHASES_5_TO_12.md](../local-docs/ROADMAP_PHASES_5_TO_12.md) for detailed specifications.

---

## 7. Implementation Guide

### Development Workflow

```bash
# 1. Setup environment
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. Start services
docker-compose up -d

# 3. Run tests
PYTHONPATH=src pytest tests/ -v --cov=kgbuilder

# 4. Check types
mypy src/

# 5. Format code
ruff format src/ tests/
```

### Creating a New Component

1. **Define Protocol** (if needed) in `src/kgbuilder/core/protocols.py`
2. **Create Module** in appropriate package
3. **Write Tests** alongside implementation
4. **Add Exports** to `__init__.py`
5. **Update Docs** if public API

### Code Style

```python
# Good: Type hints, docstrings, dataclasses
from dataclasses import dataclass
from typing import Protocol

@dataclass
class MyResult:
    """Result of my operation."""
    value: float
    metadata: dict[str, Any]

class MyService:
    """Service that does something."""
    
    def process(self, input: str) -> MyResult:
        """Process input and return result.
        
        Args:
            input: The input string.
            
        Returns:
            MyResult with processed value.
            
        Raises:
            ValueError: If input is empty.
        """
        if not input:
            raise ValueError("Input cannot be empty")
        return MyResult(value=1.0, metadata={})
```

---

## 8. Testing Strategy

### Test Organization

```
tests/
├── conftest.py           # Shared fixtures
├── document/
│   ├── test_loaders.py
│   └── test_chunking.py
├── extraction/
│   ├── test_entity.py
│   └── test_relation.py
├── confidence/
│   ├── test_analyzer.py
│   ├── test_booster.py
│   ├── test_calibrator.py
│   ├── test_voter.py
│   └── test_filter.py
└── integration/
    └── test_pipeline.py
```

### Test Patterns

```python
# Unit test with fixtures
class TestMyService:
    @pytest.fixture
    def service(self) -> MyService:
        return MyService()
    
    def test_process_valid_input(self, service: MyService) -> None:
        result = service.process("test")
        assert result.value > 0
    
    def test_process_empty_raises(self, service: MyService) -> None:
        with pytest.raises(ValueError):
            service.process("")
```

### Running Tests

```bash
# All tests
PYTHONPATH=src pytest tests/ -v

# Specific module
PYTHONPATH=src pytest tests/confidence/ -v

# With coverage
PYTHONPATH=src pytest tests/ --cov=kgbuilder --cov-report=html
```

---

## 9. File Structure

```
KnowledgeGraphBuilder/
├── src/
│   └── kgbuilder/
│       ├── __init__.py
│       ├── core/               # Shared abstractions
│       │   ├── protocols.py    # All Protocol definitions
│       │   ├── models.py       # Shared data models
│       │   └── exceptions.py   # Exception hierarchy
│       ├── document/           # Document processing
│       │   ├── loaders/        # PDF, DOCX, PPTX loaders
│       │   └── chunking/       # Chunking strategies
│       ├── embedding/          # Embedding operations
│       │   └── ollama.py       # Ollama embeddings
│       ├── extraction/         # Entity/relation extraction
│       │   ├── entity.py       # Entity extractor
│       │   ├── relation.py     # Relation extractor
│       │   └── synthesizer.py  # Findings synthesizer
│       ├── confidence/         # Confidence tuning
│       │   ├── analyzer.py     # Statistics
│       │   ├── booster.py      # Evidence boosting
│       │   ├── coreference.py  # Deduplication
│       │   ├── calibrator.py   # Isotonic calibration
│       │   ├── voter.py        # Consensus voting
│       │   └── filter.py       # Quality filtering
│       ├── assembly/           # KG assembly
│       │   ├── simple_kg_assembler.py
│       │   └── kg_assembler.py # Enhanced (Phase 6)
│       ├── storage/            # Database connectors
│       │   ├── protocol.py     # GraphStore protocol
│       │   ├── neo4j_store.py  # Neo4j implementation
│       │   ├── rdf_store.py    # RDF/SPARQL implementation
│       │   └── export.py       # Export formats
│       ├── agents/             # Agent implementations
│       │   ├── question_generator.py
│       │   └── discovery_loop.py
│       └── validation/         # SHACL validation
├── tests/                      # Test suites (mirror src/)
├── scripts/                    # Utility scripts
├── data/                       # Data files
│   ├── ontology/              # OWL ontology files
│   └── documents/             # Source documents
├── Planning/                   # THIS DOCUMENT + architecture
├── local-docs/                # Session-specific docs (can be cleaned)
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

## 10. Appendix: Data Models

### Core Models

```python
# src/kgbuilder/core/models.py

@dataclass
class Evidence:
    """Evidence supporting an extraction."""
    source_type: str  # "document" | "chunk" | "llm"
    source_id: str
    text_span: str
    confidence: float = 1.0

@dataclass
class ExtractedEntity:
    """Entity extracted from documents."""
    id: str
    label: str
    entity_type: str
    description: str
    confidence: float
    evidence: list[Evidence]
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class SynthesizedEntity:
    """Entity after deduplication and synthesis."""
    id: str
    label: str
    entity_type: str
    description: str
    confidence: float
    evidence: list[Evidence]
    merged_from: list[str]  # IDs of merged entities
    merge_count: int

@dataclass
class ExtractedRelation:
    """Relationship between entities."""
    id: str
    source_entity_id: str
    target_entity_id: str
    predicate: str
    confidence: float
    evidence: list[Evidence]
```

### Confidence Models

```python
# src/kgbuilder/confidence/

@dataclass
class ConfidenceReport:
    """Report from confidence analysis."""
    total_entities: int
    mean: float
    std_dev: float
    percentiles: dict[str, float]
    by_type: dict[str, TypeStats]
    anomalies: list[str]

@dataclass
class CalibrationResult:
    """Result of confidence calibration."""
    entity_id: str
    raw_confidence: float
    calibrated_confidence: float
    calibration_method: str
    uncertainty: float

@dataclass
class VotingResult:
    """Result of consensus voting."""
    entity_id: str
    voted_confidence: float
    vote_agreement: float
    agreeing_votes: int
    total_votes: int
    reasoning: str

@dataclass
class QualityReport:
    """Quality filtering report."""
    total_entities: int
    filtered_entities: int
    removal_rate: float
    quality_issues: list[str]
    timestamp: str
```

---

## Document Maintenance

### When to Update This Document

- **After each phase completion**: Update status, add lessons learned
- **Architecture changes**: Update diagrams and component descriptions
- **New components**: Add to file structure and implementation guide
- **API changes**: Update data models and code examples

### Related Documents

| Document | Purpose | Location |
|----------|---------|----------|
| README.md | User-facing quick start | Root |
| ARCHITECTURE.md | Detailed architecture diagrams | Planning/ |
| ISSUES_BACKLOG.md | Issue tracking (deprecated - use this) | Planning/ |

### Cleanup Candidates

The following `local-docs/` files can be archived/deleted once this document is validated:

- PHASE_*_COMPLETE.md (superseded by this document)
- SESSION_SUMMARY.md (session-specific)
- INDEX*.md (superseded by this document)
- IMPLEMENTATION_STATUS*.md (superseded)
- *_QUICKSTART.md (merged into this)

---

*Last Updated: February 3, 2026*
