# C3. KG-RAG QA Agent — Workflow & Pipeline

End-to-end flow from user question to evaluated answer, mapping each phase to a contribution.

---

## 1. QA Pipeline Flow (C3.1 + C3.4)

```
┌──────────────────────────────────────────────────────────────────┐
│                        QA Pipeline                                │
│                                                                   │
│  ┌─────────────┐   ┌──────────────┐   ┌───────────────────┐     │
│  │  1. Parse    │──►│ 2. Expand    │──►│ 3. Retrieve       │     │
│  │  Question    │   │ (Ontology)   │   │ (Vector+Graph)    │     │
│  │  (C3.4.1)   │   │ (C3.3.4)     │   │ (C3.3.1–C3.3.3)  │     │
│  └─────────────┘   └──────────────┘   └────────┬──────────┘     │
│                                                  │                │
│  ┌─────────────┐   ┌──────────────┐   ┌────────▼──────────┐     │
│  │  6. Return   │◄──│ 5. Explain   │◄──│ 4. Generate       │     │
│  │  Answer      │   │ (Provenance) │   │ Answer            │     │
│  │              │   │ (C3.4.4)     │   │ (C3.4.3)          │     │
│  └─────────────┘   └──────────────┘   └───────────────────┘     │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### Phase 1: Parse Question (C3.4.1)

```python
# scripts/run_qa.py (simplified)
query = question_parser.parse(raw_question)
# → QAQuery(
#     raw_question="Welche Rückbauverfahren werden bei Reaktor A eingesetzt?",
#     question_type=QuestionType.LIST,
#     detected_entities=["Reaktor A"],
#     detected_types=["NuclearFacility"],
#     language="de"
#   )
```

**Implementation**: LLM call with structured output to classify question type,
extract entity mentions, and decompose complex questions into sub-questions.

### Phase 2: Ontology Expansion (C3.3.4)

```python
expanded_query = ontology_retriever.expand_query(query)
# → detected_types now includes parent classes + synonyms
# → expected_relations populated from ontology (e.g., ["usesMethod", "hasComponent"])
```

### Phase 3: Retrieve (C3.3.1–C3.3.3)

```python
# Parallel retrieval
vector_ctx, graph_ctx = await asyncio.gather(
    vector_retriever.retrieve(expanded_query),
    graph_retriever.retrieve(expanded_query),
)
# Fusion + reranking
contexts = hybrid_retriever.fuse_and_rerank(vector_ctx, graph_ctx, expanded_query)
```

### Phase 4: Generate Answer (C3.4.3)

```python
answer = await answer_generator.generate(
    query=expanded_query,
    contexts=contexts,  # top-k reranked contexts
)
```

**Prompt structure**:
```
You are a QA agent for nuclear decommissioning knowledge.
Answer the question using ONLY the provided context.
Cite your sources using [Entity:ID] or [Doc:chunk_id] markers.

Context:
{serialized contexts with source labels}

Question: {query.raw_question}

Answer (in {query.language}):
```

### Phase 5: Explain (C3.4.4)

```python
explained_answer = explainer.add_provenance(
    answer=answer,
    contexts=contexts,
    query=expanded_query,
)
# → answer.reasoning_chain populated
# → answer.cited_entities populated
# → answer.subgraph_json populated (for visualization)
```

### Phase 6: Return

```python
# QAAnswer with:
# - answer_text: "Für Reaktor A werden folgende Rückbauverfahren eingesetzt: ..."
# - confidence: 0.85
# - reasoning_chain: ["Found Reaktor A in KG", "Traversed usesMethod relations", ...]
# - evidence: [RetrievedContext(...), ...]
# - cited_entities: [KGEntity("Reaktor A"), KGEntity("Verfahren X"), ...]
# - subgraph_json: { "nodes": [...], "edges": [...] }
```

---

## 2. Evaluation Workflow (C3.5)

```
┌──────────────────────────────────────────────────────────┐
│                  Evaluation Pipeline                      │
│                                                           │
│  Load QA           Run each           Compute            │
│  Benchmark  ──►    Strategy    ──►    Metrics    ──►     │
│  (C3.5.1)          (C3.3 × N)         (C3.5.2)          │
│                                                           │
│                    Compare            Generate            │
│               ──►  Strategies  ──►    Report             │
│                    (C3.5.3)           (C3.5.4)            │
└──────────────────────────────────────────────────────────┘
```

### Step 1: Load Benchmark

```python
# scripts/run_evaluation.py
dataset = QADataset.load("data/qa_benchmarks/benchmark_v1.json")
strategies = ["vector_only", "graph_only", "hybrid"]
```

### Step 2: Run Strategies

```python
for strategy_name in strategies:
    retriever = build_retriever(strategy_name, config)
    for item in dataset:
        query = question_parser.parse(item.question)
        contexts = await retriever.retrieve(query)
        answer = await answer_generator.generate(query, contexts)
        results.append(QAEvalResult(
            question_id=item.question_id,
            predicted_answer=answer.answer_text,
            expected_answer=item.expected_answer,
            retrieval_strategy=strategy_name,
            latency_ms=answer.latency_ms,
            context_count=len(contexts),
        ))
```

### Step 3: Compute Metrics

```python
for result in results:
    result.f1_score = compute_token_f1(result.predicted_answer, result.expected_answer)
    result.exact_match = normalize(result.predicted) == normalize(result.expected)
    result.faithfulness = compute_faithfulness(result.predicted_answer, contexts)
    result.relevance = compute_context_relevance(query, contexts)
```

**Key Metrics** (C3.5.2):

| Metric | Formula | Purpose |
|--------|---------|---------|
| Token F1 | Harmonic mean of precision/recall on token overlap | Answer quality |
| Exact Match | Normalized string equality | Strict correctness |
| Faithfulness | % of answer claims grounded in retrieved context | Hallucination detection |
| Context Relevance | Avg similarity(question, context_i) | Retrieval quality |
| Answer Relevance | similarity(question, answer) | Question-answer alignment |
| Latency | Wall-clock ms per question | Practical usability |

### Step 4: Compare Strategies (C3.5.3)

```python
comparisons = comparator.compare(results, group_by="retrieval_strategy")
# → list[StrategyComparison]
#   StrategyComparison("hybrid", avg_f1=0.78, avg_faithfulness=0.91, ...)
#   StrategyComparison("vector_only", avg_f1=0.62, avg_faithfulness=0.84, ...)
#   StrategyComparison("graph_only", avg_f1=0.71, avg_faithfulness=0.88, ...)
```

### Step 5: Generate Report

```python
reporter.generate(
    comparisons=comparisons,
    output_dir="reports/eval_v1/",
    formats=["json", "markdown", "html"],
)
```

**Report includes**:
- Per-strategy summary table (avg metrics)
- Per-question-type breakdown (factoid vs causal vs list etc.)
- Statistical significance tests (paired t-test / bootstrap)
- Confusion matrix: which questions each strategy gets right/wrong
- Latency distribution plots
- Best strategy per question type recommendation

---

## 3. CQ Validation Workflow (C3.2)

```python
# scripts/validate_kg.py

cqs = load_competency_questions("data/competency_questions/nuclear_decom_cqs.json")

for cq in cqs:
    # 1. Try to answer CQ using the QA pipeline
    answer = await pipeline.answer(cq.text)
    
    # 2. If CQ has SPARQL template, also check KG directly
    if cq.sparql_template:
        sparql_result = fuseki.query(cq.sparql_template)
        cq_satisfied = len(sparql_result) > 0
    
    # 3. Log coverage
    logger.info("cq_validation", cq_id=cq.question_id, 
                answered=answer.confidence > 0.5, sparql_ok=cq_satisfied)
```

**Output**: CQ coverage report showing which competency questions the KG can answer.

---

## 4. Scripts Overview

| Script | Purpose | Contribution |
|--------|---------|--------------|
| `scripts/run_qa.py` | Interactive QA session (REPL or single question) | C3.4 |
| `scripts/run_evaluation.py` | Full benchmark evaluation across strategies | C3.5 |
| `scripts/compare_strategies.py` | Head-to-head strategy comparison | C3.3 + C3.5 |
| `scripts/validate_kg.py` | CQ-based KG completeness validation | C3.2 |
| `scripts/export_results.py` | Export results to JSON/CSV/LaTeX for thesis | C3.5 |

---

## 5. Docker Compose (read-only services)

The QA agent connects to the **same infrastructure** as KGB, but read-only:

```yaml
# docker-compose.yml (kg-rag-agent)
services:
  qa-agent:
    build: .
    environment:
      KGRAG_NEO4J__URI: bolt://neo4j:7687
      KGRAG_QDRANT__URL: http://qdrant:6333
      KGRAG_FUSEKI__URL: http://fuseki:3030
      KGRAG_OLLAMA__BASE_URL: http://ollama:11434
    ports:
      - "8080:8080"   # FastAPI
    depends_on:
      - neo4j
      - qdrant
      - fuseki
    # No volumes needed — all data read from external services

  # These services are shared with KGB (or use external:true)
  neo4j:
    image: neo4j:5-community
    # ... same config as KGB
  qdrant:
    image: qdrant/qdrant:latest
  fuseki:
    image: stain/jena-fuseki
  ollama:
    image: ollama/ollama
```

Or use Docker Compose `external_links` / shared network to connect to KGB's running services.

---

## 6. Implementation Order

| Phase | What | Files | Est. Effort |
|-------|------|-------|-------------|
| **0** | Scaffold repo, pyproject, configs | Root + `core/` | 1 day |
| **1** | Connectors (Neo4j, Qdrant, Fuseki, Ollama) | `connectors/` | 2 days |
| **2** | VectorRetriever (baseline) | `retrieval/vector.py` | 1 day |
| **3** | GraphRetriever (entity-centric) | `retrieval/graph.py` | 2 days |
| **4** | Entity linker | `retrieval/entity_linker.py` | 1 day |
| **5** | HybridRetriever + RRF | `retrieval/hybrid.py` | 2 days |
| **6** | OntologyRetriever (expansion) | `retrieval/ontology.py` | 1 day |
| **7** | CrossEncoder reranker | `retrieval/reranker.py` | 0.5 day |
| **8** | QuestionParser + AnswerGenerator | `agents/` | 2 days |
| **9** | Explainer (provenance) | `agents/explainer.py` | 1 day |
| **10** | Orchestrator (full pipeline) | `agents/orchestrator.py` | 1 day |
| **11** | Evaluation metrics + dataset | `evaluation/` | 2 days |
| **12** | Strategy comparator + reporter | `evaluation/comparator.py` | 2 days |
| **13** | CQ validation | `validation/` | 1 day |
| **14** | FastAPI endpoints | `api/` | 1 day |
| | | **Total** | **~20 days** |
