# C3. KG-RAG QA Agent — Core Models

Data models for the QA agent. These consume KGB's outputs and define the QA domain.

---

## 1. Consumed from KnowledgeGraphBuilder (read-only)

These types exist in KGB's Neo4j/Qdrant/Fuseki — the QA agent reads them via connectors.
The agent defines **lightweight mirror types** (not imports) to stay decoupled.

```python
# kgrag/core/models.py

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# --- Mirrors of KGB data (read from Neo4j / Qdrant) ---

@dataclass
class KGEntity:
    """Entity node read from Neo4j."""
    id: str
    label: str
    entity_type: str            # Ontology class URI
    properties: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    source_doc_ids: list[str] = field(default_factory=list)


@dataclass
class KGRelation:
    """Relation edge read from Neo4j."""
    id: str
    source_id: str
    target_id: str
    relation_type: str          # Ontology property URI
    properties: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    evidence_text: str = ""


@dataclass
class DocumentChunk:
    """Chunk read from Qdrant (payload)."""
    chunk_id: str
    document_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None  # populated on retrieval


@dataclass
class OntologyClass:
    """Ontology class read from Fuseki."""
    uri: str
    label: str
    parent_uri: str | None = None
    properties: list[OntologyProperty] = field(default_factory=list)
    description: str = ""


@dataclass
class OntologyProperty:
    """Ontology property read from Fuseki."""
    uri: str
    label: str
    domain_uri: str
    range_uri: str
    property_type: str = "object"  # "object" | "datatype"
```

---

## 2. QA Domain Models (new)

```python
# --- Question & Answer domain ---

class QuestionType(Enum):
    FACTOID = "factoid"             # Single fact: "What is X?"
    LIST = "list"                   # Enumeration: "Which Ys are in Z?"
    BOOLEAN = "boolean"             # Yes/No: "Does X relate to Y?"
    COMPARATIVE = "comparative"     # Compare: "How does X differ from Y?"
    CAUSAL = "causal"              # Explain: "Why was X decommissioned?"
    AGGREGATION = "aggregation"     # Count/sum: "How many components..."


@dataclass
class QAQuery:
    """Parsed user question."""
    raw_question: str
    question_type: QuestionType | None = None
    detected_entities: list[str] = field(default_factory=list)
    detected_types: list[str] = field(default_factory=list)     # Ontology classes
    sub_questions: list[str] = field(default_factory=list)       # Decomposed parts
    language: str = "de"                                         # Default German


@dataclass
class RetrievedContext:
    """Single piece of retrieved evidence."""
    source: RetrievalSource
    text: str
    score: float = 0.0
    chunk: DocumentChunk | None = None
    subgraph: list[KGEntity | KGRelation] | None = None
    provenance: Provenance | None = None


class RetrievalSource(Enum):
    VECTOR = "vector"       # From Qdrant
    GRAPH = "graph"         # From Neo4j subgraph
    HYBRID = "hybrid"       # Fused vector + graph
    ONTOLOGY = "ontology"   # Ontology-expanded


@dataclass
class Provenance:
    """Tracks where evidence came from."""
    document_id: str | None = None
    chunk_id: str | None = None
    entity_ids: list[str] = field(default_factory=list)
    relation_ids: list[str] = field(default_factory=list)
    retrieval_strategy: str = ""
    retrieval_score: float = 0.0


@dataclass
class QAAnswer:
    """Final answer with full provenance."""
    question: str
    answer_text: str
    confidence: float = 0.0
    reasoning_chain: list[str] = field(default_factory=list)    # Step-by-step reasoning
    evidence: list[RetrievedContext] = field(default_factory=list)
    cited_entities: list[KGEntity] = field(default_factory=list)
    cited_relations: list[KGRelation] = field(default_factory=list)
    subgraph_json: dict[str, Any] | None = None                 # Visualizable subgraph
    latency_ms: float = 0.0
```

---

## 3. Evaluation Models

```python
# --- Evaluation ---

@dataclass
class QABenchmarkItem:
    """Single item from a gold-standard QA benchmark."""
    question_id: str
    question: str
    expected_answer: str
    expected_entities: list[str] = field(default_factory=list)
    difficulty: str = "medium"      # easy | medium | hard
    question_type: str = "factoid"
    competency_question_id: str | None = None   # Link to CQ


@dataclass
class QAEvalResult:
    """Evaluation result for a single question."""
    question_id: str
    predicted_answer: str
    expected_answer: str
    exact_match: bool = False
    f1_score: float = 0.0
    faithfulness: float = 0.0       # How much is grounded in evidence?
    relevance: float = 0.0          # How relevant is the context?
    latency_ms: float = 0.0
    retrieval_strategy: str = ""
    context_count: int = 0


@dataclass
class StrategyComparison:
    """Comparison of retrieval strategies across benchmark."""
    strategy_name: str              # "vector_only", "graph_only", "hybrid", etc.
    avg_f1: float = 0.0
    avg_faithfulness: float = 0.0
    avg_relevance: float = 0.0
    avg_latency_ms: float = 0.0
    exact_match_rate: float = 0.0
    num_questions: int = 0
    per_type_f1: dict[str, float] = field(default_factory=dict)  # By QuestionType
```

---

## 4. Competency Question Models

```python
# --- Competency Questions ---

@dataclass
class CompetencyQuestion:
    """CQ imported from KGB ontology design."""
    question_id: str            # e.g. "CQ-01"
    text: str                   # Natural language question
    entity_class: str           # Primary ontology class
    priority: str               # "must" | "should" | "could"
    aspect: str                 # "existence" | "relationship" | "attribute" | ...
    sparql_template: str = ""   # Optional SPARQL to verify answerability
```

---

## 5. Configuration Models

```python
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class Neo4jConfig(BaseModel):
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = "password"
    database: str = "neo4j"


class QdrantConfig(BaseModel):
    url: str = "http://localhost:6333"
    collection_name: str = "document_chunks"


class FusekiConfig(BaseModel):
    url: str = "http://localhost:3030"
    dataset: str = "ontology"


class OllamaConfig(BaseModel):
    base_url: str = "http://localhost:11434"
    generation_model: str = "qwen3:8b"
    embedding_model: str = "qwen3-embedding:latest"
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)


class RetrievalConfig(BaseModel):
    vector_top_k: int = 10
    graph_max_hops: int = 2
    graph_max_nodes: int = 50
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    fusion_weights: dict[str, float] = Field(
        default_factory=lambda: {"vector": 0.4, "graph": 0.4, "ontology": 0.2}
    )


class EvaluationConfig(BaseModel):
    benchmark_path: str = "data/qa_benchmarks/benchmark_v1.json"
    strategies: list[str] = Field(
        default_factory=lambda: ["vector_only", "graph_only", "hybrid"]
    )
    num_runs: int = 3   # Average over N runs


class Settings(BaseSettings):
    neo4j: Neo4jConfig = Field(default_factory=Neo4jConfig)
    qdrant: QdrantConfig = Field(default_factory=QdrantConfig)
    fuseki: FusekiConfig = Field(default_factory=FusekiConfig)
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)
    log_level: str = "INFO"

    class Config:
        env_prefix = "KGRAG_"
        env_nested_delimiter = "__"
```
