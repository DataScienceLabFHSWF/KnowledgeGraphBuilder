# Research Plan: Ontology-Driven Knowledge Graph RAG System

Any nice acronym? 

> Purpose
> 
> 
> Design, implement, and evaluate an ontology-grounded, agentic pipeline that builds Knowledge Graphs (KGs) from documents and leverages them for interpretable GraphRAG-based QA systems.
> 

---

## 🔗 Linked Pages

- 👉 [**[[KG Construction & System Design – Detailed Notes]]**](KG%20Construction%20&%20System%20Design%20%E2%80%93%20Detailed%20Notes%202f8e934a574780f5a674fc92d3986896.md)
- 👉 [**[[Implementation & Related Work]]**](Implementation%20&%20Related%20Work%202f8e934a574780808443e93e594f6996.md)

---

## 0. Research Goal & Scope

### Goal

Build an end-to-end system that:

- Constructs a **validated Knowledge Graph** from unstructured documents
- Grounds KG construction in **ontology & competency questions**
- Uses the KG for **GraphRAG / QA agents**
- Evaluates quality, performance, and interpretability

### Core Research Questions

- How can ontologies guide reliable KG construction from text?
- How does KG-augmented RAG compare to classic RAG?
- How can we evaluate and explain agentic, graph-based QA systems?

### Candidate Domains

- **Industrial problem solving**
- Example: **8D Problem Solving**
    
    [https://en.wikipedia.org/wiki/Eight_disciplines_problem_solving](https://en.wikipedia.org/wiki/Eight_disciplines_problem_solving)
    

---

## 1. Ontology Selection & Design

### 1.1 Ontology Strategy

- ☐ Reuse existing ontology
- ☐ Extend existing ontology
- ☐ Design new ontology

**Decision Criteria**

- Domain coverage
- Formal semantics (OWL/RDF)
- Availability of constraints
- Existing competency questions
- Community adoption

### 1.2 Ontology Artifacts

- Classes
- Relations
- Constraints
- Competency Questions (CQs)

**Outputs**

- Ontology file (OWL/RDF)
- Versioned CQ list

---

## 2. Data Collection & Indexing

### 2.1 Data Sources

- Academic papers
- Industrial documentation
- Manuals / SOPs
- Reports
- Web content (optional)

### 2.2 Data Preparation

- Chunking strategy
- Metadata preservation
    - Source
    - Section
    - Timestamp
    - Confidence

### 2.3 Indexing

- Vector index for **classic RAG**
- This index will be **reused for KG construction**

---

## 3. Knowledge Graph Construction (Overview)

> Key Design Principle
> 
> 
> KG construction never reads raw documents directly.
> 
> It consumes **structured research findings** produced by a DeepResearch Agent.
> 

### 3.1 Evidence Sources

- Indexed document corpus (primary)
- Optional web search (controlled, logged)

### 3.2 Agentic Construction Strategy

- Ontology-guided research
- Layered entity extraction
- Iterative refinement
- Provenance-aware graph assembly

👉 **Details in [[[KG Construction & System Design – Detailed Notes]]](KG%20Construction%20&%20System%20Design%20%E2%80%93%20Detailed%20Notes%202f8e934a574780f5a674fc92d3986896.md)**

---

## 4. KG Validation

### Validation Techniques

- SHACL constraints
- Ontology reasoning
- Competency Question answering

### Validation Metrics

- Constraint violation rate
- CQ coverage
- Entity consistency

---

## 5. GraphRAG & QA Agents

### 5.1 QA Architectures

- Classic RAG (baseline)
- KG-augmented RAG
- Subgraph retrieval
- Path-based reasoning
- Multi-agent QA

### 5.2 Retrieval Strategies

- Entity-centric retrieval
- Subgraph expansion
- Hybrid vector + graph

---

## 6. Evaluation (End-to-End)

### 6.1 QA Evaluation

- Domain-specific question set
- Ground truth answers
- Failure analysis

### 6.2 RAG Metrics

- deepeval
- Faithfulness
- Relevance
- Answer completeness

### 6.3 Manual Evaluation

- Expert review
- Error taxonomy

### 6.4 Graph-Based Metrics

- Centrality
- Communities
- Density
- Motifs

### 6.5 Embeddings & Representation Analysis

- Semantic embeddings (LLM)
- Graph embeddings (GraphSAGE)
- Structural vs semantic comparison
- Community alignment

---

## 7. Interpretability & UX

### 7.1 User Interface

- Graph exploration UI
- Entity & relation inspection
- Filtering & search

### 7.2 Explainable QA

- Show retrieved subgraph
- Clickable source links
- Reasoning traces

---

## 8. Agent Design & Orchestration

### Agent Roles

- Question-Asking Agent
- DeepResearch Agent
- KG Builder Agent
- Validation Agent
- QA Agent
- Evaluation Agent

### Question Design

- Derived from competency questions
- Logged & versioned
- Adaptive generation

---

## 9. Engineering & Project Planning

### LLM Strategy

- Small models for development
- Large models for final runs
- Open-source vs closed trade-offs

### Software Architecture

- Modular services
- Agent orchestration
- Shared storage (KG, vectors, logs)

### Repo Structure

```
/agents
/ontology
/kg
/research
/evaluation
/frontend
/docs

```

### Standards

- Documentation templates
- Code style guide
- Shared Copilot instruction file

---

## 10. Expected Contributions

- Ontology-guided KG construction pipeline
- Evidence-grounded GraphRAG architecture
- Evaluation framework for KG-augmented QA
- Interpretability mechanisms for RAG systems

[**KG Construction & System Design – Detailed Notes**](KG%20Construction%20&%20System%20Design%20%E2%80%93%20Detailed%20Notes%202f8e934a574780f5a674fc92d3986896.md)

[**Implementation & Related Work**](Implementation%20&%20Related%20Work%202f8e934a574780808443e93e594f6996.md)

[📚 Related Work – Ontology-Driven KG Construction & GraphRAG](%F0%9F%93%9A%20Related%20Work%20%E2%80%93%20Ontology-Driven%20KG%20Construction%20&%202f8e934a5747807b8201e6cd85bb925d.md)

[bibtex](bibtex%202f8e934a5747806fbdabd230e01ee0ba.md)