# Phase 12: Semantic Enhancement & Analytics Plan

This document outlines the implementation strategy for Phase 12, focusing on adding automated reasoning, recursive taxonomies, and graph-based insights to the Knowledge Graph.

## 1. Objectives
- **OWL-RL Inference**: Materialize inferred relations based on ontology axioms (Transitivity, Symmetry, InverseOf, SubClassOf).
- **SKOS Taxonomy Enrichment**: Map entities to a hierarchy of concepts using SKOS (broader/narrower/related).
- **Embedding-based Discovery**: Use vector similarity to propose missing relations between entities.
- **Graph Analytics**: Calculate centrality, connectivity, and importance metrics (PageRank, Betweenness).

## 2. Component Architecture

### 2.1 Inference Engine (`src/kgbuilder/analytics/inference.py`)
- `OntologyReasoner`: Applies OWL-RL rules to the Neo4j/RDF store.
- Supports materialization (write-back) of inferred edges.

### 2.2 SKOS Service (`src/kgbuilder/analytics/skos.py`)
- `SKOSEnricher`: Queries external or internal SKOS vocabularies to identify broader/narrower concepts.
- Integrates with the `EnrichmentPipeline`.

### 2.3 Graph Metrics (`src/kgbuilder/analytics/metrics.py`)
- Wrappers for Neo4j Graph Data Science (GDS) or NetworkX for basic connectivity stats.

## 3. Implementation Roadmap

### Task 1: Basic Ontology Inference (SubClassOf/SubPropertyOf)
- Materialize transitive closures of `subClassOf` and `subPropertyOf`.
- Ensure `is-a` chains are complete in Neo4j.

### Task 2: Symmetry & Inversion
- Identify symmetric properties in OWL and create bidirectional edges.
- Identify inverse properties and create the corresponding inverse edges.

### Task 3: SKOS Integration
- Map entity labels to SKOS concepts using `prefLabel` and `altLabel`.
- Add `broader` relations to the graph to create a shallow taxonomy.

### Task 4: Embedding-based Link Prediction
- Identify entity pairs with high cosine similarity but no direct relation.
- Use LLM to verify if a relation should exist (Human-in-the-loop or high-confidence automated).

## 4. Neo4j GDS Integration
- If Neo4j GDS is available, implement wrappers for:
  - `gds.pageRank.stream`
  - `gds.louvain.stream` (Community detection)
