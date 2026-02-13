# C3. KG-RAG QA Agent — Retrieval Strategies (C3.3)

The core differentiator of this thesis contribution: **ontology-informed hybrid retrieval**
that combines vector similarity, graph traversal, and ontology-guided expansion.

---

## Strategy Overview

| Strategy | Source | Strengths | Weaknesses |
|----------|--------|-----------|------------|
| **VectorOnly** | Qdrant | Fast, good for lexical similarity | No structure, misses multi-hop |
| **GraphOnly** | Neo4j | Precise relationships, multi-hop | Needs entity linking, no fuzzy match |
| **Hybrid (FusionRAG)** | Both | Best of both worlds | More complex, tuning required |
| **Ontology-Expanded** | Fuseki + Both | Handles synonyms, class hierarchies | Requires quality ontology |

All strategies implement a common `Retriever` protocol; the evaluation (C3.5)
compares them head-to-head on the same benchmark.

---

## 1. VectorRetriever (C3.3.1) — Classic RAG Baseline

```python
# kgrag/retrieval/vector.py

class VectorRetriever:
    """Classic RAG: embed question → search Qdrant → return top-k chunks."""

    def __init__(
        self,
        qdrant: QdrantConnector,
        ollama: OllamaConnector,
        config: RetrievalConfig,
    ) -> None: ...

    async def retrieve(self, query: QAQuery) -> list[RetrievedContext]:
        """
        1. Embed query.raw_question via Ollama embedding model
        2. Search Qdrant collection for top-k nearest chunks
        3. Wrap results as RetrievedContext(source=VECTOR)
        """
```

**Purpose**: Baseline for C3.5 comparison. Shows what vanilla RAG achieves.

---

## 2. GraphRetriever (C3.3.2) — KG-Only Retrieval

Three sub-strategies, all querying Neo4j:

### 2a. Entity-Centric Retrieval

```python
class EntityCentricRetriever:
    """
    1. Entity-link: find KG entities matching question terms
       - Fuzzy match entity labels against detected_entities
       - Use embedding similarity as fallback
    2. Fetch 1-hop neighborhood of matched entities
    3. Serialize subgraph as natural language context
    """
```

**Cypher pattern**:
```cypher
MATCH (e:Entity)-[r]-(neighbor)
WHERE e.id IN $entity_ids
RETURN e, r, neighbor
LIMIT $max_nodes
```

### 2b. Subgraph Retrieval

```python
class SubgraphRetriever:
    """
    1. Entity-link (same as above)
    2. Expand to k-hop subgraph between matched entities
    3. Rank paths by relation confidence
    4. Return highest-scoring subgraph
    """
```

**Cypher pattern**:
```cypher
MATCH path = (a:Entity)-[*1..{max_hops}]-(b:Entity)
WHERE a.id IN $source_ids AND b.id IN $target_ids
RETURN path, reduce(s = 0, r IN relationships(path) | s + r.confidence) AS score
ORDER BY score DESC
LIMIT $max_paths
```

### 2c. Path-Based Retrieval

```python
class PathRetriever:
    """
    For relationship questions ("How does X relate to Y?"):
    1. Entity-link both X and Y
    2. Find shortest paths between them
    3. Serialize paths as natural language evidence
    """
```

**Cypher pattern**:
```cypher
MATCH path = shortestPath((a:Entity)-[*..{max_hops}]-(b:Entity))
WHERE a.id = $source_id AND b.id = $target_id
RETURN path
```

### Graph Context Serialization

The graph retriever serializes subgraphs to natural language for the LLM:

```
Entities:
- "Reaktor A" (NuclearFacility, confidence: 0.92)
- "Abbruchverfahren X" (DecommissioningMethod, confidence: 0.87)

Relations:
- "Reaktor A" --[usesMethod]--> "Abbruchverfahren X" (confidence: 0.85)
  Evidence: "Für den Rückbau von Reaktor A wird das Verfahren X eingesetzt."
```

---

## 3. HybridRetriever / FusionRAG (C3.3.3) — Primary Strategy

```python
# kgrag/retrieval/hybrid.py

class HybridRetriever:
    """
    FusionRAG: combine vector + graph retrieval with weighted fusion.

    The key innovation: ontology-informed fusion where graph results are
    weighted higher when the question targets known ontology relations.
    """

    def __init__(
        self,
        vector: VectorRetriever,
        graph: GraphRetriever,
        ontology: OntologyConnector,
        reranker: CrossEncoderReranker,
        config: RetrievalConfig,
    ) -> None: ...

    async def retrieve(self, query: QAQuery) -> list[RetrievedContext]:
        """
        Phase 1 — Parallel retrieval:
            vector_results = await vector.retrieve(query)
            graph_results  = await graph.retrieve(query)

        Phase 2 — Ontology-informed weight adjustment:
            If query.detected_types match ontology classes with many relations
            → increase graph_weight (structured info more likely useful)
            If query is free-text / no entity matches
            → increase vector_weight (fuzzy matching needed)

        Phase 3 — Reciprocal Rank Fusion:
            Merge results using RRF with adjusted weights:
            score(d) = Σ_s  weight_s / (k + rank_s(d))
            where s ∈ {vector, graph}, k = 60

        Phase 4 — Cross-encoder reranking:
            Top-N fused results → cross-encoder(query, context) → final ranking

        Phase 5 — Deduplication + provenance:
            Deduplicate overlapping chunks/subgraphs
            Attach provenance (which retriever, scores, entity IDs)
        """
```

### Reciprocal Rank Fusion (RRF)

```python
def reciprocal_rank_fusion(
    ranked_lists: dict[str, list[RetrievedContext]],
    weights: dict[str, float],
    k: int = 60,
) -> list[RetrievedContext]:
    """
    Standard RRF with per-source weights.

    For each document d appearing in any ranked list:
        rrf_score(d) = Σ_{source} weight[source] / (k + rank[source](d))

    Returns merged list sorted by rrf_score descending.
    """
```

### Adaptive Fusion Weights

```python
def compute_adaptive_weights(
    query: QAQuery,
    ontology: OntologyConnector,
    base_weights: dict[str, float],
) -> dict[str, float]:
    """
    Adjust fusion weights based on query characteristics:

    - If detected_entities are found in KG → boost graph weight
    - If detected_types match classes with >5 relations → boost graph weight
    - If question_type is CAUSAL/COMPARATIVE → boost graph weight (path retrieval)
    - If question_type is FACTOID and no entities found → boost vector weight
    - Ontology weight boosted when query terms match class labels/synonyms
    """
```

---

## 4. OntologyRetriever (C3.3.4) — Query Expansion

```python
# kgrag/retrieval/ontology.py

class OntologyRetriever:
    """
    Uses the Fuseki ontology to expand and enrich queries before retrieval.

    NOT a standalone retriever — acts as a pre-processing enhancer
    for VectorRetriever and GraphRetriever.
    """

    def expand_query(self, query: QAQuery) -> QAQuery:
        """
        1. Map detected_entities to ontology classes
        2. Expand with:
           - Parent classes (e.g., "Reaktor" → also search "NuclearFacility")
           - Sibling classes (e.g., "BWR" → also consider "PWR")
           - Related properties (tell GraphRetriever which relations to traverse)
           - rdfs:label / skos:altLabel synonyms
        3. Return enriched QAQuery with expanded detected_types
        """

    def get_expected_relations(self, entity_types: list[str]) -> list[str]:
        """
        Given ontology classes, return which relations to prioritize
        in graph retrieval. E.g., NuclearFacility → [hasComponent, 
        usesMethod, locatedIn, operatedBy, ...]
        """

    def get_answer_template(self, question_type: QuestionType, entity_types: list[str]) -> str:
        """
        Generate an answer structure hint based on ontology.
        E.g., for QuestionType.LIST + entity_type=DecommissioningPhase:
        → "The answer should list instances of DecommissioningPhase."
        """
```

### SPARQL Queries for Expansion

```sparql
# Get subclasses + labels for expansion
SELECT ?sub ?label WHERE {
    ?sub rdfs:subClassOf* <{class_uri}> .
    ?sub rdfs:label ?label .
}

# Get synonyms
SELECT ?altLabel WHERE {
    <{class_uri}> skos:altLabel ?altLabel .
}

# Get expected relations for a class
SELECT ?prop ?range ?propLabel WHERE {
    ?prop rdfs:domain <{class_uri}> .
    ?prop rdfs:range ?range .
    ?prop rdfs:label ?propLabel .
}
```

---

## 5. Cross-Encoder Reranker

```python
# kgrag/retrieval/reranker.py

class CrossEncoderReranker:
    """
    Reranks retrieved contexts using a cross-encoder model.
    Applied as final step in HybridRetriever.
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> None:
        from sentence_transformers import CrossEncoder
        self._model = CrossEncoder(model_name)

    def rerank(
        self, 
        query: str, 
        contexts: list[RetrievedContext], 
        top_k: int = 5,
    ) -> list[RetrievedContext]:
        """
        Score each (query, context.text) pair.
        Return top_k sorted by cross-encoder score.
        """
```

---

## 6. Entity Linking (shared utility)

```python
# kgrag/retrieval/entity_linker.py

class EntityLinker:
    """
    Links question terms to KG entities. Used by all graph-based retrievers.

    Strategies (in priority order):
    1. Exact label match (case-insensitive)
    2. Fuzzy label match (Levenshtein ≤ 2)
    3. Embedding similarity (embed term → search Qdrant entity index)
    4. Ontology-expanded match (via OntologyRetriever synonyms)
    """

    def link(self, terms: list[str]) -> list[KGEntity]:
        """Return matched KG entities for the given terms."""
```

---

## 7. Protocol Definition

```python
# kgrag/core/protocols.py

from typing import Protocol, runtime_checkable

@runtime_checkable
class Retriever(Protocol):
    """All retrieval strategies implement this."""
    async def retrieve(self, query: QAQuery) -> list[RetrievedContext]: ...


@runtime_checkable
class QueryExpander(Protocol):
    """Ontology-based query expansion."""
    def expand_query(self, query: QAQuery) -> QAQuery: ...


@runtime_checkable
class Reranker(Protocol):
    """Context reranking."""
    def rerank(
        self, query: str, contexts: list[RetrievedContext], top_k: int = 5
    ) -> list[RetrievedContext]: ...
```

---

## 8. Strategy Selection Logic

```python
def select_strategy(query: QAQuery, config: RetrievalConfig) -> Retriever:
    """
    Auto-select retrieval strategy based on question characteristics.
    
    Rules:
    - CAUSAL/COMPARATIVE → HybridRetriever (needs path + context)
    - BOOLEAN with 2+ entities → GraphRetriever.path (relationship check)
    - LIST with ontology class → GraphRetriever.entity_centric
    - FACTOID with no entity matches → VectorRetriever (fuzzy)
    - Default → HybridRetriever
    """
```

This auto-selection is logged for evaluation — C3.5 tracks which strategy
was selected per question and whether manual override would have helped.
