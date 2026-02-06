# Phase 7: KG Assembly & Multi-Store Integration

**Status**: 🟢 Starting  
**Date**: February 3, 2026  
**Estimate**: 6-8 hours  
**Branch**: `feature/phase-7-multi-store`

---

## Overview

**Goal**: Enable KG assembly and export in multiple formats (JSON-LD, RDF/Turtle, YARRRML, Cypher, GraphML) with support for both Neo4j and RDF/SPARQL backends.

**Input**: Entities + Relations from Phase 6  
**Output**: Queryable KGs in Neo4j + RDF + 5 export formats

---

## Task Breakdown

### Task 7.1: GraphStore Protocol Definition (1.5h)
**Objective**: Define unified interface for all graph storage backends.

**Deliverables**:
- [ ] `src/kgbuilder/storage/protocol.py` with `GraphStore` protocol
- [ ] `Node`, `Edge`, `QueryResult` dataclasses
- [ ] Exception hierarchy (`GraphStoreError`, `NodeNotFoundError`, etc.)
- [ ] CRUD operations (create, read, update, delete)
- [ ] Batch operations interface
- [ ] Query interface (store-agnostic)
- [ ] Export interface
- [ ] Health check interface

**Key Design**:
```python
class GraphStore(Protocol):
    """Unified interface for graph storage backends."""
    
    # Node Operations
    def create_node(self, node: Node) -> str: ...
    def get_node(self, node_id: str) -> Node | None: ...
    def update_node(self, node_id: str, properties: dict) -> bool: ...
    def delete_node(self, node_id: str) -> bool: ...
    
    # Edge Operations  
    def create_edge(self, edge: Edge) -> str: ...
    def get_edge(self, edge_id: str) -> Edge | None: ...
    def get_edges_for_node(self, node_id: str) -> list[Edge]: ...
    
    # Batch Operations
    def batch_create_nodes(self, nodes: list[Node]) -> list[str]: ...
    def batch_create_edges(self, edges: list[Edge]) -> list[str]: ...
    
    # Query Operations
    def query(self, query: str, params: dict | None = None) -> QueryResult: ...
    
    # Export
    def export(self, format: str) -> str | dict: ...
```

**Status**: ⬜ Not Started

---

### Task 7.2: Neo4j Store Implementation (2h)
**Objective**: Implement GraphStore for Neo4j backend.

**Deliverables**:
- [ ] `src/kgbuilder/storage/neo4j_store.py` implementing `GraphStore`
- [ ] CRUD operations
- [ ] Batch create with transactions
- [ ] Index creation for performance
- [ ] Cypher query support
- [ ] Subgraph extraction
- [ ] Export to Cypher CREATE statements
- [ ] Tests with mock Neo4j driver

**Key Components**:
- Connection pooling with retry logic
- Transaction management
- Batch operations (bulk insert)
- Index strategies (node ID, node type, confidence)
- Query result mapping

**Status**: ⬜ Not Started

---

### Task 7.3: RDF/SPARQL Store Implementation (2h)
**Objective**: Implement GraphStore for Apache Fuseki RDF backend.

**Deliverables**:
- [ ] `src/kgbuilder/storage/rdf_store.py` implementing `GraphStore`
- [ ] Node/Edge to RDF triple mapping
- [ ] SPARQL query execution
- [ ] INSERT/DELETE operations
- [ ] Ontology integration
- [ ] Export to Turtle, JSON-LD, N-Triples
- [ ] Tests with mock SPARQL endpoint

**Key Components**:
- RDFLib for triple construction
- SPARQLWrapper for remote queries
- Namespace management
- SPARQL CONSTRUCT queries for subgraph extraction

**Status**: ⬜ Not Started

---

### Task 7.4: KG Export Framework (1.5h)
**Objective**: Create unified export system supporting 5 formats.

**Deliverables**:
- [ ] `src/kgbuilder/storage/export.py` with `KGExporter`
- [ ] JSON-LD export with @context
- [ ] RDF/Turtle export
- [ ] YARRRML mapping rules
- [ ] Cypher CREATE statements
- [ ] GraphML XML format
- [ ] `ExportConfig` for selective export
- [ ] Validation for each format

**Formats**:

| Format | Use Case | File Ext | Status |
|--------|----------|----------|--------|
| JSON-LD | Linked Data interchange | `.jsonld` | ⬜ |
| RDF/Turtle | Semantic Web, SPARQL | `.ttl` | ⬜ |
| YARRRML | RDF mapping rules | `.yaml` | ⬜ |
| Cypher | Neo4j import | `.cypher` | ⬜ |
| GraphML | Graph visualization | `.graphml` | ⬜ |

**Status**: ⬜ Not Started

---

### Task 7.5: Multi-Store Integration (1.5h)
**Objective**: Create orchestration layer for multi-store coordination.

**Deliverables**:
- [ ] `src/kgbuilder/assembly/kg_builder.py` with `KGBuilder`
- [ ] Store selection logic
- [ ] Query routing (auto-detect SPARQL vs Cypher)
- [ ] Store synchronization (dual-write)
- [ ] Health checking for all stores
- [ ] Configuration management
- [ ] Result aggregation from multiple stores

**Key Features**:
- Primary store selection (Neo4j | RDF | both)
- Query auto-routing (SPARQL → RDF, Cypher → Neo4j)
- Automatic store failover
- Consistent result format across stores

**Status**: ⬜ Not Started

---

## Dependencies

```
7.1 (Protocol) ────→ 7.2 (Neo4j)  ──┐
                                    ├──→ 7.4 (Export) ──→ 7.5 (Integration)
                 ┌──→ 7.3 (RDF)    ──┘
                 │
       (parallel)
```

**Order**:
1. Start with 7.1 (Protocol) - foundation for all stores
2. Parallel: 7.2 (Neo4j) + 7.3 (RDF) - both implement Protocol
3. Then: 7.4 (Export) - uses stores for data extraction
4. Finally: 7.5 (Integration) - orchestrates everything

---

## Test Strategy

### Unit Tests
- Mock implementations of GraphStore protocol
- Mock Neo4j driver and SPARQL endpoint
- Test each CRUD operation
- Test query parsing and result mapping
- Test export format generation

### Integration Tests
- Real Neo4j instance (docker-compose)
- Real Fuseki instance (docker-compose)
- End-to-end KG assembly
- Query execution across stores
- Multi-store synchronization

### Test Files
```
tests/storage/
├── test_protocol.py          # Protocol compliance
├── test_neo4j_store.py       # Neo4j implementation
├── test_rdf_store.py         # RDF implementation
├── test_export.py            # Export formats
└── test_kg_builder.py        # Integration
```

---

## Implementation Checklist

### Phase 7.1: Protocol
- [ ] Node dataclass with properties
- [ ] Edge dataclass with properties
- [ ] QueryResult dataclass
- [ ] GraphStore protocol with all methods
- [ ] Exception hierarchy
- [ ] Type hints and docstrings
- [ ] Tests for protocol structure

### Phase 7.2: Neo4j Store
- [ ] Connection management
- [ ] Index creation
- [ ] Node CRUD operations
- [ ] Edge CRUD operations
- [ ] Batch operations with transactions
- [ ] Cypher query execution
- [ ] Export to Cypher statements
- [ ] Tests (80%+ coverage)

### Phase 7.3: RDF Store
- [ ] SPARQL endpoint connection
- [ ] Node to RDF triple conversion
- [ ] Edge to RDF triple conversion
- [ ] SPARQL INSERT/DELETE operations
- [ ] SPARQL SELECT query execution
- [ ] Export to Turtle/JSON-LD/N-Triples
- [ ] Tests (75%+ coverage)

### Phase 7.4: Export Framework
- [ ] JSON-LD generation with context
- [ ] RDF/Turtle serialization
- [ ] YARRRML mapping generation
- [ ] Cypher CREATE statement generation
- [ ] GraphML XML generation
- [ ] Format validation
- [ ] Tests for all 5 formats

### Phase 7.5: Integration
- [ ] KGBuilder orchestrator
- [ ] Store selection logic
- [ ] Query routing (auto-detect)
- [ ] Dual-write synchronization
- [ ] Health checking
- [ ] Configuration management
- [ ] Tests (80%+ coverage)

---

## Code Structure

```
src/kgbuilder/storage/
├── __init__.py               # Public API
├── protocol.py              # GraphStore, Node, Edge, QueryResult
├── neo4j_store.py           # Neo4j implementation
├── rdf_store.py             # RDF/SPARQL implementation
├── export.py                # KGExporter (all 5 formats)
└── exceptions.py            # GraphStoreError hierarchy

src/kgbuilder/assembly/
├── kg_builder.py            # KGBuilder orchestrator (NEW)
└── simple_kg_assembler.py   # Existing (will be used by KGBuilder)
```

---

## Success Criteria

- [ ] All 5 export formats working
- [ ] Both Neo4j and RDF stores functional
- [ ] Query routing between stores working
- [ ] Multi-store sync verified
- [ ] No type errors (mypy strict)
- [ ] No linting errors (ruff)
- [ ] 80%+ test coverage
- [ ] Documentation complete
- [ ] Docker compose includes both Neo4j and Fuseki

---

## Next Steps After Phase 7

**Phase 8**: Validation Pipeline
- SHACL shape validation
- Domain rule checking
- Conflict detection

**Phase 9**: Analytics & Evaluation
- Quality metrics
- Performance benchmarks
- Evaluation suite

---

## Resources

- **GraphStore Protocol Docs**: [MASTER_PLAN.md](./MASTER_PLAN.md#task-62-graphstore-protocol)
- **Neo4j Driver Docs**: https://neo4j.com/docs/python-manual/current/
- **SPARQLWrapper Docs**: https://sparqlwrapper.readthedocs.io/
- **JSON-LD Spec**: https://www.w3.org/TR/json-ld11/
- **RDF/Turtle Spec**: https://www.w3.org/TR/turtle/

---

**Ready to Start**: Yes ✅  
**Branch**: `feature/phase-7-multi-store`  
**Let's begin with Task 7.1!**
