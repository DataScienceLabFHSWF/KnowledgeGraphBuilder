# FusionRAG Retrieval Implementation Plan

**Branch**: `feature/fusionrag-retrieval`  
**Release Target**: 0.2.0  
**Status**: Planning

## Overview

FusionRAG (Fusion of Semantic, Vector, and Knowledge Graph RAG) retrieves answers from documents using a hybrid approach:

1. **Vector Retrieval**: Semantic similarity search in Qdrant
2. **Knowledge Graph Retrieval**: Entity/relation queries on Neo4j knowledge graph
3. **Fusion**: Combine and rank results, synthesize answers

Ontology constraints guide extraction and validation.

## Phase 1: Entity & Relation Extraction

### 1.1 Ontology-Guided Entity Extraction
**Task**: Extract entities from chunks using ontology classes as constraints

**Components**:
- `LLMEntityExtractor`: Query LLM with ontology class definitions
  - Input: chunk text + relevant ontology classes
  - LLM task: "Extract entities of these types from the text"
  - Output: `ExtractedEntity(id, label, type, confidence, evidence)`
  - Store in Neo4j as nodes

**Ontology Integration**:
- Query Fuseki for entity class definitions
- Include confidence thresholds from ontology
- Validate extracted types against valid classes

**Implementation Details**:
- Use Ollama (qwen3) for local extraction
- Prompt engineering with ontology examples
- Confidence scoring (0-1)
- Track evidence (chunk ID, position)

### 1.2 Relation Extraction
**Task**: Extract relations between extracted entities

**Components**:
- `LLMRelationExtractor`: Extract subject-predicate-object triples
  - Input: chunk text + extracted entities + valid relations from ontology
  - LLM task: "What relations exist between these entities?"
  - Output: `ExtractedRelation(subject_id, predicate, object_id, confidence)`
  - Store in Neo4j as edges

**Ontology Integration**:
- Query Fuseki for valid relation types
- Validate: subject type → predicate → object type
- Filter invalid triples

### 1.3 Extraction Pipeline
```
For each chunk in Qdrant:
  1. Retrieve chunk vector + text
  2. Extract entities (ontology-guided)
  3. Extract relations between entities (ontology-guided)
  4. Validate against ontology constraints
  5. Store entities & relations in Neo4j
  6. Link to source chunks via provenance
```

**Progress Tracking**:
- Per-chunk extraction metrics (entities found, relations, confidence)
- Aggregated statistics (total nodes, edges, coverage)
- Failed extraction tracking

## Phase 2: Knowledge Graph Assembly

### 2.1 Entity Deduplication
**Task**: Merge duplicate entities across chunks

**Strategy**:
- Name similarity (Levenshtein distance)
- Embedding similarity (reuse document embeddings)
- Type matching (must be same ontology class)
- Merge with confidence threshold

### 2.2 Relation Consolidation
**Task**: Aggregate duplicate relations

**Strategy**:
- Subject + predicate + object match
- Average confidence scores
- Track number of observations
- Keep strongest evidence links

### 2.3 Graph Export
**Task**: Export assembled KG in multiple formats

**Formats**:
- JSON-LD (JSON linked data)
- RDF Turtle (semantic web standard)
- YARRRML (YAML RDF mapping)
- Neo4j native (Cypher queries)

## Phase 3: Hybrid Retrieval

### 3.1 Vector Retrieval
**Task**: Find semantically similar chunks

```python
# Query: user question
query_embedding = ollama.embed(query)
top_chunks = qdrant.search(
    query_embedding,
    collection="kgbuilder",
    limit=5
)
```

### 3.2 Knowledge Graph Retrieval
**Task**: Query KG for entities and relations

```cypher
# Query: user question → extracted entities
MATCH (e:Entity {name: "Kernkraftwerk Emsland"})-[r]->(o)
RETURN e, r, o
```

### 3.3 Semantic Retrieval
**Task**: Combine vector + KG results

**Fusion Strategy**:
- Combine chunk IDs from both approaches
- Rank by relevance score (vector similarity + KG distance)
- Deduplicate
- Return top-K chunks

### 3.4 Answer Synthesis
**Task**: Generate answer from retrieved context

```python
# Use LLM to synthesize answer from chunks
answer = llm.generate(
    prompt=f"Question: {query}\n\nContext: {context}\n\nAnswer:",
    model="qwen3"
)
```

## Implementation Order

1. **Week 1**: Entity extraction pipeline
   - Implement `LLMEntityExtractor`
   - Query Fuseki ontology in extraction prompts
   - Test on sample chunks
   - Store in Neo4j

2. **Week 2**: Relation extraction
   - Implement `LLMRelationExtractor`
   - Validate against ontology relations
   - Link to entities
   - Store in Neo4j

3. **Week 3**: KG assembly
   - Entity deduplication
   - Relation consolidation
   - Export pipeline

4. **Week 4**: Hybrid retrieval
   - Vector retrieval
   - KG retrieval
   - Fusion and ranking
   - Answer synthesis

## Code Structure

```
src/kgbuilder/
├── extraction/
│   ├── entity.py (existing: LLMEntityExtractor)
│   ├── relation.py (existing: LLMRelationExtractor)
│   ├── synthesizer.py (existing: FindingsSynthesizer)
│   └── fusion.py (NEW: ontology-guided extraction)
├── assembly/
│   ├── core.py (existing: graph assembly)
│   └── deduplication.py (NEW: entity/relation merging)
├── retrieval/
│   ├── __init__.py (NEW)
│   ├── vector.py (NEW: vector search)
│   ├── graph.py (NEW: KG queries)
│   ├── fusion.py (NEW: hybrid retrieval)
│   └── synthesizer.py (NEW: answer generation)
└── validation/
    └── ontology_validator.py (NEW: KG validation)
```

## Testing Strategy

- Unit tests for entity/relation extraction
- Integration tests with Fuseki ontology
- End-to-end tests on sample documents
- Benchmark on full 33-document corpus
- Validation against ground truth (if available)

## Metrics to Track

- Extraction precision/recall
- Entity deduplication accuracy
- Relation coverage
- Vector retrieval MAP@5
- KG query performance
- Answer synthesis quality

## Next Steps

1. Create extraction API designs
2. Implement ontology-guided prompts
3. Set up testing infrastructure
4. Begin entity extraction implementation
