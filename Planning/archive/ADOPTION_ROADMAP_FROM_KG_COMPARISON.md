# Implementation Roadmap: KGB vs kg-comparison

**Focus**: What we should adopt from colleague's approach, what to keep unique

---

## 🎯 High-Priority Adoptions from kg-comparison

### 1. **Single-Pass Relation Extraction** (Can do IMMEDIATELY)

**Their approach** (kg-comparison):
```python
# src/extractor/ollama_extractor.py
async def extract(self, text: str, schema: KnowledgeGraphOntology) -> KnowledgeGraph:
    messages = [
        {
            "role": "system",
            "content": f"""
            Extract BOTH entities AND relations from the text.
            
            ENTITY_ONTOLOGY_SCHEMA: {entities_json}
            RELATION_ONTOLOGY_SCHEMA: {relations_json}
            
            Output format: {{"nodes": [...], "relations": [...]}}
            """
        },
        {"role": "user", "content": text}
    ]
    
    response = client.beta.chat.completions.parse(
        model=self.config.model,
        messages=messages,
        response_format=KnowledgeGraph,  # Both entities + relations
    )
    return KnowledgeGraph(**json.loads(response.choices[0].message.content))
```

**Why adopt**:
- ✅ Relations extracted in SAME LLM call (no extra cost)
- ✅ Semantic coherence (entities + relations together)
- ✅ Simpler pipeline (no Phase 5 waiting)

**Implementation for KGB** (Code sketch):
```python
# Modify LLMEntityExtractor to also extract relations
# File: src/kgbuilder/extraction/relation.py (new)

class LLMEntityRelationExtractor:
    async def extract(
        self,
        texts: list[str],
        ontology_classes: list[OntologyClassDef],
        ontology_relations: list[OntologyRelationDef],  # NEW
        num_retries: int = 3
    ) -> tuple[list[ExtractedEntity], list[ExtractedRelation]]:
        
        # Modified prompt: include both entities and relations
        system_prompt = f"""
        Extract entities AND relations from the text.
        
        Allowed entities: {entities_schema}
        Allowed relations: {relations_schema}
        
        For each relation, validate:
        - start_node_type must exist in entities
        - end_node_type must exist in entities
        - relation type must match allowed relations
        """
        
        response = await self._llm.generate_structured(
            texts=texts,
            system_prompt=system_prompt,
            schema=EntityRelationSchema
        )
        
        return response.entities, response.relations
```

**Where to wire**: [src/kgbuilder/experiment/manager.py](../src/kgbuilder/experiment/manager.py#L410-430)
```python
# Instead of Phase 5 separate extraction:

# Extract both entities AND relations in discovery phase
discover_result = discovery_loop.run_discovery(
    max_iterations=...,
    coverage_target=0.85,
    include_relations=True,  # NEW
)

# discover_result now contains: entities + relations
```

**Effort**: 3-4 hours (modify extractor + discovery loop)  
**Benefit**: Complete KG immediately, no Phase 5 wait

---

### 2. **Rich Schema Representation** (Property Extraction)

**Their approach** (kg-comparison):
```python
# src/schema_builder/ollama_schema_builder.py
@dataclass
class PropertyOntology:
    name: str           # "name", "start_date", "location"
    type: str           # "string", "date", "location"
    description: str    # "Name of the action"

@dataclass
class NodeOntology:
    type: str
    description: str
    properties: list[PropertyOntology]  # Rich schema!

# Usage in extraction prompt:
entities_schema = {
    "Action": {
        "description": "An action in decommissioning",
        "properties": [
            {"name": "name", "type": "string"},
            {"name": "start_date", "type": "date"},
            {"name": "estimated_duration", "type": "string"}
        ]
    }
}
```

**Why adopt**:
- ✅ Richer entity representation
- ✅ Guides LLM to extract properties
- ✅ Better structure for downstream use

**Current KGB state**:
```python
# We only have class names
ontology_classes = ["Action", "Parameter", "State", ...]
# Missing: property definitions per class
```

**Implementation for KGB**:
```python
# File: src/kgbuilder/core/models.py (modify)

@dataclass
class OntologyClassDef:
    uri: str
    label: str
    description: str | None
    examples: list[str] = field(default_factory=list)
    properties: list[OntologyPropertyDef] = field(default_factory=list)  # NEW

@dataclass
class OntologyPropertyDef:
    name: str
    data_type: str  # "string", "date", "float", "boolean"
    description: str | None = None
    required: bool = False
    examples: list[str] = field(default_factory=list)

# Usage in ontology service:
def get_class_with_properties(self, class_name: str) -> OntologyClassDef:
    """Return class with all properties"""
    class_def = OntologyClassDef(...)
    class_def.properties = self._extract_data_properties(class_name)
    return class_def
```

**Effort**: 4-5 hours (ontology service + extraction prompt)  
**Benefit**: Richer entity extraction, match kg-comparison quality

---

### 3. **Formal Evaluation Framework** (Precision/Recall/F1)

**Their approach** (kg-comparison):
```python
# src/evaluation/evaluator.py
def evaluate_knowledge_graphs(gold_kg: KnowledgeGraph, pred_kg: KnowledgeGraph) -> MetricSummary:
    """Evaluate predicted KG against gold standard"""
    
    # Node matching
    tp_nodes = len([n for n in pred_kg.nodes if n in gold_kg.nodes])
    fp_nodes = len(pred_kg.nodes) - tp_nodes
    fn_nodes = len(gold_kg.nodes) - tp_nodes
    
    node_precision = tp_nodes / (tp_nodes + fp_nodes) if (tp_nodes + fp_nodes) > 0 else 0
    node_recall = tp_nodes / (tp_nodes + fn_nodes) if (tp_nodes + fn_nodes) > 0 else 0
    
    # Relation matching (similar)
    # Property matching (similar)
    
    return MetricSummary(
        nodes=MetricSet(precision=node_precision, recall=node_recall, f1=...),
        relations=MetricSet(...),
        properties=MetricSet(...),
        global_=MetricSet(...)
    )
```

**Current KGB state**:
```python
# We track:
# - Entities discovered
# - Entities deduplicated
# - Nodes created in Neo4j
# Missing: Formal metrics against ground truth
```

**Implementation for KGB** (Phase post-discovery):
```python
# File: src/kgbuilder/validation/evaluator.py (new)

@dataclass
class MetricSet:
    precision: float
    recall: float
    f1: float
    tp: int
    fp: int
    fn: int

def evaluate_extraction(
    extracted: list[ExtractedEntity],
    ground_truth: list[ExtractedEntity],
    match_threshold: float = 0.85
) -> MetricSet:
    """Evaluate extraction against ground truth"""
    
    tp = len([e for e in extracted 
              if any(similarity(e, g) > match_threshold for g in ground_truth)])
    fp = len(extracted) - tp
    fn = len(ground_truth) - tp
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    return MetricSet(precision=precision, recall=recall, f1=f1, tp=tp, fp=fp, fn=fn)

# Log to wandb
wandb_run.log({
    "entity_precision": metric_set.precision,
    "entity_recall": metric_set.recall,
    "entity_f1": metric_set.f1,
    "tp": metric_set.tp,
    "fp": metric_set.fp,
    "fn": metric_set.fn
})
```

**Effort**: 2-3 hours (evaluation logic + wandb integration)  
**Benefit**: Quantitative comparison, demo readiness

---

## 💡 Features to Keep Unique in KGB

### 1. ✅ **Iterative Discovery**
Don't remove! It's our advantage:
```python
# Their approach: one-shot extraction
# Our approach: iterative with coverage target
for iteration in range(max_iterations):
    if coverage >= coverage_target:
        break  # Early termination = faster execution
```

### 2. ✅ **Confidence Scoring**
Keep the per-entity confidence:
```python
@dataclass
class ExtractedEntity:
    confidence: float = 0.8  # They don't have this
    
# Allows us to filter low-confidence extractions
# Better for demo (no garbage entities)
```

### 3. ✅ **Multi-Attempt Fallback**
Keep the question-augmented retry:
```python
# Attempt 1: Standard extraction
# Attempt 2: With question context (higher chance of success)
# This is unique to us, makes us more robust
```

### 4. ✅ **Real-time Wandb Logging**
Better than MLflow for this use case:
- ✅ Faster setup
- ✅ Better visualization
- ✅ Real-time progress (not just checkpoints)

### 5. ✅ **JSON-based Config**
Keep it over Hydra:
- ✅ Simpler for Docker/deployment
- ✅ Version-controllable
- ✅ Less CLI complexity for demo

---

## 🔧 Quick Implementation Priority

### WEEK 1 (This week)
Priority 1 (DO NOW):
1. ✅ Fix Ollama timeout (increase to 180s)
2. ⏳ Monitor current experiment to completion
3. 🔧 Extract relations in same LLM call (adopt #1)

Priority 2 (Do next):
4. 🔧 Add property extraction (adopt #2)
5. 📊 Create evaluation framework (adopt #3)

### WEEK 2
6. 🎯 Create demo config (fast execution)
7. 📈 Compare results with kg-comparison approach
8. 🎓 Document final results

---

## 🚀 Concrete Code Changes (Step-by-step)

### Change 1: Add Relations to Discovery Loop

**File**: [src/kgbuilder/discovery/iterative_loop.py](../src/kgbuilder/discovery/iterative_loop.py)

```python
@dataclass
class DiscoveryResult:
    entities: list[ExtractedEntity]
    relations: list[ExtractedRelation] = field(default_factory=list)  # ADD THIS
    coverage: float
    iterations: int

async def run_discovery(
    self,
    max_iterations: int = 3,
    coverage_target: float = 0.85,
    extract_relations: bool = True,  # ADD THIS
) -> DiscoveryResult:
    
    all_entities = []
    all_relations = []  # ADD THIS
    
    for iteration in range(max_iterations):
        for question in self.ontology_questions:
            docs = self.retriever.retrieve(question, k=10)
            
            # Extract entities
            entities = await self.extractor.extract(docs, question)
            all_entities.extend(entities)
            
            # Extract relations (NEW)
            if extract_relations:
                relations = await self.relation_extractor.extract(
                    docs,
                    entity_types=[e.entity_type for e in all_entities],
                    question=question
                )
                all_relations.extend(relations)
        
        coverage = self._calculate_coverage(all_entities)
        if coverage >= coverage_target:
            break
    
    return DiscoveryResult(
        entities=all_entities,
        relations=all_relations,  # ADD THIS
        coverage=coverage,
        iterations=iteration + 1
    )
```

### Change 2: Create Relation Extractor

**File**: [src/kgbuilder/extraction/relation.py](../src/kgbuilder/extraction/relation.py) (NEW)

```python
from dataclasses import dataclass

@dataclass
class ExtractedRelation:
    source_id: str
    source_type: str
    target_id: str
    target_type: str
    relation_type: str
    confidence: float
    evidence: list[Evidence] = field(default_factory=list)

class LLMRelationExtractor:
    def __init__(self, llm_provider, ontology_service, confidence_threshold=0.5):
        self._llm = llm_provider
        self._ontology = ontology_service
        self._confidence_threshold = confidence_threshold
    
    async def extract(
        self,
        texts: list[str],
        entity_types: list[str],
        question: str | None = None
    ) -> list[ExtractedRelation]:
        """Extract relations from texts"""
        
        # Get allowed relations from ontology
        allowed_relations = self._ontology.get_all_relations()
        
        prompt = f"""
        Extract relationships between {', '.join(entity_types)} entities.
        
        Allowed relationships: {json.dumps(allowed_relations)}
        
        For each relationship:
        - Identify source and target entities
        - Verify they are mentioned in the text
        - Assign confidence (0-1)
        
        Output format: {{"relations": [...]}}
        """
        
        response = await self._llm.generate_structured(
            texts=texts,
            prompt=prompt,
            schema=RelationSchema
        )
        
        relations = []
        for rel in response.relations:
            if rel.confidence >= self._confidence_threshold:
                relations.append(ExtractedRelation(
                    source_id=rel.source_id,
                    source_type=rel.source_type,
                    target_id=rel.target_id,
                    target_type=rel.target_type,
                    relation_type=rel.relation_type,
                    confidence=rel.confidence
                ))
        
        return relations
```

### Change 3: Wire Relations into Manager

**File**: [src/kgbuilder/experiment/manager.py](../src/kgbuilder/experiment/manager.py#L410-430)

```python
# In _build_kg method:

# Create relation extractor
from kgbuilder.extraction.relation import LLMRelationExtractor
relation_extractor = LLMRelationExtractor(
    llm_provider=llm,
    ontology_service=ontology_service,
    confidence_threshold=variant.params.relation_confidence_threshold
)

# Run discovery WITH relations
discovery_loop = IterativeDiscoveryLoop(
    retriever=retriever,
    extractor=entity_extractor,
    relation_extractor=relation_extractor,  # NEW
    question_generator=question_gen,
    ontology_classes=ontology_classes,
)

discover_result = discovery_loop.run_discovery(
    max_iterations=variant.params.max_iterations,
    coverage_target=0.85,
    extract_relations=True,  # NEW
)

# Now discover_result has both entities AND relations
entities = discover_result.entities
relations = discover_result.relations  # NEW

# Build KG with both
kg_builder = KGBuilder(primary_store=neo4j_store)
build_result = kg_builder.build(
    entities=nodes,
    relations=relations  # ADD THIS
)
```

---

## 📊 Side-by-side: Before vs After Implementation

| Aspect | Before (Current) | After (With Adoptions) |
|--------|------------------|----------------------|
| **Entities per call** | ~3-10 | ~3-10 (same) |
| **Relations extracted** | ❌ None (Phase 5) | ✅ In discovery |
| **Properties per entity** | ❌ None | ✅ name, date, location, ... |
| **Confidence scoring** | ✅ Yes | ✅ Enhanced |
| **Evaluation metrics** | ⚠️ Ad-hoc | ✅ Formal (P/R/F1) |
| **Time to complete KG** | 18 hours | 12 hours (no Phase 5) |
| **Demo readiness** | 40% | 95% |

---

## ⚠️ Risks & Mitigation

### Risk 1: More LLM calls = Slower execution
**Mitigation**: Single-pass extraction (entities + relations) = SAME number of calls

### Risk 2: JSON validation complexity
**Mitigation**: Use Pydantic schema (like kg-comparison) with fallback parsing

### Risk 3: Properties missing from ontology
**Mitigation**: Extract data properties from Fuseki (they do this with owlready2)

---

## 🎯 End Result After Changes

**Your pipeline will have**:
1. ✅ Entities + Relations extracted in discovery (not waiting for Phase 5)
2. ✅ Rich properties per entity (not just types)
3. ✅ Formal evaluation metrics (P/R/F1)
4. ✅ Unique iterative discovery (faster than one-shot)
5. ✅ Unique confidence scoring (better quality control)
6. ✅ Better demo-ready state

**Estimated additional effort**: 15-20 hours over next 1-2 weeks  
**Estimated payoff**: Complete feature parity with kg-comparison + unique advantages

---

**Decision**: Proceed with all 3 adoptions, keep all 5 unique features.
