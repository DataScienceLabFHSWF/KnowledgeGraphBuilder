# Ontology-Driven Knowledge Graph Construction for RAG

## Academic Overview & Research Motivation

**Project**: KnowledgeGraphBuilder  
**Domain**: Nuclear Decommissioning (design is domain-agnostic)  
**Language**: Python 3.11+  
**Last Updated**: February 6, 2026

---

## 1. Motivation

Large Language Models excel at text generation but struggle with factual grounding, domain-specific reasoning, and traceable answers. Knowledge Graphs (KGs) provide structured, validated knowledge representations that complement LLMs by enabling:

- **Factual grounding** — answers backed by explicit triples and provenance
- **Ontology conformance** — extraction guided by domain-specific schemas (OWL)
- **Iterative refinement** — KG quality improves through multi-pass discovery
- **Explainability** — reasoning chains can be traced through the graph

This project investigates how **ontology-guided KG construction** can be combined with **Retrieval-Augmented Generation** (RAG) to produce high-quality, validated, and interpretable question-answering systems.

---

## 2. Core Research Questions

1. **RQ1**: How can ontologies guide reliable KG construction from unstructured text?
   - How does ontology guidance impact quality and coverage vs. schema-free extraction?
   - What role do competency questions (CQs) play in directing discovery?

2. **RQ2**: How does KG-augmented RAG compare to classic vector-based RAG?
   - What are the trade-offs between classic, hybrid, and KG-only RAG architectures?
   - When does graph structure improve retrieval over pure embedding similarity?

3. **RQ3**: How can we evaluate and explain agentic, graph-based QA systems?
   - How do different ontology/CQ versions affect KG structure and downstream QA performance?
   - What metrics best capture KG quality for RAG applications?

4. **RQ4**: How can we systematically track, compare, and reproduce KG building experiments for academic evaluation?

---

## 3. Research Approach

### 3.1 Ontology Selection & Design

- Reuse or extend existing OWL ontology for the target domain
- Define competency questions (CQs) — natural-language questions the KG must answer
- CQs drive the iterative discovery loop: each CQ generates targeted extraction queries

### 3.2 Data Collection & Indexing

- Ingest unstructured documents (PDF, DOCX, PPTX, TXT, Markdown)
- Chunk, embed, and index into a vector store (Qdrant)
- The KG pipeline consumes chunks via retrieval, never reads raw documents directly

### 3.3 KG Construction Pipeline

An iterative, ontology-guided pipeline:

1. **Ontology Processing** — Load OWL classes, properties, relations from Fuseki
2. **Question Generation** — Derive discovery questions from ontology classes and CQs
3. **Iterative Discovery** — For each question: retrieve relevant chunks → extract entities/relations → synthesize findings
4. **Entity Synthesis** — Deduplicate, merge, resolve entities across documents
5. **Relation Extraction** — Extract typed relations with domain/range constraints
6. **KG Assembly** — Build validated graph in Neo4j + RDF stores
7. **Validation** — SHACL constraints, semantic rules, consistency checking

### 3.4 Evaluation Strategy

- **QA Evaluation**: Benchmark questions answered against the KG (accuracy, F1, coverage)
- **RAG Comparison**: Classic RAG vs. KG-augmented RAG vs. hybrid approaches
- **Graph Metrics**: Density, connectedness, ontology coverage, CQ answerability
- **Ablation Studies**: With/without ontology guidance, different extraction models, CQ variants

---

## 4. Expected Contributions

1. **Ontology-guided KG construction pipeline** — Iterative, confidence-scored, evidence-grounded extraction from unstructured documents
2. **Evidence-grounded GraphRAG architecture** — Combining structured KG traversal with vector retrieval for QA
3. **Evaluation framework** — Systematic metrics for KG quality, RAG performance, and experiment reproducibility
4. **Interpretability mechanisms** — Traceable reasoning through graph subgraphs, provenance chains, and CQ coverage

---

## 5. Related Work

### 5.1 Ontology Learning & Population

| Paper | Key Contribution | Relevance |
|-------|-----------------|-----------|
| LLMs4OL (Babaei Giglou et al., 2023) | Zero-shot ontology learning: term typing, taxonomy induction, relation extraction | Baseline for LLM ontology capabilities |
| OntoAxiom (Bakker et al., 2025) | Benchmark for OWL axiom identification by LLMs | Evaluating ontology quality with LLMs |
| OLLM (Lo et al., 2024) | End-to-end ontology induction with semantic+structural metrics | Alternative approach: LLM builds ontology itself |
| Ontology Learning Review (Wang et al., 2024) | Survey of rule-based → DL → LLM methods | Historical context and method comparison |

### 5.2 LLM-Based KG Construction

| Paper | Key Contribution | Relevance |
|-------|-----------------|-----------|
| LLM-Empowered KG Survey (Bian et al., 2025) | Comprehensive survey: schema-based vs schema-free, extraction/linking/fusion/reasoning | Positions our work in the field |
| AutoKG (Zhu et al., 2024) | Multi-agent framework; LLMs better at reasoning than extraction | Validates agent-based KG construction |
| Ontology-Grounded KG (Feng & Miao, 2024) | Ontology + CQs guide construction, Wikidata alignment | Closest to our approach |
| TKGCon (Ding et al., 2024) | Theme-specific KGs, Wikipedia categories as ontology backbone | Alternative ontology sourcing strategy |

### 5.3 GraphRAG & KG-Augmented Retrieval

| Paper | Key Contribution | Relevance |
|-------|-----------------|-----------|
| GraphRAG Survey (Peng et al., 2024) | First systematic survey: indexing/retrieval/generation stages | Taxonomy for our RAG design |
| Local-to-Global GraphRAG (Edge et al., 2024) | Entity KGs + community detection + hierarchical summaries | Key architectural influence |
| KG²RAG (Zhu et al., 2025) | KG-guided chunk expansion for multi-hop QA | Hybrid retrieval strategy |

### 5.4 Multi-Agent Systems

| Paper | Key Contribution | Relevance |
|-------|-----------------|-----------|
| MA-RAG (Nguyen et al., 2025) | Planner/extractor/QA agents; smaller models benefit from agentic design | Agent orchestration patterns |
| RAGulating Compliance (Agarwal et al., 2025) | Multi-Agent KG for regulatory QA, real-world incomplete KGs | Industrial application pattern |

---

## 6. Bibliography

```bibtex
@article{babaei2023llms4ol,
  title={LLMs4OL: Large Language Models for Ontology Learning},
  author={Babaei Giglou, H. and others},
  journal={arXiv preprint arXiv:2307.16648},
  year={2023}
}

@article{bakker2025ontoaxiom,
  title={Ontology Learning with LLMs: A Benchmark Study on Axiom Identification},
  author={Bakker, R. and others},
  journal={arXiv preprint arXiv:2512.05594},
  year={2025}
}

@article{lo2024ollm,
  title={End-to-End Ontology Learning with Large Language Models},
  author={Lo, A. and others},
  journal={arXiv preprint arXiv:2410.23584},
  year={2024}
}

@article{wang2024ontologyreview,
  title={A Short Review for Ontology Learning from Text},
  author={Wang, Y. and others},
  journal={arXiv preprint arXiv:2404.14991},
  year={2024}
}

@article{bian2025llmkg,
  title={LLM-Empowered Knowledge Graph Construction: A Survey},
  author={Bian, H. and others},
  journal={arXiv preprint arXiv:2510.20345},
  year={2025}
}

@article{zhu2024autokg,
  title={LLMs for Knowledge Graph Construction and Reasoning},
  author={Zhu, Y. and others},
  journal={arXiv preprint arXiv:2305.13168},
  year={2024}
}

@article{feng2024ontologykg,
  title={Ontology-Grounded Automatic KG Construction under Wikidata Schema},
  author={Feng, X. and Miao, S.},
  journal={arXiv preprint arXiv:2412.20942},
  year={2024}
}

@article{ding2024tkgcon,
  title={Automated Construction of Theme-Specific Knowledge Graphs},
  author={Ding, F. and others},
  journal={arXiv preprint arXiv:2404.19146},
  year={2024}
}

@article{peng2024graphrag,
  title={Graph Retrieval-Augmented Generation: A Survey},
  author={Peng, B. and others},
  journal={arXiv preprint arXiv:2408.08921},
  year={2024}
}

@article{edge2024localglobal,
  title={From Local to Global: A GraphRAG Approach to Query-Focused Summarization},
  author={Edge, D. and others},
  journal={arXiv preprint arXiv:2404.16130},
  year={2024}
}

@article{nguyen2025marag,
  title={MA-RAG: Multi-Agent Retrieval-Augmented Generation},
  author={Nguyen, T. and others},
  journal={arXiv preprint arXiv:2505.20096},
  year={2025}
}

@article{yu2024rageval,
  title={Evaluation of Retrieval-Augmented Generation: A Survey},
  author={Yu, H. and others},
  journal={arXiv preprint arXiv:2405.07437},
  year={2024}
}
```
