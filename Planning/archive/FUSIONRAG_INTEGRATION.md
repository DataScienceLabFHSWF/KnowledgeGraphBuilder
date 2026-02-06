# FusionRAG Integration Planning

> **Last Updated**: 2026-02-02  
> **Feature**: Advanced RAG with FusionRAG capabilities for knowledge discovery

---

## Overview

**FusionRAG** provides a state-of-the-art document processing and retrieval framework. We plan to integrate it in two key ways:

1. **Benchmark Standard RAG Pipeline**: Use FusionRAG's unified processor as the baseline for comparing different RAG architectures
2. **Deep Research & Knowledge Discovery**: Leverage FusionRAG's full capabilities for iterative entity discovery and semantic reasoning

---

## 1. Standard RAG Benchmark Pipeline

### Purpose
Establish a baseline RAG system to benchmark against more complex approaches.

### Components

#### 1.1 Document Processing (✅ In Progress)
- [x] Unified document processor with text extraction
- [x] Chunking with metadata preservation
- [x] Language detection
- [ ] Implement retrieval pipeline
- [ ] Measure retrieval quality metrics (precision, recall, NDCG)

#### 1.2 Simple Retrieval
```python
class StandardRAGPipeline:
    """Basic RAG: Dense retrieval only."""
    
    def __init__(self, vector_store: QdrantStore, llm_provider: OllamaProvider):
        self.vector_store = vector_store
        self.llm = llm_provider
    
    def retrieve(self, query: str, top_k: int = 5) -> list[str]:
        """Retrieve most similar documents."""
        query_embedding = embed(query)
        results = self.vector_store.search(query_embedding, top_k=top_k)
        return [r.content for r in results]
    
    def generate(self, query: str) -> str:
        """Generate response from retrieved docs."""
        docs = self.retrieve(query)
        prompt = f"Context: {docs}\nQuestion: {query}\nAnswer:"
        return self.llm.generate(prompt)
```

#### 1.3 Evaluation Metrics
- Retrieval recall (is correct document in top-k?)
- Retrieval precision (are retrieved documents relevant?)
- NDCG (normalized discounted cumulative gain)
- Answer relevance (using proxy metrics)
- Answer faithfulness (grounding in retrieved documents)

---

## 2. FusionRAG Deep Research Pipeline

### Purpose
Enable iterative knowledge discovery and semantic reasoning for comprehensive KG construction.

### Architecture

```
Query/Entity
    ↓
[1. Semantic Search]
    - Multi-query expansion
    - Hybrid search (dense + sparse)
    - Relevance feedback loop
    ↓
[2. Document Understanding]
    - Extract semantic structure
    - Identify key entities and concepts
    - Build local topic graphs
    ↓
[3. Iterative Discovery]
    - Question generation from documents
    - Adaptive retrieval based on gaps
    - Confidence-based refinement
    ↓
[4. Knowledge Synthesis]
    - Entity linking across documents
    - Relation discovery
    - Contradiction detection
    - Confidence aggregation
    ↓
Knowledge Graph with provenance
```

### Key Components

#### 2.1 Multi-Strategy Retrieval
```python
class FusionRAGRetriever:
    """Advanced retrieval combining multiple strategies."""
    
    def __init__(self, 
                 dense_retriever: DenseRetriever,      # Vector similarity
                 sparse_retriever: SparseRetriever,    # BM25
                 reranker: Reranker,                   # Cross-encoder
                 llm: LLMProvider):
        self.dense = dense_retriever
        self.sparse = sparse_retriever
        self.reranker = reranker
        self.llm = llm
    
    def retrieve_with_fusion(self, query: str, top_k: int = 10) -> list[Document]:
        """Fuse multiple retrieval strategies."""
        # 1. Get candidates from both dense and sparse
        dense_results = self.dense.search(query, k=top_k*2)
        sparse_results = self.sparse.search(query, k=top_k*2)
        
        # 2. Merge and deduplicate
        merged = self._merge_results(dense_results, sparse_results)
        
        # 3. Rerank with cross-encoder
        reranked = self.reranker.rank(query, merged, top_k)
        
        return reranked
```

#### 2.2 Iterative Question Generation & Answering
```python
class IterativeDiscoveryAgent:
    """Iteratively discover knowledge through question generation."""
    
    def __init__(self, 
                 retriever: FusionRAGRetriever,
                 llm: LLMProvider,
                 extractor: EntityRelationExtractor,
                 graph_store: Neo4jStore):
        self.retriever = retriever
        self.llm = llm
        self.extractor = extractor
        self.graph = graph_store
    
    async def discover_knowledge(self, seed_topic: str, iterations: int = 3):
        """Iteratively discover knowledge for a topic."""
        discovered = set()
        
        for i in range(iterations):
            # 1. Generate questions about topic
            questions = self.llm.generate_questions(
                seed_topic,
                existing_knowledge=discovered
            )
            
            # 2. Retrieve answers
            for q in questions:
                docs = self.retriever.retrieve_with_fusion(q, top_k=5)
                
                # 3. Extract entities and relations
                entities, relations = self.extractor.extract(
                    docs,
                    context=seed_topic
                )
                
                # 4. Store and expand
                discovered.update(entities)
                self.graph.add_entities_and_relations(entities, relations)
        
        return discovered
```

#### 2.3 Semantic Linking & Disambiguation
```python
class SemanticLinker:
    """Link entities across documents using semantic similarity."""
    
    def link_entities(self, entities: list[Entity], threshold: float = 0.85):
        """Find and link coreferent entities."""
        embeddings = [embed(e.text) for e in entities]
        
        links = []
        for i, e1 in enumerate(entities):
            for j, e2 in enumerate(entities[i+1:], i+1):
                sim = cosine_similarity(embeddings[i], embeddings[j])
                if sim > threshold:
                    # Check for contradictions
                    if not self._contradicts(e1, e2):
                        links.append((e1.id, e2.id, sim))
        
        return links
```

#### 2.4 Confidence & Provenance Tracking
```python
@dataclass
class ProvenanceMetadata:
    """Track provenance of extracted knowledge."""
    source_documents: list[str]           # Which documents contributed
    retrieval_score: float                # How relevant was retrieval
    extraction_confidence: float          # How confident was extraction
    iteration_discovered: int             # Which iteration found it
    evidence_strength: float              # Aggregated confidence
    contradictions: list[str]             # Any conflicting sources
```

---

## 3. Implementation Roadmap

### Phase 1: Standard RAG (Week 1)
- [x] Document ingestion and chunking
- [ ] Dense vector retrieval
- [ ] Basic LLM answering
- [ ] Evaluation suite
- [ ] Baseline metrics

### Phase 2: FusionRAG Retrieval (Week 2)
- [ ] Implement sparse retriever (BM25)
- [ ] Add cross-encoder reranking
- [ ] Fusion strategy
- [ ] Comparative metrics vs. standard RAG

### Phase 3: Deep Research Agent (Week 3)
- [ ] Question generation pipeline
- [ ] Iterative discovery loop
- [ ] Entity linking and disambiguation
- [ ] Confidence aggregation
- [ ] Graph construction from discovered knowledge

### Phase 4: Validation & Optimization (Week 4)
- [ ] Competency question validation
- [ ] Knowledge graph completeness assessment
- [ ] Performance optimization
- [ ] Comparison: Standard RAG vs. FusionRAG

---

## 4. Evaluation Framework

### Metrics to Track

#### Retrieval Quality
- Recall@k: Is the correct document in top-k results?
- Precision@k: What fraction of top-k results are relevant?
- NDCG: Ranking quality considering position
- MRR: Mean reciprocal rank of first relevant

#### Knowledge Discovery
- Entity coverage: % of ontology classes found
- Relation coverage: % of ontology relations discovered
- Knowledge redundancy: How many sources confirm each fact
- Contradiction rate: % of conflicting assertions

#### Answer Quality
- Faithfulness: Does answer ground in retrieved docs?
- Relevance: Does answer address the query?
- Completeness: Does answer cover all aspects?
- Consistency: Are answers consistent with KG?

#### Efficiency
- Retrieval time per query
- Extraction time per document
- Total discovery time
- Memory usage

---

## 5. Competitive Advantages of FusionRAG Approach

1. **Multi-Strategy Retrieval**: Combines dense + sparse for robustness
2. **Iterative Refinement**: Asks new questions based on discoveries
3. **Confidence Tracking**: Knows what it doesn't know
4. **Semantic Linking**: Handles entity coreference across documents
5. **Provenance**: Full lineage from sources to conclusions

---

## 6. Integration with Existing Systems

### Document Processor ↔ Retriever
```
AdvancedDocumentProcessor
    ↓ (chunks + metadata + language)
    ↓
FusionRAGRetriever
    ↓ (multi-strategy ranking)
    ↓
EntityExtractor (ontology-guided)
    ↓ (entities + relations + confidence)
    ↓
Neo4jGraphStore (semantic KG)
```

### Pipelines
1. **Ingest Pipeline**: Document processing → Vector storage
2. **Standard RAG**: Vector retrieval → LLM answering
3. **FusionRAG**: Multi-strategy retrieval → Entity extraction → Knowledge synthesis

---

## 7. Example: Deep Research on Decommissioning

```python
# Initialize
agent = IterativeDiscoveryAgent(
    retriever=FusionRAGRetriever(...),
    llm=OllamaProvider("qwen3"),
    extractor=LLMEntityExtractor(...),
    graph=Neo4jStore(...)
)

# Discover knowledge
discovered = await agent.discover_knowledge(
    seed_topic="Nuclear facility decommissioning",
    iterations=5
)

# Results
print(f"Discovered {len(discovered)} entities")
print(f"Found {len(agent.graph.relations)} relations")
print(f"Covered {coverage}% of ontology")
```

---

## Success Criteria

- [x] Ingestion pipeline working (documents → vectors)
- [ ] Standard RAG > 80% retrieval recall on test queries
- [ ] FusionRAG > 90% retrieval recall
- [ ] Entity discovery > 85% coverage of ontology
- [ ] Knowledge graph > 80% complete vs. competency questions
- [ ] Inference time < 5 sec per query
- [ ] System handles 30+ documents efficiently

---

## References

- FusionRAG Paper: https://arxiv.org/abs/2404.68505
- Dense Passage Retrieval: https://arxiv.org/abs/2004.04906
- ColBERT: https://arxiv.org/abs/2004.12832
- Multi-hop QA: https://arxiv.org/abs/1809.02776
