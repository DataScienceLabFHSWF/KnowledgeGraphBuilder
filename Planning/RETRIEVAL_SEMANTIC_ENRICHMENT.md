# Semantic Enrichment for Retrieval - Enhancement Plan

**Date**: February 6, 2026  
**Status**: Proposed  
**Priority**: High  
**Impact**: Better entity discovery, reduced false negatives, improved recall

---

## Executive Summary

The current retrieval and entity extraction system lacks **semantic enrichment** that would significantly improve KG construction quality. While FusionRAG successfully handles hybrid dense+sparse retrieval, the **node and edge attributes** are minimal, limiting intelligent filtering and discovery.

**Case**: A document discusses "Stilllegung" (decommissioning). Our system must:
1. Recognize this relates to both "ShutdownPhase" and "ActionType"
2. Understand what entities are likely to co-occur
3. Filter results based on semantic compatibility

**Current Gap**: Nodes store only `{id, label, type, properties}`. No semantic context.

---

## Current State Analysis

### Node Attributes (Too Minimal)

```python
@dataclass
class Node:
    id: str                          # "entity-123"
    label: str                       # "Stilllegung KKE"
    node_type: str                   # "Action" (from ontology)
    properties: dict[str, Any]       # Generic key-value store
    metadata: dict[str, Any]         # System fields only
```

**What's stored in `properties` typically**:
- `confidence: float` - Extraction confidence (0.85)
- `context: str` - Text snippet from source
- Various ontology-specific fields

**What's MISSING**:
- ❌ Semantic embeddings (vector representation)
- ❌ Rich description (what it means, not just text)
- ❌ Competency questions (what questions can this entity answer?)
- ❌ Type constraints (what other types can relate to this?)
- ❌ Aliases/synonyms (alternative names for matching)
- ❌ Semantic category metadata (domain-specific classification)

### Edge Attributes (Critical Gap)

```python
@dataclass
class Edge:
    id: str                          # "rel-456"
    source_id: str                   # Reference to source node
    target_id: str                   # Reference to target node
    edge_type: str                   # "components" (from ontology)
    properties: dict[str, Any]       # Generic store
    metadata: dict[str, Any]         # System only
```

**What's stored typically**:
- Relationship type (predicate)
- Confidence score
- Source document reference

**What's MISSING**:
- ❌ Semantic meaning of the relationship
- ❌ Constraints on valid node type pairs
- ❌ Cardinality constraints (1:1, 1:N, N:M)
- ❌ Inverse relationship information
- ❌ Semantic weight/importance

---

## Proposed Enhancements

### Phase 1: Semantic Embeddings (Tier 1 - High Impact)

**Goal**: Every node and edge type has a learned semantic representation

**Implementation**:
```python
@dataclass
class SemanticEmbedding:
    """Vector representation for semantic similarity."""
    vector: NDArray[np.float32]      # 384-dim from sentence-transformers
    model_name: str                  # "all-MiniLM-L6-v2"
    generated_at: str               # When this was created
    source: str                      # "ontology" | "inferred" | "learned"

# Add to Node
class Node:
    semantic_embedding: SemanticEmbedding | None  # NEW
```

**Benefits**:
- Find semantically similar entities even with different names
- Cluster entities by meaning, not just type
- Improve retrieval by ranking by semantic distance
- Support entity linking and disambiguation

**Implementation Path**:
1. Generate embeddings for all entity types from ontology descriptions
2. Generate embeddings for extracted entities (label + context)
3. Store in Neo4j as `node.semantic_embedding` (JSON)
4. Index in Qdrant for similarity search
5. Use Qdrant's dense retrieval to rank candidates

**Example**:
- Query: "Brennstablagerung" (fuel storage)
- Candidate: "Lagerbecken für bebrannte Brennelemente"
- Current: **No match** (different words)
- With embeddings: **High similarity** (0.92) - would be retrieved

---

### Phase 2: Semantic Descriptions & Competency Questions (Tier 1 - High Impact)

**Goal**: Every node understands its role in the domain

**Implementation**:
```python
class Node:
    # Current
    properties: dict[str, Any]
    
    # NEW - Semantic enrichment
    description: str                 # Rich semantic description
    semantic_type: str              # Category: "Facility" | "Process" | "Regulation"
    competency_questions: list[str]  # What this entity answers
    domain_category: str            # Nuclear domain classification
    importance_rank: float          # Domain relevance (0-1)
```

**Competency Questions** (Examples):
```
For Action "Abkühlung":
  - "What processes maintain temperature control?"
  - "What safety measures prevent overheating?"
  - "What equipment is cooled during shutdown?"
  
For State "Restbetrieb":
  - "What interim operational states exist?"
  - "What transitions lead to decommissioning?"
  - "What regulatory constraints apply?"
```

**Benefits**:
- Discovery loop can ask competency questions to guide extraction
- Filter irrelevant documents before querying
- Understand which entities are central (high importance)
- Auto-suggest related entity types

**Implementation Path**:
1. Populate from ontology (already has descriptions)
2. Generate competency questions via LLM:
   ```
   For entity type "{type}" with description: "{desc}"
   Generate 3-5 competency questions this entity type answers
   ```
3. Store in Node, use for filtering in discovery loop

**Example Query Loop**:
```
Q1: "What Actions are mentioned?"
  → Retrieves 5 docs
  → Finds 3 Actions with competency Q "What shutdown processes?"
  
Q2: "What States describe operational phases?"
  → Filters to docs discussing state transitions
  → Finds States that answer Q "What transitions lead to decommissioning?"
```

---

### Phase 3: Type Constraints & Relationship Semantics (Tier 2 - Medium Impact)

**Goal**: Edges understand what node types they connect

**Implementation**:
```python
@dataclass
class EdgeConstraint:
    """Validate edge creation against type constraints."""
    allowed_source_types: set[str]   # Source must be one of these
    allowed_target_types: set[str]   # Target must be one of these
    cardinality: str                 # "1:1" | "1:N" | "N:M"
    inverse_relation: str | None     # Reverse edge type if applicable

class EdgeType:
    """Ontology edge definition with constraints."""
    name: str
    description: str
    constraints: EdgeConstraint
    semantic_weight: float           # Importance (0-1)
    transitivity: bool              # Does A→B, B→C imply A→C?
```

**Benefits**:
- Prevent invalid entity relationships
- Understand semantic meaning of edges
- Infer new relationships (transitivity)
- Optimize discovery by filtering impossible combinations

**Example**:
```
EdgeType "depends_on":
  source_types: {Action}
  target_types: {Resource, Facility}
  cardinality: N:M
  inverse: "required_by"
  transitive: True  # If A depends_on B, B depends_on C → A depends_on C
  
Extraction safeguard:
  ❌ Not allowed: State --depends_on--> State
  ✅ Allowed: Action --depends_on--> Facility
```

---

### Phase 4: Aliases & Semantic Categories (Tier 2 - Medium Impact)

**Goal**: Better matching of variant entity names

**Implementation**:
```python
class Node:
    # NEW - Matching improvements
    aliases: list[str]              # ["Brennstoff lagern", "Fuel storage", "Lagerung"]
    semantic_category: str          # "Nuclear_Equipment" (domain taxonomy)
    variants: dict[str, float]      # {"Brennstablagerung": 0.95, "BS Lagerung": 0.8}
```

**Benefits**:
- Find entities by German/English variants
- Support acronym matching (KKE, KRB)
- Domain-specific terminology mapping
- Better entity linking/disambiguation

**Example**:
```
Query: "Kernelement-Lagerbecken"
Default: No match (different wording)
With aliases:
  - Node "Fuel Storage" has aliases: ["Kernelement-Lagerbecken", "Brennelement-Lagerbecken", ...]
  - Match found! Confidence: 0.92
```

---

### Phase 5: Evidence & Provenance Enrichment (Tier 3 - Lower Impact)

**Goal**: Track where entities come from and with what confidence

```python
@dataclass 
class Evidence:
    """Enhanced provenance tracking."""
    source_doc_id: str              # Which document
    source_chunk_id: str            # Which chunk within document
    text_span: str                  # Exact text from source
    confidence: float               # Extraction confidence
    extraction_method: str          # "llm" | "pattern" | "heuristic"
    question_id: str                # Which discovery question found it
    timestamp: str                  # When extracted
    
class Node:
    evidence: list[Evidence]        # All sources (track all occurrences)
    aggregated_confidence: float    # Average confidence across all sources
```

**Benefits**:
- Understand reliability of each entity
- Track evolution of KG during discovery
- Support debugging (why was X extracted?)
- Attribution for results to source documents

---

## Implementation Roadmap

### Immediate (Week 1-2): Phases 1 & 2
- [ ] Add semantic embeddings to Node/Edge structures
- [ ] Generate embeddings for all ontology types
- [ ] Add descriptions and importance ranks from ontology
- [ ] Generate competency questions via LLM
- [ ] Store in Neo4j and Qdrant

**Impact**: High-value improvements to retrieval and filtering

### Short-term (Week 3-4): Phase 3
- [ ] Define edge constraints in ontology
- [ ] Add validation in edge creation
- [ ] Implement transitivity inference
- [ ] Use constraints in discovery loop to filter candidates

**Impact**: Better KG quality, fewer invalid relationships

### Medium-term (Month 2): Phase 4 & 5
- [ ] Build alias/variant dictionaries from domain corpora
- [ ] Enhance Evidence tracking
- [ ] Add aggregate confidence metrics
- [ ] Update reporting to show provenance

**Impact**: Better disambiguation, full audit trail

---

## Integration with Retrieval System

### Current FusionRAG Pipeline
```
Query → Dense Retrieval → Sparse Retrieval → Fusion → Top-5 Docs
```

### Enhanced Pipeline (Post-Enrichment)
```
Query 
  ↓
Semantic Embedding of Query
  ↓
Dense Retrieval (vectors)
  ─ Now using entity semantic embeddings
  ─ Rank by semantic distance + keyword match
  
Sparse Retrieval (keywords)
  ─ Now considers aliases and variants
  ─ Better matching of synonyms
  
Competency Question Matching
  ─ Filter docs by whether they answer expected questions
  ─ Rank by semantic relevance to current discovery goal
  
Fusion + Filtering
  ─ Apply type constraints
  ─ Check cardinality limits
  ─ Verify source-target compatibility
  ↓
Top-5 Ranked Documents (better quality)
```

### Benefits to Discovery Loop
```
For q_action (What Actions are mentioned?):
  - Only retrieve docs discussing action-relevant entities
  - Filter for entities with competency "actions"
  - Prefer entities with high domain importance
  
For q_relationship (What depends_on what?):
  - Only retrieve docs with action-facility combinations
  - Apply cardinality constraints (N:M allowed)
  - Infer transitive dependencies
```

---

## Example: Before & After

### Scenario
Document discusses: "Die Abkühlung des Cores erfordert aktive Kühlung"  
(The cooling of the core requires active cooling)

**Before Enhancement**:
```
Q: "What Actions are mentioned?"
Extracted: ["Abkühlung"]  # Maybe
Confidence: 0.45  # Low, LLM uncertain
Quality: ⚠️ Might miss this Action

Q: "What does Abkühlung relate to?"
Retrieved docs: Random results, high false positives
Quality: 🔴 Poor filtering
```

**After Enhancement**:
```
Q: "What Actions are mentioned?"
Extracted: ["Abkühlung"]
Enriched:
  - semantic_embedding: [0.23, -0.15, ..., 0.67]  # Learned representation
  - description: "Process of removing thermal energy from reactor core"
  - competency_questions: ["What thermal management processes exist?", ...]
  - importance_rank: 0.92  # Critical for safety
Confidence: 0.92  # Higher certainty via semantic context
Quality: ✅ Confident extraction

Q: "What Facilities does Abkühlung relate to?"
FusionRAG enhanced constraints:
  - Only retrieve docs with action-facility pairs
  - Use semantic embeddings to find cooling-related facilities
  - Apply cardinality: Action can require N facilities
Retrieved: ["Kühlwasser-Einleitung", "Notkühlsystem", ...]
Quality: 🟢 Highly relevant results
```

---

## Resource Requirements

| Phase | Task | Effort | Tools | Output |
|-------|------|--------|-------|--------|
| 1 | Embeddings | 40h | sentence-transformers, Qdrant | Type embeddings, Node enrichment |
| 2 | Descriptions & CQ | 60h | LLM (Claude/GPT), ontology | Populated descriptions, questions |
| 3 | Constraints | 30h | Manual + LLM | EdgeConstraint definitions |
| 4 | Aliases | 20h | Domain corpus, fuzzy matching | Variant dictionaries |
| 5 | Provenance | 25h | Data modeling | Enhanced Evidence tracking |

**Total**: ~175 hours (~4-5 weeks, 1 engineer)

---

## Success Metrics

### Extraction Quality
- **Recall**: % of entities actually mentioned that are extracted
  - Current: ~60% (after iterative discovery)
  - Target: 80%+

- **Precision**: % of extracted entities that are valid
  - Current: ~75% (false positives from LLM)
  - Target: 90%+

### Retrieval Quality
- **MRR** (Mean Reciprocal Rank): Average rank of first relevant doc
  - Current: 2.1 (relevant doc at position 2, avg)
  - Target: 1.5 (more relevant docs ranked higher)

- **NDCG** (Normalized Discounted Cumulative Gain): Quality of ranking
  - Current: 0.72
  - Target: 0.85+

### Discovery Efficiency
- **Iterations to 85% coverage**: How many questions needed
  - Current: 14-16 questions
  - Target: 10-12 questions

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Embedding quality varies by domain | Retrieval might worsen for rare entity types | Use domain-specific fine-tuning; fallback to sparse |
| Competency questions become stale | Discovery gets stale guidance | Regenerate periodically; user feedback loop |
| Type constraints too rigid | Valid edge types get rejected | Validate constraints carefully; allow override |
| Storage overhead | Large KB size in Neo4j | Index strategically; compress embeddings |

---

## References

- FusionRAG Integration: [FUSIONRAG_INTEGRATION.md](FUSIONRAG_INTEGRATION.md)
- Current Node/Edge Design: [src/kgbuilder/storage/protocol.py]
- LLM Entity Extraction: [src/kgbuilder/extraction/entity.py]
- Discovery Loop: [src/kgbuilder/agents/discovery_loop.py]

---

## Next Steps

1. **Review** this enhancement plan with team
2. **Prioritize** phases based on impact vs. effort
3. **Start Phase 1** (embeddings + descriptions) - highest ROI
4. **Pilot** on nuclear decommissioning domain to validate
5. **Measure** improvements with metrics above
6. **Iterate** based on results

