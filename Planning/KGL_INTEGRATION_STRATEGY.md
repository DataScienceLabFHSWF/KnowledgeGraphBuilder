# KGL (kglab) Integration Strategy

## Overview

**Project Role**: Post-Processing & Analytics (Phase 11+)
**Library**: `kglab` (https://derwen.ai/docs/kgl/)
**Purpose**: Graph analytics, semantic inference, SKOS expansion, and validation.

**Note**: KGL is **NOT** used for the core Extraction Pipeline (Phase 1-6). It is an integration layer for analytics.

---

## 1. Why KGL for this Project?

We already use `rdflib` for RDF handling and `neo4j` for property graphs. KGL adds an abstraction layer that bridges these two worlds and adds powerful analytics capabilities that would otherwise require custom implementation.

| Feature | Without KGL | With KGL |
| :--- | :--- | :--- |
| **Graph Exchange** | Manual RDF<->Property Graph conversion | `kglab` provides seamless morphing between RDF (SKOS/OWL) and Neo4j |
| **Inference** | Requires OWL-RL engine setup | Built-in OWL-RL reasoning on in-memory graphs |
| **Graph Metrics** | Custom Cypher queries | `kglab` calculates centrality, PageRank, etc. on the fly |
| **Visualization** | Requires external tools | Interactive PyVis visualizations out-of-the-box |

## 2. Integration Points

### A. Semantic Validation (OWL-RL)
After the KG is built, we use KGL to run inference rules defined in `ont.owl`. This materializes implicit relationships that the LLM might have missed but are logically implied by the ontology.

```python
import kglab

def apply_inference(rdf_file: str):
    kg = kglab.KnowledgeGraph()
    kg.load_rdf(rdf_file)
    
    # Materialize triples based on OWL rules
    kg.materialize("rdfs")
    kg.materialize("owlrl")
    
    return kg
```

### B. SKOS Taxonomy Expansion
Our ontology uses SKOS for concept hierarchies. KGL has native SKOS support to expand broader/narrower concepts, allowing our RAG retrieval to search for "Vehicles" and automatically include "Trucks" and "Cars".

### C. Graph Analytics
We use KGL to identify the most critical nodes in our extracted graph (Entities referenced by many Decommissioning Plans).

```python
measure = kglab.Measure()
key_nodes = measure.pagerank(kg)
```

## 3. Implementation Status

- [ ] **Phase 1-10**: Core Extraction Pipeline (Current Focus) - Uses `rdflib` directly.
- [ ] **Phase 11**: Semantic Enrichment - Will use KGL for OWL-RL inference.
- [ ] **Phase 12**: Analytics Dashboard - Will use KGL + PyVis.

## 4. Dependencies
Adding `kglab` to `requirements.txt`:
```
kglab>=0.6.0
owlrl
```
