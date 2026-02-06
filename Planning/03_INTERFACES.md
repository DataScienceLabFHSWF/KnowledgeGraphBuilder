# Interface Definitions

## All Service Protocols, Data Models & Interactions

**Last Updated**: February 6, 2026

---

## 1. Core Data Models

### 1.1 Document Processing

```python
@dataclass
class Document:
    id: str
    content: str
    metadata: DocumentMetadata
    source_path: Path
    file_type: FileType       # PDF, DOCX, PPTX, TXT, MD
    chunks: list[Chunk] = field(default_factory=list)

@dataclass
class Chunk:
    id: str
    content: str
    document_id: str
    start_char: int
    end_char: int
    metadata: ChunkMetadata   # position, overlap, token_count

@dataclass
class Evidence:
    source_type: str          # "document", "web", "user"
    source_id: str            # chunk_id or URL
    text_span: str
    confidence: float
```

### 1.2 Ontology Models

```python
@dataclass
class OntologyClassDef:
    uri: str                       # e.g. "http://example.org/ontology#Facility"
    label: str                     # "Facility"
    description: str
    examples: list[str]
    parent_uri: str | None
    properties: list[OntologyPropertyDef]

@dataclass
class OntologyPropertyDef:
    name: str
    data_type: str                 # "string", "integer", "date", etc.
    description: str
    required: bool
    examples: list[str]

@dataclass
class OntologyRelationDef:
    uri: str
    label: str
    description: str
    domain: list[str]              # Source entity types (URIs)
    range: list[str]               # Target entity types (URIs)
    is_functional: bool            # At most one value
    is_inverse_functional: bool
    is_transitive: bool
    is_symmetric: bool
    examples: list[tuple[str, str]]
```

### 1.3 Extraction Models (Pydantic — LLM Output)

```python
class EntityItem(BaseModel):
    id: str
    label: str
    entity_type: str
    confidence: float
    start_char: int
    end_char: int
    context: str

class EntityExtractionOutput(BaseModel):
    entities: list[EntityItem]

class RelationItem(BaseModel):
    id: str
    source_id: str
    source_label: str
    relation_type: str
    target_id: str
    target_label: str
    confidence: float

class RelationExtractionOutput(BaseModel):
    relations: list[RelationItem]

class FindingItem(BaseModel):
    id: str
    finding_type: str
    summary: str
    entities: list[str]
    confidence: float

class FindingsSynthesisOutput(BaseModel):
    findings: list[FindingItem]
```

### 1.4 KG Entities & Relations (Internal)

```python
@dataclass
class ExtractedEntity:
    id: str
    label: str
    entity_type: str
    description: str
    confidence: float
    evidence: list[Evidence]
    aliases: list[str]
    properties: dict[str, Any]

@dataclass
class SynthesizedEntity:
    id: str
    label: str
    entity_type: str
    description: str
    confidence: float
    evidence: list[Evidence]
    merged_from: list[str]         # IDs of source ExtractedEntity objects
    merge_count: int

@dataclass
class ExtractedRelation:
    id: str
    source_entity_id: str
    target_entity_id: str
    predicate: str
    confidence: float
    evidence: list[Evidence]
```

### 1.5 Graph Models

```python
@dataclass
class Node:
    id: str
    label: str
    node_type: str
    properties: dict[str, Any]
    metadata: dict[str, Any]

@dataclass
class Edge:
    id: str
    source_id: str
    target_id: str
    edge_type: str
    properties: dict[str, Any]
    metadata: dict[str, Any]

@dataclass
class SearchResult:
    id: str
    score: float
    metadata: dict[str, Any]
    content: str | None
```

### 1.6 Validation Models

```python
class ViolationSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class ConflictType(Enum):
    TYPE = "type"
    VALUE = "value"
    TRANSITIVE = "transitive"
    CARDINALITY = "cardinality"
    DOMAIN_RANGE = "domain_range"

@dataclass
class ValidationViolation:
    severity: ViolationSeverity
    path: str
    message: str
    value: Any
    expected: Any
    focus_node: str
    shape_uri: str | None

@dataclass
class RuleViolation:
    rule_name: str
    rule_description: str
    subject_id: str
    predicate: str
    object_id: str
    reason: str
    recommendation: str

@dataclass
class Conflict:
    conflict_type: ConflictType
    entity_id: str
    details: dict[str, Any]

@dataclass
class ValidationResult:
    violations: list[ValidationViolation]
    passed: bool
    total_checks: int
    pass_rate: float
```

### 1.7 LLM Models

```python
class MessageRole(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"

@dataclass
class Message:
    role: MessageRole
    content: str
    tool_calls: list[ToolCall] | None = None

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]

@dataclass
class GenerationConfig:
    temperature: float = 0.7
    top_p: float = 0.9
    max_tokens: int = 2048
    stop_sequences: list[str] = field(default_factory=list)
    response_format: str | None = None
```

---

## 2. Service Protocols

### 2.1 Document Loading

```python
@runtime_checkable
class DocumentLoader(Protocol):
    def load(self, path: Path) -> Document: ...
    def supported_extensions(self) -> list[str]: ...
    def load_batch(self, paths: list[Path]) -> list[Document]: ...

@runtime_checkable
class ChunkingStrategy(Protocol):
    def chunk(
        self,
        document: Document,
        chunk_size: int = 512,
        overlap: int = 50,
    ) -> list[Chunk]: ...
```

**Implementations**: `PDFLoader`, `OfficeLoader`, `TextLoader`, `MarkdownLoader`  
**Chunking**: `FixedSizeChunker`, `SemanticChunker`, `StructuralChunker`, `HierarchicalChunker`

### 2.2 Embedding & Vector Store

```python
@runtime_checkable
class EmbeddingProvider(Protocol):
    def embed_text(self, text: str) -> NDArray[np.float32]: ...
    def embed_batch(self, texts: list[str]) -> list[NDArray[np.float32]]: ...
    @property
    def model_name(self) -> str: ...
    @property
    def dimension(self) -> int: ...

@runtime_checkable
class VectorStore(Protocol):
    def add(self, records: list[VectorRecord]) -> list[str]: ...
    def search(
        self,
        query_vector: NDArray[np.float32],
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]: ...
    def hybrid_search(
        self,
        query_text: str,
        query_vector: NDArray[np.float32],
        limit: int = 10,
    ) -> list[SearchResult]: ...
    def get(self, record_id: str) -> VectorRecord | None: ...
    def delete(self, record_ids: list[str]) -> int: ...
    def count(self) -> int: ...
```

**Implementations**: `QdrantVectorStore` (primary), `ChromaVectorStore` (dev)

### 2.3 LLM Provider

```python
@runtime_checkable
class LLMProvider(Protocol):
    @property
    def model_name(self) -> str: ...

    def generate(self, prompt: str, **kwargs: Any) -> str: ...

    def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        max_retries: int = 3,
        **kwargs: Any,
    ) -> Any: ...

    def chat(
        self,
        messages: list[Message],
        config: GenerationConfig | None = None,
    ) -> Message: ...
```

**Implementation**: `OllamaProvider`
- Connects to Ollama REST API (default: `http://localhost:11434`)
- Models: Qwen3, Llama3.1, etc.
- `generate_structured()`: JSON output with Pydantic validation, retry with error feedback, JSON recovery strategies
- `embed_query()`: 384-dim embeddings via `qwen3-embedding`
- Class-level token counters for cost tracking

### 2.4 Entity Extraction

```python
@runtime_checkable
class EntityExtractor(Protocol):
    def extract(
        self,
        text: str,
        ontology_classes: list[OntologyClassDef],
        existing_entities: list[ExtractedEntity] | None = None,
    ) -> list[ExtractedEntity]: ...
```

**Implementation**: `LLMEntityExtractor`
- Constructor: `(llm_provider: LLMProvider, confidence_threshold=0.5, max_retries=3)`
- Builds ontology-guided prompt with class definitions, examples, and existing entities
- Calls `llm.generate_structured(prompt, EntityExtractionOutput)`
- Handles arithmetic expressions in LLM output (e.g., `266 - 12 + 8`)
- Deduplicates by label+type key

### 2.5 Relation Extraction

```python
@runtime_checkable
class RelationExtractor(Protocol):
    def extract(
        self,
        text: str,
        entities: list[ExtractedEntity],
        ontology_relations: list[OntologyRelationDef],
    ) -> list[ExtractedRelation]: ...
```

**Implementation**: `LLMRelationExtractor`
- Uses `ExtractionChains` (LangChain LCEL) for structured LLM calls
- Validates domain/range: source entity type ∈ relation.domain, target ∈ relation.range
- Checks cardinality: functional properties allow at most one object per subject
- Deduplicates by `(source_id, predicate, target_id)` key

### 2.6 Graph Store

```python
@runtime_checkable
class GraphStore(Protocol):
    def add_node(self, node: Node) -> str: ...
    def add_edge(self, edge: Edge) -> str: ...
    def get_node(self, node_id: str) -> Node | None: ...
    def get_neighbors(self, node_id: str, edge_type: str | None = None) -> list[Node]: ...
    def query(self, query_str: str) -> list[dict[str, Any]]: ...
    def get_subgraph(self, node_ids: list[str], depth: int = 1) -> tuple[list[Node], list[Edge]]: ...
    def export(self, format: str) -> str: ...
    def statistics(self) -> dict[str, Any]: ...
    def clear(self) -> None: ...
```

**Implementation**: `Neo4jGraphStore`
- Cypher query execution
- Batch node/edge insertion
- Subgraph extraction for RAG

### 2.7 RDF Store

```python
@runtime_checkable
class RDFStore(Protocol):
    def load_ontology(self, path: Path) -> None: ...
    def add_triples(self, triples: list[tuple[str, str, str]]) -> int: ...
    def query_sparql(self, query: str) -> list[dict[str, Any]]: ...
    def serialize(self, format: str = "turtle") -> str: ...
```

**Implementation**: `FusekiRDFStore`
- SPARQL 1.1 queries via HTTP
- Ontology loading (OWL/RDF)
- TBox (schema) / ABox (instances) separation

### 2.8 Validation

```python
@runtime_checkable
class Validator(Protocol):
    def validate(self, graph: GraphStore) -> ValidationReport: ...

@dataclass
class ValidationReport:
    passed: bool
    violations: list[ValidationViolation]
    summary: dict[str, Any]
```

**Implementations**:
- `SHACLValidator` — Converts GraphStore → RDF → validates with pyshacl
- `OntologyValidator` — Checks class/relation conformance
- `CompetencyQuestionValidator` — Tests if CQs are answerable from the KG
- `RulesEngine` — Executes semantic rules (inverse, transitive, domain/range, functional)
- `ConsistencyChecker` — Detects conflicts (type, value, cardinality, transitive chain)

### 2.9 Experiment Framework

```python
@dataclass
class ExperimentConfig:
    name: str
    description: str
    output_dir: Path
    variants: list[ConfigVariant]
    evaluation: EvaluationConfig
    parallel_jobs: int = 1

@dataclass
class ConfigVariant:
    name: str
    description: str
    params: KGBuilderParams       # model, max_iterations, thresholds, etc.

@dataclass
class KGBuilderParams:
    model: str = "qwen3"
    max_iterations: int = 5
    confidence_threshold: float = 0.5
    chunk_size: int = 512
    top_k: int = 10
```

**Key classes**:
- `ExperimentManager` — Orchestrates multi-variant experiment runs (async parallel)
- `ConfigRunner` — Executes a single configuration variant
- `CheckpointManager` — Saves/loads extraction results as JSON
- `ExperimentAnalyzer` — Convergence analysis, comparative statistics
- `ExperimentPlotter` — Visualization (matplotlib/plotly)
- `ExperimentReporter` — Multi-format report generation (Markdown/JSON/HTML)

---

## 3. Service Interaction Diagram

```
                           ┌───────────────────┐
                           │  CLI / Scripts     │
                           │  (Typer entry)     │
                           └─────────┬─────────┘
                                     │
                           ┌─────────▼─────────┐
                           │  ExperimentManager │
                           │  or BuildPipeline  │
                           └─────────┬─────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              ▼                      ▼                      ▼
   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
   │  DocumentLoader   │  │  OntologyService │  │  CheckpointMgr   │
   │  → Chunks         │  │  (Fuseki/OWL)    │  │  (JSON save/load)│
   └────────┬─────────┘  └────────┬─────────┘  └──────────────────┘
            │                      │
            ▼                      ▼
   ┌──────────────────┐  ┌──────────────────┐
   │  EmbeddingProvider│  │  QuestionGenerator│
   │  (Ollama)        │  │  (CQ → questions)│
   └────────┬─────────┘  └────────┬─────────┘
            │                      │
            ▼                      ▼
   ┌──────────────────┐  ┌──────────────────┐
   │  VectorStore      │  │  DiscoveryLoop   │
   │  (Qdrant)        │◀─│  (orchestrator)  │
   └──────────────────┘  └────────┬─────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼                              ▼
         ┌──────────────────┐           ┌──────────────────┐
         │  EntityExtractor  │           │  RelationExtractor│
         │  (LLM + schema)  │           │  (LLM + ontology) │
         └────────┬─────────┘           └────────┬─────────┘
                  │                               │
                  └───────────┬───────────────────┘
                              ▼
                   ┌──────────────────┐
                   │  Synthesizer     │
                   │  (dedup, merge)  │
                   └────────┬─────────┘
                            ▼
                   ┌──────────────────┐
                   │  Enrichment      │
                   │  Pipeline        │
                   └────────┬─────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
   │  Neo4j       │ │  Qdrant      │ │  Fuseki      │
   │  GraphStore  │ │  VectorStore │ │  RDFStore    │
   └──────┬───────┘ └──────────────┘ └──────────────┘
          │
          ▼
   ┌──────────────────┐
   │  Validation       │
   │  SHACL + Rules    │
   │  + Consistency    │
   └──────┬───────────┘
          ▼
   ┌──────────────────┐
   │  Evaluation       │
   │  QA + Metrics     │
   └──────────────────┘
```

---

## 4. Semantic Rules (Validation)

```python
class SemanticRule(ABC):
    name: str
    description: str
    enabled: bool = True

    @abstractmethod
    def check(self, store: GraphStore) -> list[RuleViolation]: ...

# Concrete rules:
class InversePropertyRule(SemanticRule):
    """If (A, property, B) exists, ensure (B, inverse_property, A) exists."""

class TransitiveRule(SemanticRule):
    """If (A, prop, B) and (B, prop, C), ensure (A, prop, C) exists."""

class DomainRangeRule(SemanticRule):
    """Ensure source type ∈ domain and target type ∈ range."""

class FunctionalPropertyRule(SemanticRule):
    """Ensure at most one value per subject for functional properties."""
```

---

## 5. Stopping Criteria

```python
@dataclass
class StoppingCriteria:
    max_iterations: int = 5
    min_cq_coverage: float = 0.8
    min_validation_pass_rate: float = 0.9
    min_avg_confidence: float = 0.6
    marginal_gain_threshold: float = 0.01
    graph_stability_threshold: float = 0.95

class StoppingReason(Enum):
    MAX_ITERATIONS = "max_iterations"
    CQ_COVERAGE_MET = "cq_coverage_met"
    VALIDATION_PASS_RATE_MET = "validation_pass_rate_met"
    MARGINAL_GAIN_BELOW_THRESHOLD = "marginal_gain_below_threshold"
    GRAPH_STABLE = "graph_stable"
    ALL_CRITERIA_MET = "all_criteria_met"
    USER_STOPPED = "user_stopped"
    ERROR = "error"
    TIMEOUT = "timeout"
```
