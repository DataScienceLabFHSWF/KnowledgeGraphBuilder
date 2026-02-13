# C3. KG-RAG QA Agent — Repository Scaffold

**Separate repo**: `kg-rag-agent/` — consumes KGs built by KnowledgeGraphBuilder.

## Directory Tree

```
kg-rag-agent/
├── README.md
├── pyproject.toml                    # → see C3_PYPROJECT.md
├── docker-compose.yml                # Neo4j, Qdrant, Fuseki, Ollama (read-only)
├── .env.example
├── .github/
│   ├── copilot-instructions.md
│   └── workflows/
│       └── ci.yml                    # ruff, mypy, pytest
├── data/
│   ├── competency_questions/         # CQ sets (imported from KGB)
│   │   └── nuclear_decom_cqs.json
│   ├── qa_benchmarks/                # Gold-standard QA datasets
│   │   ├── benchmark_v1.json
│   │   └── README.md
│   └── ontologies/                   # Cached ontology snapshots
│       └── ndd_ontology.ttl
├── scripts/
│   ├── run_qa.py                     # C3.4 — Interactive QA session
│   ├── run_evaluation.py             # C3.5 — Full benchmark evaluation
│   ├── compare_strategies.py         # C3.3 — Compare retrieval strategies
│   └── export_results.py             # Export evaluation results
├── src/
│   └── kgrag/
│       ├── __init__.py
│       ├── core/                     # Shared abstractions
│       │   ├── __init__.py
│       │   ├── config.py             # C3.1 — Pydantic settings
│       │   ├── models.py             # C3.1 — QA data models
│       │   ├── protocols.py          # C3.1 — Retriever/Agent protocols
│       │   └── exceptions.py
│       ├── connectors/               # C3.1 — External service connectors
│       │   ├── __init__.py
│       │   ├── neo4j.py              # Read-only Neo4j client (consumes KGB's graph)
│       │   ├── qdrant.py             # Read-only Qdrant client (consumes KGB's vectors)
│       │   ├── fuseki.py             # Read-only Fuseki client (reads ontology)
│       │   └── ollama.py             # LLM provider for generation
│       ├── retrieval/                # C3.3 — Retrieval strategies
│       │   ├── __init__.py
│       │   ├── vector.py             # C3.3.1 — ClassicRAG: Qdrant-only retrieval
│       │   ├── graph.py              # C3.3.2 — KG-only: entity-centric, subgraph, path
│       │   ├── hybrid.py             # C3.3.3 — FusionRAG: vector + graph + reranking
│       │   ├── ontology.py           # C3.3.4 — Ontology-guided query expansion
│       │   └── reranker.py           # Cross-encoder reranking
│       ├── agents/                   # C3.4 — QA Agent implementations
│       │   ├── __init__.py
│       │   ├── question_parser.py    # C3.4.1 — Decompose complex questions
│       │   ├── context_assembler.py  # C3.4.2 — Merge retrieval contexts
│       │   ├── answer_generator.py   # C3.4.3 — LLM answer generation
│       │   ├── explainer.py          # C3.4.4 — Provenance + reasoning chains
│       │   └── orchestrator.py       # C3.4.5 — Multi-step QA orchestration
│       ├── validation/               # C3.2 — KG validation (read from KGB)
│       │   ├── __init__.py
│       │   ├── shacl.py              # C3.2.1 — SHACL constraint checks
│       │   ├── cq_validator.py       # C3.2.2 — CQ-based KG completeness
│       │   └── consistency.py        # C3.2.3 — Logical consistency checks
│       ├── evaluation/               # C3.5 — End-to-end evaluation
│       │   ├── __init__.py
│       │   ├── qa_dataset.py         # C3.5.1 — QA benchmark dataset loader
│       │   ├── metrics.py            # C3.5.2 — QA metrics (accuracy, F1, faithfulness)
│       │   ├── comparator.py         # C3.5.3 — RAG strategy comparison
│       │   └── reporter.py           # C3.5.4 — Evaluation reports (MD, JSON, HTML)
│       └── api/                      # Optional: REST/WebSocket API
│           ├── __init__.py
│           ├── server.py             # FastAPI server
│           ├── routes.py             # QA endpoints
│           └── schemas.py            # API request/response schemas
└── tests/
    ├── conftest.py                   # Shared fixtures (mock Neo4j, Qdrant, Fuseki)
    ├── core/
    │   └── test_models.py
    ├── retrieval/
    │   ├── test_vector.py
    │   ├── test_graph.py
    │   └── test_hybrid.py
    ├── agents/
    │   ├── test_question_parser.py
    │   ├── test_answer_generator.py
    │   └── test_orchestrator.py
    └── evaluation/
        ├── test_metrics.py
        └── test_comparator.py
```

## Component Mapping to Contributions

| Component | File(s) | Contribution |
|-----------|---------|--------------|
| Pipeline Config + Connectors | `core/config.py`, `connectors/` | **C3.1** Pipeline Architecture |
| SHACL + CQ Validation | `validation/` | **C3.2** KG Validation |
| Vector/Graph/Hybrid Retrieval | `retrieval/` | **C3.3** Retrieval Strategies |
| QA Agents + Explainer | `agents/` | **C3.4** GraphRAG QA Agents |
| Metrics + Comparator + Reporter | `evaluation/` | **C3.5** End-to-End Evaluation |

## Data Flow

```
User Question
    │
    ▼
QuestionParser (C3.4.1)
    │ decomposed sub-questions + entity hints
    ▼
┌─────────────────────────────────────────┐
│         Retrieval Layer (C3.3)          │
│                                         │
│  VectorRetriever ──┐                    │
│  (Qdrant chunks)   │                    │
│                     ├──► FusionRAG ──►  │
│  GraphRetriever ────┘   (hybrid)        │
│  (Neo4j subgraphs)                      │
│                                         │
│  OntologyRetriever                      │
│  (Fuseki: expand types, synonyms)       │
└─────────────────────────────────────────┘
    │ ranked context chunks + subgraphs
    ▼
ContextAssembler (C3.4.2)
    │ unified context with provenance
    ▼
AnswerGenerator (C3.4.3)
    │ LLM-generated answer
    ▼
Explainer (C3.4.4)
    │ answer + reasoning chain + evidence
    ▼
QA Response (with provenance)
```
