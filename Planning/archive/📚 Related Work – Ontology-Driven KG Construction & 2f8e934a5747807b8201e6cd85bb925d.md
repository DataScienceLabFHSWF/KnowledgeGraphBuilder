# 📚 Related Work – Ontology-Driven KG Construction & GraphRAG

# 

> This page collects open-access (mostly arXiv) research relevant to:
> 
> - Ontology learning & population
> - LLM-based Knowledge Graph construction
> - GraphRAG / KG-augmented RAG
> - Agentic & multi-agent systems
> - Evaluation of KGs and RAG systems

---

## 1. Ontology Learning & Population from Text

### LLMs4OL: Large Language Models for Ontology Learning

**Babaei Giglou et al., 2023**

🔗 https://arxiv.org/abs/2307.16648

- Zero-shot ontology learning with LLMs
- Tasks: term typing, taxonomy induction, relation extraction
- Evaluated across WordNet, GeoNames, UMLS
- Shows LLMs capture taxonomic and relational structure surprisingly well

---

### Ontology Learning with LLMs: A Benchmark Study on Axiom Identification

**Bakker et al., 2025**

🔗 https://arxiv.org/abs/2512.05594

- Introduces **OntoAxiom** benchmark
- Tests LLM ability to identify OWL axioms
- Evaluates subclass, domain, range, disjointness
- Strong relevance for ontology validation & SHACL-style checks

---

### End-to-End Ontology Learning with Large Language Models (OLLM)

**Lo et al., 2024**

🔗 https://arxiv.org/abs/2410.23584

- End-to-end ontology induction instead of pipelined subtasks
- Trains LLMs on entire ontology subgraphs
- Introduces semantic + structural similarity metrics
- Strong reference for ontology-from-text pipelines

---

### A Short Review of Ontology Learning from Text

**Wang et al., 2024**

🔗 https://arxiv.org/abs/2404.14991

- Survey from rule-based → deep learning → LLM-based methods
- Good background & positioning reference
- Discusses evaluation challenges and explainability

---

## 2. LLM-Based Knowledge Graph Construction

### LLM-Empowered Knowledge Graph Construction: A Survey

**Bian et al., 2025**

🔗 https://arxiv.org/abs/2510.20345

- Comprehensive survey of LLMs across the KG pipeline
- Schema-based vs schema-free KG construction
- Covers extraction, linking, fusion, reasoning
- Excellent framing paper for your approach

---

### LLMs for Knowledge Graph Construction and Reasoning

**Zhu et al., 2024**

🔗 https://arxiv.org/abs/2305.13168

- Evaluates LLMs on KG extraction, reasoning, QA
- Introduces **AutoKG** multi-agent framework
- Shows LLMs excel more at reasoning than raw extraction

---

### Ontology-Grounded Automatic KG Construction under Wikidata Schema

**Feng & Miao, 2024**

🔗 https://arxiv.org/abs/2412.20942

- Uses ontology + competency questions to guide KG construction
- Aligns extracted relations to Wikidata schema
- Very close to your ontology-first philosophy

---

### Automated Construction of Theme-Specific Knowledge Graphs (TKGCon)

**Ding et al., 2024**

🔗 https://arxiv.org/abs/2404.19146

- Builds domain KGs from document corpora
- Uses Wikipedia categories as ontology backbone
- LLM proposes candidate relations
- Demonstrates ontology-guided prompting improves precision

---

## 3. GraphRAG & KG-Augmented RAG

### Graph Retrieval-Augmented Generation: A Survey

**Peng et al., 2024**

🔗 https://arxiv.org/abs/2408.08921

- First systematic GraphRAG survey
- Defines indexing, retrieval, and generation stages
- Core reference for GraphRAG architectures

---

### Retrieval-Augmented Generation with Graphs (GraphRAG)

**Han et al., 2025**

🔗 https://arxiv.org/abs/2501.00309

- Formalizes GraphRAG pipeline
- Reviews retrieval, organization, and generation strategies
- Strong design-space overview

---

### From Local to Global: A GraphRAG Approach to Query-Focused Summarization

**Edge et al., 2024**

🔗 https://arxiv.org/abs/2404.16130

- Builds entity KGs from documents
- Uses community detection + summaries
- Improves global reasoning over large corpora

---

### KG²RAG: Knowledge Graph-Guided Retrieval-Augmented Generation

**Zhu et al., 2025**

🔗 https://arxiv.org/abs/2502.06864

- Uses KG-guided chunk expansion
- Combines semantic retrieval + KG traversal
- Improves multi-hop QA (HotpotQA)

---

## 4. Agentic & Multi-Agent Systems

### AutoKG (Multi-Agent KG Construction)

**Zhu et al., 2024**

🔗 https://arxiv.org/abs/2305.13168

- Specialized agents for extraction & reasoning
- Strong reference for agent separation

---

### MA-RAG: Multi-Agent Retrieval-Augmented Generation

**Nguyen et al., 2025**

🔗 https://arxiv.org/abs/2505.20096

- Planner, extractor, QA agents
- Outperforms standard RAG on multi-hop QA
- Shows smaller models benefit strongly from agentic design

---

### RAGulating Compliance: Multi-Agent KG for Regulatory QA

**Agarwal et al., 2025**

🔗

- Important for real-world, incomplete KGs