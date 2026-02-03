# Phase 7 Implementation Plan: What's Already Done & What's Needed

**Status**: Assessment Complete  
**Date**: February 3, 2026  
**Current State**: Significant foundation exists, refactoring + enhancement needed

---

## Current State Assessment

### ✅ What Already Exists

1. **Protocol Foundation** (`src/kgbuilder/storage/protocol.py` - 707 lines)
   - ✅ Node, Edge, QueryResult dataclasses
   - ✅ GraphStore Protocol with full interface
   - ✅ GraphStatistics dataclass
   - ✅ InMemoryGraphStore implementation (full CRUD)
   - ✅ to_dict(), from_dict() serialization

2. **Export Module** (`src/kgbuilder/storage/export.py` - 513 lines)
   - ✅ KGExporter class with multiple formats
   - ✅ to_jsonld() - JSON-LD format
   - ✅ to_turtle() - RDF Turtle
   - ✅ to_cypher() - Neo4j Cypher statements
   - ✅ to_graphml() - GraphML XML
   - ✅ export_to_file() method
   - ✅ ExportConfig for selective export

3. **Neo4j Assembly** (`src/kgbuilder/assembly/simple_kg_assembler.py` - 436 lines)
   - ✅ Directly writes to Neo4j
   - ✅ Transaction management
   - ✅ Confidence & provenance tracking
   - ✅ Index creation

4. **RDF Store** (`src/kgbuilder/storage/rdf.py` - exists)
   - ✅ Basic structure in place

### ⚠️ What Needs Work

1. **Neo4j Store Refactoring**
   - [ ] Extract Neo4j logic from SimpleKGAssembler into a store class
   - [ ] Make it compatible with GraphStore Protocol
   - [ ] Add query execution capability
   - [ ] Add export methods

2. **RDF Store Enhancement**
   - [ ] Fully implement GraphStore Protocol
   - [ ] Add SPARQL query support
   - [ ] Add export methods

3. **Multi-Store Integration**
   - [ ] Create KGBuilder orchestrator
   - [ ] Add query routing (SPARQL vs Cypher)
   - [ ] Add store synchronization
   - [ ] Add health checking

4. **Tests**
   - [ ] Complete export tests
   - [ ] Add Neo4j store tests
   - [ ] Add RDF store tests
   - [ ] Add integration tests

---

## Revised Phase 7 Plan

### Task 7.1: Neo4j Store Implementation (2.5h)
**Refactor SimpleKGAssembler → Neo4jGraphStore**

**Objectives**:
1. Extract Neo4j connection logic into `Neo4jGraphStore` class
2. Implement GraphStore Protocol fully
3. Add query execution
4. Keep existing SimpleKGAssembler as thin wrapper or deprecate

**File**: `src/kgbuilder/storage/neo4j_store.py`

**Key Methods to Add**:
- `create_node(node: Node) -> str`
- `get_node(node_id: str) -> Node | None`
- `batch_create_nodes(nodes: list[Node]) -> list[str]`
- `batch_create_edges(edges: list[Edge]) -> list[str]`
- `query(query_str: str, params: dict) -> QueryResult`
- `get_subgraph(node_ids: list[str], depth: int) -> tuple[list[Node], list[Edge]]`
- `export(format: str) -> str`
- `get_statistics() -> GraphStatistics`

**Status**: ⬜ Not Started (2.5h)

---

### Task 7.2: RDF Store Enhancement (2h)
**Complete RDFGraphStore implementation**

**Current State**: File exists but incomplete

**Objectives**:
1. Implement full GraphStore Protocol
2. Add SPARQL query execution
3. Add export methods (Turtle, JSON-LD, N-Triples)
4. Add tests

**File**: `src/kgbuilder/storage/rdf.py` (existing) or refactor

**Key Methods**:
- Same as Neo4j but using RDF/SPARQL backend
- INSERT queries for adding nodes/edges
- CONSTRUCT queries for retrieval
- CONSTRUCT queries for subgraph extraction

**Status**: ⬜ Not Started (2h)

---

### Task 7.3: KG Builder Orchestrator (1.5h)
**Create multi-store coordination layer**

**File**: `src/kgbuilder/assembly/kg_builder.py` (NEW)

**Objectives**:
1. Accept multiple stores (Neo4j, RDF)
2. Auto-route queries to appropriate store
3. Support dual-write (sync both stores)
4. Health checking
5. Configuration

**Key Class**:
```python
class KGBuilder:
    def __init__(
        self,
        primary_store: GraphStore,
        secondary_store: GraphStore | None = None,
        sync: bool = True
    ):
        self.primary = primary_store
        self.secondary = secondary_store
        self.sync = sync
    
    def build(self, entities, relations) -> KGBuildResult:
        """Build KG in primary store, optionally sync to secondary."""
        result = self.primary.batch_create_nodes(entities)
        if self.secondary and self.sync:
            self.secondary.batch_create_nodes(entities)
        ...
    
    def query(self, query_str: str, store: str = "auto") -> QueryResult:
        """Route query to appropriate store."""
        if store == "auto":
            if query_str.strip().upper().startswith("SELECT"):
                return self.secondary.query(query_str)  # SPARQL
            else:
                return self.primary.query(query_str)    # Cypher
        ...
```

**Status**: ⬜ Not Started (1.5h)

---

### Task 7.4: Update build_kg.py Integration (1h)
**Wire new architecture into pipeline**

**Changes**:
1. Replace SimpleKGAssembler with Neo4jGraphStore
2. Optionally add RDF store
3. Use KGBuilder for orchestration
4. Export results after assembly

**Current Code**:
```python
assembler = SimpleKGAssembler(...)
result = assembler.assemble(entities=..., relations=...)
```

**New Code**:
```python
from kgbuilder.storage import Neo4jGraphStore, create_graph_store
from kgbuilder.assembly.kg_builder import KGBuilder

# Create stores
neo4j_store = Neo4jGraphStore(uri=..., auth=...)
# rdf_store = RDFGraphStore(endpoint=...)  # Optional

# Create orchestrator
builder = KGBuilder(primary_store=neo4j_store)

# Build and export
kg_result = builder.build(entities, relations)

# Export to formats
exporter = KGExporter(neo4j_store)
exporter.export_to_file("output/kg.jsonld", format="jsonld")
exporter.export_to_file("output/kg.ttl", format="turtle")
```

**Status**: ⬜ Not Started (1h)

---

### Task 7.5: Testing & Documentation (1h)
**Comprehensive testing and doc updates**

**Tests**:
- Neo4j store unit tests (mock driver)
- RDF store unit tests (mock SPARQL)
- KGBuilder integration tests
- Multi-store sync tests
- Export format tests

**Documentation**:
- Update MASTER_PLAN.md with Phase 7 completion
- Add Neo4jGraphStore usage examples
- Add RDFGraphStore usage examples
- Add export examples

**Status**: ⬜ Not Started (1h)

---

## Total Estimate: 8 hours

| Task | Hours | Status |
|------|-------|--------|
| 7.1: Neo4j Store | 2.5 | ⬜ |
| 7.2: RDF Store | 2.0 | ⬜ |
| 7.3: KGBuilder | 1.5 | ⬜ |
| 7.4: Integration | 1.0 | ⬜ |
| 7.5: Testing & Docs | 1.0 | ⬜ |
| **Total** | **8** | **⬜** |

---

## Execution Order

1. **Start with 7.1**: Neo4j Store (foundation for everything)
2. **Then 7.2**: RDF Store (parallel capability)
3. **Then 7.3**: KGBuilder (orchestration)
4. **Then 7.4**: Integration (wire into pipeline)
5. **Finally 7.5**: Testing & Docs (quality)

---

## Key Files to Work On

### New Files to Create
- `src/kgbuilder/storage/neo4j_store.py` (2.5h work)
- `src/kgbuilder/assembly/kg_builder.py` (1.5h work)

### Files to Enhance
- `src/kgbuilder/storage/rdf.py` (add full impl)
- `scripts/build_kg.py` (add export, new orchestrator)
- Tests (new test files)

### Files Already Complete
- `src/kgbuilder/storage/protocol.py` ✅
- `src/kgbuilder/storage/export.py` ✅
- `src/kgbuilder/storage/protocol.py::InMemoryGraphStore` ✅

---

## Branch Status

- **Branch**: `feature/phase-7-multi-store` (created)
- **Base**: `main` (latest)
- **Ready to start**: YES ✅

---

**Decision**: Ready to begin Task 7.1 (Neo4j Store Implementation)
