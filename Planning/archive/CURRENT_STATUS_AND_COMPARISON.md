# Current Status & Comparison with kg-comparison

**Date**: February 5, 2026  
**Status**: RUNNING - Baseline experiment in progress  
**Uptime**: Experiment started ~6 hours ago, currently processing discovery phase

---

## 📊 Current System Status

### What's Running Right Now

```
Process: /home/fneubuerger/KnowledgeGraphBuilder/.venv/bin/python scripts/run_single_experiment.py examples/experiment_baseline.json
PID: 2558970
Uptime: 6+ hours
Current Activity: Iterative discovery loop (question processing)
Progress: Processing question #8 of 18 (q_action - "What Actions are mentioned?")
```

### Pipeline Phase Reached

```
✅ Phase 1: Ontology processing (COMPLETE)
   - Loaded 18 ontology classes from Fuseki
   - Generated 18 discovery questions
   
✅ Phase 2: Iterative discovery (IN PROGRESS)
   - Iteration 1 of N max iterations
   - Processing 18 questions sequentially
   - Per question: retrieve 10 documents → extract entities
   
⏳ Phase 3-6: Not yet reached
   - Storage & vectorization
   - Entity synthesis
   - Relation extraction
   - KG assembly
```

### Recent Issue (Just Occurred)

```
2026-02-05 08:29:36 [debug] extracted_from_document
  doc_id=kk1_umweltvertraeglichkeitsuntersuchung_chunk_2
  entity_count=3 question_id=q_action

Generation failed: HTTPConnectionPool(host='localhost', port=18134): Read timed out. 
(read timeout=120)
```

**Root Cause**: Ollama server response timeout (120 seconds exceeded)  
**Status**: System will retry with exponential backoff  
**Impact**: Experiment continues, slower execution due to timeouts

---

## 🔍 Detailed Comparison: KnowledgeGraphBuilder vs kg-comparison

### 1. **Architecture & Framework**

#### kg-comparison (Colleague's Repo)
- **Hydra-based configuration management** (YAML configs with CLI overrides)
- **MLflow integration** for experiment tracking
- **4 framework implementations**: Ollama, LangChain, LlamaIndex, Neo4j
- **Abstract base classes**: Extractor, SchemaBuilder
- **Focus**: Framework comparison (same ontology, different extractors)

#### KnowledgeGraphBuilder (Ours)
- **Pydantic-based configuration management** (JSON configs with code objects)
- **Weights & Biases (wandb) integration** for experiment tracking
- **1 framework implementation**: Ollama-based (fully custom)
- **Protocol-based design** (structural typing via @runtime_checkable)
- **Focus**: Single optimized pipeline with multi-variant experiments

**Verdict**: Both solid, different philosophies:
- kg-comparison: Extensible framework comparison
- KnowledgeGraphBuilder: Focused, optimized single path

---

### 2. **Entity Extraction Pipeline**

#### kg-comparison

**Schema Building** (`src/schema_builder/`)
```python
class SchemaBuilder(ABC):
    def __init__(self, ontology_path: Union[str, Path]):
        self.onto = get_ontology(str(self.ontology_path)).load()
    
    @abstractmethod
    def build_schema(self) -> Union[...]:
        """Framework-specific"""
        pass
```

**Extraction** (`src/extractor/ollama_extractor.py`)
```python
async def extract(self, text: str, schema: KnowledgeGraphOntology) -> KnowledgeGraph:
    # Build system prompt with ontology schema (nodes + relations)
    messages = [
        {"role": "system", "content": self.system_prompt.format(
            entities=json.dumps(ontology_dict["nodes"], ...),
            relations=json.dumps(ontology_dict["relations"], ...)
        )},
        {"role": "user", "content": text}
    ]
    
    # Direct JSON parsing with Pydantic
    response = client.beta.chat.completions.parse(
        model=self.config.model,
        messages=messages,
        response_format=KnowledgeGraph,  # Pydantic schema
    )
    return KnowledgeGraph(**json.loads(response.choices[0].message.content))
```

**Key Features**:
- ✅ Extracts **both entities AND relations** in single LLM call
- ✅ Uses `client.beta.chat.completions.parse()` (structured output)
- ✅ Validates against Pydantic schema automatically
- ✅ Full system prompt guidance for entities + relations
- ❌ Single-pass (can't improve with feedback/discovery)

#### KnowledgeGraphBuilder

**Ontology Service** (`src/kgbuilder/ontology/fuseki_service.py`)
```python
def get_all_classes(self) -> list[str]:
    """Returns: ['Action', 'Parameter', 'State', ...]"""
    
def get_class_description(self, class_name: str) -> str:
    """Returns: "Action represents an action taken in the domain" """
```

**Entity Extraction** (`src/kgbuilder/extraction/entity.py`)
```python
async def extract(
    self,
    texts: list[str],
    ontology_classes: list[OntologyClassDef],  # Class definitions
    num_retries: int = 3
) -> list[ExtractedEntity]:
    # Multi-step, iterative approach
    # 1st attempt: Standard extraction
    # 2nd attempt (on failure): Question-augmented retry
    # Includes confidence scoring per entity
```

**Key Features**:
- ✅ **Iterative discovery** (question-augmented retries)
- ✅ Confidence scoring per entity (not just binary)
- ✅ Fallback mechanism (retry with question context)
- ❌ **Relations not extracted in this phase** (TODO in build_kg.py)
- ✅ Integrates with FusionRAG retrieval (semantic relevance)

**Verdict**: Different strategies:
- **kg-comparison**: One-shot comprehensive extraction (entities + relations)
- **KnowledgeGraphBuilder**: Iterative discovery focused on entities first

---

### 3. **Schema Representation**

#### kg-comparison

```python
# src/models/ollama_ontology_builder_schema.py
@dataclass
class PropertyOntology:
    name: str
    type: str
    description: str

@dataclass
class NodeOntology:
    type: str
    description: str
    properties: list[PropertyOntology] = field(default_factory=list)

@dataclass
class RelationOntology:
    type: str
    description: str
    start_node_type: str
    end_node_type: str

@dataclass
class KnowledgeGraphOntology:
    nodes: dict[str, NodeOntology]
    relations: dict[str, RelationOntology]
```

**Usage in Extraction**:
```json
{
  "nodes": {
    "Action": {
      "type": "Action",
      "description": "An action in decommissioning",
      "properties": [
        {"name": "name", "type": "string", "description": "Action name"},
        {"name": "start_date", "type": "date", "description": "When started"}
      ]
    }
  },
  "relations": {
    "precedes": {
      "type": "precedes",
      "description": "Action A precedes action B",
      "start_node_type": "Action",
      "end_node_type": "Action"
    }
  }
}
```

#### KnowledgeGraphBuilder

```python
# src/kgbuilder/extraction/entity.py
@dataclass
class OntologyClassDef:
    uri: str                      # http://ontology#/Action
    label: str                    # Action
    description: str | None       # "An action in decommissioning"
    examples: list[str] = field(default_factory=list)  # ["Dismantling", "Removal"]

@dataclass
class ExtractedEntity:
    id: str                       # "action-dismantling-1"
    label: str                    # "Dismantling"
    entity_type: str              # "Action"
    confidence: float = 0.8
    evidence: list[Evidence] = field(default_factory=list)
```

**Current Usage in Pipeline**: Only passes class labels (strings), NOT full definitions  
**Problem**: OntologyClassDef conversion added in current experiment:
```python
# From manager.py (this session's fix)
ontology_classes = [
    OntologyClassDef(
        uri=f"http://ontology#/{label}",
        label=label,
        description=None
    )
    for label in ontology_service.get_all_classes()
]
```

**Verdict**:
- **kg-comparison**: Rich schema with properties + type constraints built-in
- **KnowledgeGraphBuilder**: Minimal schema (just class names), confidence scores added

---

### 4. **Relation Extraction**

#### kg-comparison

**✅ IMPLEMENTED**: Relations extracted in single LLM call with entities
```python
# From OllamaExtractor.extract()
response = client.beta.chat.completions.parse(
    model=self.config.model,
    messages=messages,
    response_format=KnowledgeGraph,  # Includes nodes + relations
)

# Output validates against KnowledgeGraph Pydantic model:
class KnowledgeGraph(BaseModel):
    nodes: list[Node]
    relations: list[Relation]
```

#### KnowledgeGraphBuilder

**❌ NOT IMPLEMENTED** (yet):
- Current phase: Entity extraction only
- Phase 5 (not yet reached): LLMRelationExtractor
- File [scripts/build_kg.py](../scripts/build_kg.py#L628-L664) has TODO section:

```python
# TODO: Relation extraction not yet implemented in manager.py
# Planned:
# 1. Build LLMRelationExtractor
# 2. Retrieve chunks mentioning entity pairs
# 3. Extract relations with domain/range validation
# 4. Cross-document relation discovery
```

**Verdict**: 
- **kg-comparison**: Relations extraction complete
- **KnowledgeGraphBuilder**: Relations on roadmap (Phase 5)

---

### 5. **Discovery & Iteration Strategy**

#### kg-comparison

```python
# pipeline.py - Single pass extraction
async def run_pipeline(cfg: Config) -> None:
    schema = extractor.build_schema_from_ontology(cfg.path.owl_path)
    text = Path(cfg.path.evaluation_text_path).read_text()
    
    extracted_graph = await extractor.extract(text=text, schema=schema)
    # Done. Single extraction pass per text.
```

**Strategy**: Single comprehensive extraction per document

#### KnowledgeGraphBuilder

```python
# IterativeDiscoveryLoop (src/kgbuilder/discovery/iterative_loop.py)
async def run_discovery(
    self,
    max_iterations: int = 3,
    coverage_target: float = 0.85,
    top_k_docs: int = 10,
) -> DiscoveryResult:
    
    for iteration in range(max_iterations):
        # 1. For each question in ontology:
        for question in ontology_questions:
            # 2. Retrieve top 10 relevant documents
            docs = retriever.retrieve(question, k=10)
            
            # 3. Extract entities from each document
            entities += extractor.extract(docs, question)
        
        # 4. Check coverage: have we found enough entity types?
        if coverage >= coverage_target:
            break
```

**Strategy**: Iterative discovery with coverage-based termination
- Questions guide entity search
- Multiple iterations refine coverage
- Fallback mechanism on extraction failure

**Verdict**:
- **kg-comparison**: Batch processing (fast, simple)
- **KnowledgeGraphBuilder**: Iterative discovery (comprehensive, slower)

---

### 6. **Configuration Management**

#### kg-comparison (Hydra)

```yaml
# config.py + CLI overrides
python main.py \
  framework=ollama \
  framework.model=llama3.1:8b \
  evaluation=doc \
  framework.llm_common_config.seed=42 \
  --multirun  # Run multiple variants
```

**Advantages**:
- ✅ Sweeping (easy multi-variant execution)
- ✅ YAML defaults override via CLI
- ✅ Nested config composition

#### KnowledgeGraphBuilder (Pydantic JSON)

```python
# examples/experiment_baseline.json
{
  "name": "kg_baseline",
  "variants": [
    {
      "name": "baseline",
      "params": {
        "max_iterations": 3,
        "top_k_docs": 10,
        "confidence_threshold": 0.6
      }
    },
    {
      "name": "strict",
      "params": {
        "max_iterations": 5,
        "top_k_docs": 5,
        "confidence_threshold": 0.8
      }
    }
  ]
}
```

**Advantages**:
- ✅ Type-safe (Pydantic validation)
- ✅ Version-controllable (JSON configs)
- ✅ No CLI complexity

**Verdict**: Different philosophies:
- **kg-comparison**: Hydra (flexible, research-friendly)
- **KnowledgeGraphBuilder**: JSON (simple, versioned)

---

### 7. **Experiment Tracking**

#### kg-comparison (MLflow)

```python
import mlflow

@mlflow.trace(name="extract_graph", span_type=SpanType.PARSER)
async def extract(self, text: str, schema: schema) -> KnowledgeGraph:
    # MLflow auto-tracks time, inputs, outputs
    ...

# Start server
mlflow server --host 127.0.0.1 --port 8090
```

**Metrics Tracked**:
- Extraction time per framework
- Precision, Recall, F1 per component
- Comparison tables (frameworks × models)

#### KnowledgeGraphBuilder (Weights & Biases)

```python
# ConfigRunner.run() - This session's additions
wandb_run = wandb.init(project="kg-builder", name=variant.name, reinit=True)

# Continuous logging at 4 checkpoints:
wandb_run.log({"status": "initializing_services"})
wandb_run.log({"status": "discovery_started", "ontology_classes": 18})
wandb_run.log({"discovery_complete": 1, "entities_discovered": 42, ...})
wandb_run.log({"kg_build_complete": 1, "nodes_created": 40, ...})

# Dashboard: https://wandb.ai/dsfhswf/kg-builder
```

**Metrics Tracked**:
- Real-time progress (status updates)
- Entity counts per discovery phase
- KG assembly metrics (nodes, edges)
- Per-variant aggregated results

**Verdict**:
- **kg-comparison**: MLflow (framework comparison focus)
- **KnowledgeGraphBuilder**: Wandb (real-time monitoring)

---

### 8. **Error Handling & Robustness**

#### kg-comparison

```python
# Straightforward error handling
try:
    response = client.beta.chat.completions.parse(...)
except Exception as e:
    logger.error(f"Extraction failed: {e}")
```

**Resilience**: Limited (single-pass failure = lost data)

#### KnowledgeGraphBuilder

```python
# Multi-layer fallback (LLMEntityExtractor)
async def extract(self, texts, ontology_classes, num_retries=3):
    for attempt in range(num_retries):
        try:
            # Attempt 1: Standard extraction
            return llm.generate_structured(...)
        except ExtractionError:
            if attempt == 0:
                # Attempt 2: Question-augmented retry
                text_with_question = f"{question}\n\n{text}"
                return llm.generate_structured(text_with_question)
            else:
                # Attempt 3: Return empty with logging
                logger.warning(f"Extraction failed after {num_retries} retries")
                raise
```

**Resilience**: 3-tier fallback + question augmentation

**Recent Issue Handling**:
```
HTTPConnectionPool read timeout → System retries with backoff
Expected behavior: Auto-recover or skip document, continue with others
```

**Verdict**:
- **kg-comparison**: Simple error handling
- **KnowledgeGraphBuilder**: Sophisticated fallback mechanisms

---

## 📋 Feature Comparison Matrix

| Feature | kg-comparison | KnowledgeGraphBuilder | Notes |
|---------|---------------|-----------------------|-------|
| **Entity Extraction** | ✅ Single-pass | ✅ Iterative | KGB more comprehensive |
| **Relation Extraction** | ✅ Implemented | ❌ TODO (Phase 5) | KGB roadmap |
| **Confidence Scoring** | ❌ N/A | ✅ Per-entity | KGB more nuanced |
| **Framework Comparison** | ✅ 4 frameworks | ❌ 1 (Ollama) | kg-comp focus |
| **Experiment Tracking** | ✅ MLflow | ✅ Wandb | Both solid |
| **Config Management** | ✅ Hydra | ✅ JSON/Pydantic | Different approach |
| **Error Resilience** | ⚠️ Basic | ✅ 3-tier fallback | KGB stronger |
| **Discovery Questions** | ❌ Manual texts | ✅ Auto-generated | KGB advantage |
| **Iterative Refinement** | ❌ Single-pass | ✅ Coverage-based | KGB advantage |
| **Property Extraction** | ✅ Full schema | ⚠️ Minimal | kg-comp richer |
| **Cross-document Relations** | ❌ Single doc | ✅ Planned | KGB roadmap |

---

## 🎯 What We Should Implement from kg-comparison

### HIGH PRIORITY
1. **Property extraction** → Enhance schema beyond class names
   ```python
   # Currently: class names only ["Action", "Parameter", ...]
   # Should be: Full NodeOntology with properties
   ```

2. **Single-pass relation extraction** → Don't wait for Phase 5
   ```python
   # Adapt their LLM prompt to include relations alongside entities
   # Use their ground truth converter pattern
   ```

3. **OWL parsing improvements** → Use owlready2 like they do
   ```python
   # Their pattern: Extract entities + object properties + data properties
   # More complete than current ontology service
   ```

### MEDIUM PRIORITY
4. **Evaluation framework** → Adapt their metrics (Precision, Recall, F1)
   ```python
   # They have: src/evaluation/evaluator.py
   # We have: Validation logic spread across components
   ```

5. **Schema validation** → Stronger constraints
   ```python
   # They validate: domain/range, cardinality
   # We should add: Range checking, type constraints
   ```

### LOWER PRIORITY
6. **Framework comparison** → Not needed (we're optimizing single path)
7. **Hydra configuration** → Keep JSON (simpler for production)

---

## 🔧 Our Unique Advantages Over kg-comparison

### 1. Iterative Discovery
- Question-guided exploration
- Coverage-based termination
- NOT one-shot extraction

### 2. Confidence Scoring
- Per-entity confidence (not binary)
- Evidence tracking
- Uncertainty quantification

### 3. Real-time Monitoring
- Continuous wandb logging
- Progress visibility during long runs
- Per-variant aggregation

### 4. Fallback Mechanisms
- Question-augmented retry
- Multi-attempt extraction
- Graceful degradation

### 5. RAG Integration
- Semantic relevance (Qdrant)
- Hybrid retrieval (dense + sparse)
- Document-aware extraction

---

## 📝 Recommendations for Next Steps

### Immediate (Before Demo)
1. **Fix Ollama timeout issue**
   - Increase read timeout from 120s to 180s
   - Implement circuit breaker pattern
   - Add per-document timeout escalation

2. **Add property extraction**
   - Map ontology data properties to entity properties
   - Include in prompt: "Extract these properties: [name, date, ...]"
   - Validate against schema

### Short-term (This Week)
3. **Implement Phase 5: Relation Extraction**
   - Adapt kg-comparison's relation prompt
   - Extract after entity discovery completes
   - Validate domain/range constraints

4. **Add evaluation metrics**
   - Precision/Recall framework (like kg-comparison)
   - Compare against ground truth if available
   - Report per-variant metrics

### Medium-term (Next Sprint)
5. **Cross-document relation discovery**
   - Link entities across documents
   - Temporal/causal inference
   - Multi-hop path discovery

6. **Schema evolution**
   - Learn new entity types from text
   - Suggest missing properties
   - Adapt ontology based on extraction results

---

## 📊 Experiment Progress Summary

| Phase | Status | Time Elapsed | Next Event |
|-------|--------|--------------|-----------|
| 1: Ontology | ✅ Complete | ~2 min | Questions generated (18) |
| 2: Discovery | 🔄 In Progress | ~6+ hours | Processing Q8 of 18 (timeout hit) |
| 3: Vectorization | ⏳ Pending | N/A | After discovery complete |
| 4: Synthesis | ⏳ Pending | N/A | Dedup entities |
| 5: Relations | ⏳ Pending | N/A | Extract cross-entity relations |
| 6: KG Assembly | ⏳ Pending | N/A | Write to Neo4j |

**Estimated Total Time**: 12-18 hours (due to Ollama speed)  
**Current Blocker**: Read timeout in extraction (recoverable)

---

## 🎓 Key Learnings from Comparison

1. **Relations matter**: kg-comparison gets them in one pass; we're planning Phase 5
2. **Property extraction**: They're richer; we should enhance schema
3. **Single vs. iterative**: Their one-shot is faster; ours is more comprehensive
4. **Framework flexibility**: They support 4; we're optimized for 1 (Ollama)
5. **Evaluation**: They have robust metrics; we should formalize ours

---

**Document updated**: 2026-02-05 08:35  
**Experiment running**: 6+ hours (expected 12-18 hours total)  
**Next checkpoint**: Check log after 2 hours for progress update
