# 📋 KnowledgeGraphBuilder – Issues Backlog

> **Purpose**: Track all features, tasks, and milestones for the KG construction pipeline.  
> **Status Legend**: `[ ]` Not Started | `[~]` In Progress | `[x]` Done

---

## 🏗️ Epic 1: Core Infrastructure & Project Setup

### Issue #1.1: Project Scaffolding
**Priority**: 🔴 Critical | **Estimate**: 2h

- [ ] Initialize Python project structure with `pyproject.toml`
- [ ] Set up virtual environment management (uv/poetry)
- [ ] Create base directory structure:
  ```
  /src
    /kgbuilder
      /core           # Shared abstractions & interfaces
      /document       # Document processing module
      /embedding      # Embedding & vector operations
      /extraction     # Entity/relation extraction
      /assembly       # KG assembly & merging
      /validation     # SHACL & ontology validation
      /storage        # Database connectors
      /agents         # Agent orchestration
      /config         # Configuration management
  /tests
  /scripts
  /docs
  ```
- [ ] Configure logging framework (structlog)
- [ ] Set up pre-commit hooks (ruff, black, mypy)

**Acceptance Criteria**:
- `pip install -e .` works
- All modules importable
- CI/CD skeleton in place

---

### Issue #1.2: Configuration Management
**Priority**: 🔴 Critical | **Estimate**: 3h

- [ ] Implement hierarchical config system (YAML + env vars)
- [ ] Define configuration schema with Pydantic
- [ ] Support multiple environments (dev, test, prod)
- [ ] Configuration for:
  - LLM endpoints (Ollama)
  - Database connections
  - Processing parameters
  - Agent settings

**Acceptance Criteria**:
- Config validation on startup
- Secrets loaded from environment
- Type-safe config access

---

### Issue #1.3: Dependency Injection Container
**Priority**: 🟡 Medium | **Estimate**: 4h

- [ ] Implement lightweight DI container
- [ ] Register all services with interfaces
- [ ] Support lazy initialization
- [ ] Enable easy mocking for tests

**Acceptance Criteria**:
- All components resolve via DI
- No hard-coded dependencies
- Test doubles easily injectable

---

## 📄 Epic 2: Document Processing Pipeline

### Issue #2.1: Document Ingestion Interface
**Priority**: 🔴 Critical | **Estimate**: 4h

- [ ] Define `DocumentLoader` protocol/interface
- [ ] Implement base document model:
  ```python
  @dataclass
  class Document:
      id: str
      content: str
      metadata: DocumentMetadata
      source_path: Path
      file_type: FileType
      chunks: list[Chunk] = field(default_factory=list)
  ```
- [ ] Support file types: PDF, DOCX, PPTX, TXT, MD
- [ ] Implement factory pattern for loader selection

**Acceptance Criteria**:
- Unified interface for all document types
- Metadata extracted consistently
- Extensible for new formats

---

### Issue #2.2: PDF Document Loader
**Priority**: 🔴 Critical | **Estimate**: 6h

- [ ] Implement `PDFLoader` using `pdfplumber` / `PyMuPDF`
- [ ] Extract text with layout preservation
- [ ] Handle multi-column layouts
- [ ] Extract tables as structured data
- [ ] Extract images with OCR fallback (optional)
- [ ] Preserve page numbers in metadata

**Acceptance Criteria**:
- Clean text extraction from academic papers
- Tables converted to structured format
- Page-level provenance maintained

---

### Issue #2.3: Office Document Loaders
**Priority**: 🟡 Medium | **Estimate**: 4h

- [ ] Implement `DOCXLoader` using `python-docx`
- [ ] Implement `PPTXLoader` using `python-pptx`
- [ ] Preserve document structure (headings, lists)
- [ ] Extract embedded tables
- [ ] Handle speaker notes (PPTX)

**Acceptance Criteria**:
- Structural elements preserved
- Consistent output format

---

### Issue #2.4: Chunking Strategy System
**Priority**: 🔴 Critical | **Estimate**: 6h

- [ ] Define `ChunkingStrategy` protocol
- [ ] Implement strategies:
  - `FixedSizeChunker` (token-based with overlap)
  - `SemanticChunker` (sentence/paragraph boundaries)
  - `StructuralChunker` (section-based)
  - `HierarchicalChunker` (nested chunks)
- [ ] Chunk metadata:
  ```python
  @dataclass
  class Chunk:
      id: str
      content: str
      document_id: str
      start_char: int
      end_char: int
      metadata: ChunkMetadata  # section, page, etc.
  ```
- [ ] Configurable chunk size and overlap

**Acceptance Criteria**:
- Strategies swappable via config
- Provenance fully traceable
- Chunks respect semantic boundaries

---

## 🧠 Epic 3: Embedding & Vector Operations

### Issue #3.1: Embedding Provider Interface
**Priority**: 🔴 Critical | **Estimate**: 3h

- [ ] Define `EmbeddingProvider` protocol:
  ```python
  class EmbeddingProvider(Protocol):
      def embed_text(self, text: str) -> np.ndarray: ...
      def embed_batch(self, texts: list[str]) -> np.ndarray: ...
      @property
      def dimension(self) -> int: ...
      @property
      def model_name(self) -> str: ...
  ```
- [ ] Implement `OllamaEmbeddingProvider`
- [ ] Support model switching (nomic-embed, mxbai, etc.)
- [ ] Implement caching layer for embeddings

**Acceptance Criteria**:
- Ollama integration working
- Batch processing efficient
- Model-agnostic interface

---

### Issue #3.2: Vector Database Abstraction
**Priority**: 🔴 Critical | **Estimate**: 6h

- [ ] Define `VectorStore` protocol:
  ```python
  class VectorStore(Protocol):
      def add(self, embeddings: np.ndarray, metadata: list[dict]) -> list[str]: ...
      def search(self, query: np.ndarray, top_k: int, filters: dict | None) -> list[SearchResult]: ...
      def delete(self, ids: list[str]) -> None: ...
      def get(self, ids: list[str]) -> list[dict]: ...
  ```
- [ ] Implement `ChromaDBStore` (recommended for local dev)
- [ ] Implement `QdrantStore` (recommended for production)
- [ ] Implement `MilvusStore` (alternative)
- [ ] Support metadata filtering

**Acceptance Criteria**:
- Stores swappable via config
- Hybrid search support (dense + sparse)
- Persistence and recovery

---

### Issue #3.3: Document Indexing Service
**Priority**: 🔴 Critical | **Estimate**: 4h

- [ ] Implement `IndexingService` orchestrator
- [ ] Pipeline: Load → Chunk → Embed → Store
- [ ] Incremental indexing (skip already indexed)
- [ ] Index statistics and monitoring

**Acceptance Criteria**:
- End-to-end document indexing
- Idempotent operations
- Progress reporting

---

## 🔍 Epic 4: LLM Integration & Agent Framework

### Issue #4.1: LLM Provider Interface
**Priority**: 🔴 Critical | **Estimate**: 4h

- [ ] Define `LLMProvider` protocol:
  ```python
  class LLMProvider(Protocol):
      def generate(self, prompt: str, **kwargs) -> str: ...
      def generate_structured(self, prompt: str, schema: Type[T]) -> T: ...
      def chat(self, messages: list[Message]) -> Message: ...
      @property
      def supports_tools(self) -> bool: ...
  ```
- [ ] Implement `OllamaProvider`
- [ ] Support streaming responses
- [ ] Implement retry logic with exponential backoff
- [ ] Token counting and budget management

**Acceptance Criteria**:
- Structured output via JSON mode
- Tool calling support
- Error handling robust

---

### Issue #4.2: Tool Framework for Agents
**Priority**: 🔴 Critical | **Estimate**: 6h

- [ ] Define `Tool` protocol:
  ```python
  class Tool(Protocol):
      name: str
      description: str
      parameters: dict  # JSON Schema
      def execute(self, **kwargs) -> ToolResult: ...
  ```
- [ ] Implement core tools:
  - `VectorSearchTool` - Search indexed documents
  - `OntologyQueryTool` - Query ontology structure
  - `KGQueryTool` - Query current KG state
  - `ValidationTool` - Run SHACL validation
- [ ] Tool result formatting for LLM consumption
- [ ] Tool execution logging

**Acceptance Criteria**:
- Tools auto-discovered and registered
- Schema-validated inputs
- Full execution traces

---

### Issue #4.3: Base Agent Framework
**Priority**: 🔴 Critical | **Estimate**: 8h

- [ ] Define `Agent` base class:
  ```python
  class Agent(ABC):
      def __init__(self, llm: LLMProvider, tools: list[Tool]): ...
      @abstractmethod
      def run(self, input: AgentInput) -> AgentOutput: ...
      def reason(self, context: str) -> str: ...
      def act(self, action: Action) -> ActionResult: ...
  ```
- [ ] Implement ReAct-style reasoning loop
- [ ] Support multi-turn conversations
- [ ] Agent state management
- [ ] Implement agent execution traces

**Acceptance Criteria**:
- Agents composable
- Full observability
- Graceful error recovery

---

### Issue #4.4: Agent Orchestration System
**Priority**: 🟡 Medium | **Estimate**: 8h

- [ ] Define `Pipeline` abstraction for agent workflows
- [ ] Implement DAG-based orchestration
- [ ] Support parallel agent execution
- [ ] Implement checkpointing for long-running pipelines
- [ ] Agent communication via message passing

**Acceptance Criteria**:
- Complex workflows definable
- Resume from checkpoints
- Resource management

---

## 🔬 Epic 5: Knowledge Extraction

### Issue #5.1: Entity Extraction Interface
**Priority**: 🔴 Critical | **Estimate**: 4h

- [ ] Define extraction result models:
  ```python
  @dataclass
  class ExtractedEntity:
      id: str
      label: str
      type: str  # Ontology class
      description: str
      confidence: float
      evidence: list[Evidence]
  
  @dataclass
  class ExtractedRelation:
      id: str
      source_entity_id: str
      target_entity_id: str
      predicate: str  # Ontology relation
      confidence: float
      evidence: list[Evidence]
  ```
- [ ] Define `Extractor` protocol
- [ ] Support ontology-constrained extraction

**Acceptance Criteria**:
- Extraction tied to ontology
- Provenance always captured
- Confidence scores meaningful

---

### Issue #5.2: LLM-Based Entity Extractor
**Priority**: 🔴 Critical | **Estimate**: 8h

- [ ] Implement `LLMEntityExtractor`
- [ ] Ontology-guided prompting:
  - Feed relevant ontology classes
  - Include class descriptions & constraints
  - Few-shot examples per class
- [ ] Multi-pass extraction for complex documents
- [ ] Entity deduplication within document

**Acceptance Criteria**:
- Extracts entities aligned to ontology
- Handles ambiguous mentions
- Coreference resolution

---

### Issue #5.3: LLM-Based Relation Extractor
**Priority**: 🔴 Critical | **Estimate**: 8h

- [ ] Implement `LLMRelationExtractor`
- [ ] Ontology-guided relation prompting:
  - Valid relations between entity types
  - Domain/range constraints
  - Cardinality hints
- [ ] Support n-ary relations via reification
- [ ] Confidence calibration

**Acceptance Criteria**:
- Relations respect ontology schema
- Handles implicit relations
- Symmetric/transitive handling

---

### Issue #5.4: Research Findings Synthesizer
**Priority**: 🟡 Medium | **Estimate**: 6h

- [ ] Implement `FindingsSynthesizer` (DeepResearch output)
- [ ] Output format:
  ```yaml
  finding_id: FR-0231
  ontology_concepts: [RootCause, CorrectiveAction]
  question: "What are common root causes?"
  claims:
    - text: "Root causes often categorized as..."
      confidence: 0.82
      evidence:
        - source_type: local_doc
          chunk_id: DOC-112-CH-7
  ```
- [ ] Aggregate evidence from multiple sources
- [ ] Conflict detection and resolution

**Acceptance Criteria**:
- Structured research output
- Evidence fully traceable
- Conflicts flagged

---

## 🏗️ Epic 6: KG Assembly & Storage

### Issue #6.1: KG Assembly Engine
**Priority**: 🔴 Critical | **Estimate**: 8h

- [ ] Implement `KGAssembler`:
  - Convert findings → nodes & edges
  - Entity resolution across documents
  - Merge duplicate entities
  - Attach provenance metadata
- [ ] Support incremental assembly
- [ ] Handle conflicting information

**Acceptance Criteria**:
- Clean entity resolution
- Full provenance chain
- Confidence propagation

---

### Issue #6.2: Graph Database Abstraction
**Priority**: 🔴 Critical | **Estimate**: 6h

- [ ] Define `GraphStore` protocol:
  ```python
  class GraphStore(Protocol):
      def add_node(self, node: Node) -> str: ...
      def add_edge(self, edge: Edge) -> str: ...
      def query(self, cypher: str) -> list[dict]: ...
      def get_subgraph(self, node_id: str, depth: int) -> Graph: ...
      def export(self, format: ExportFormat) -> str: ...
  ```
- [ ] Implement `Neo4jStore`
- [ ] Support transactions
- [ ] Implement graph traversal helpers

**Acceptance Criteria**:
- CRUD operations working
- Efficient traversals
- ACID compliance

---

### Issue #6.3: RDF/SPARQL Store Integration
**Priority**: 🟡 Medium | **Estimate**: 6h

- [ ] Implement `RDFStore` (Jena/Fuseki or Oxigraph)
- [ ] Support SPARQL queries
- [ ] Ontology loading and reasoning
- [ ] RDF serialization (Turtle, JSON-LD, N-Triples)

**Acceptance Criteria**:
- SPARQL endpoint functional
- Reasoning enabled
- Standard RDF formats

---

### Issue #6.4: KG Export Formats
**Priority**: 🟡 Medium | **Estimate**: 4h

- [ ] Implement export to:
  - **YARRRML** (for RML mapping)
  - **JSON-LD** (for web/API)
  - **RDF/Turtle** (for semantic web)
  - **Cypher** (for Neo4j import)
  - **GraphML** (for analysis tools)
- [ ] Schema-compliant exports
- [ ] Provenance preservation in exports

**Acceptance Criteria**:
- Round-trip capability
- Standards compliant
- Metadata preserved

---

## ✅ Epic 7: Validation Pipeline

### Issue #7.1: Ontology Validation Service
**Priority**: 🔴 Critical | **Estimate**: 6h

- [ ] Load and parse OWL ontology
- [ ] Extract validation rules:
  - Class hierarchy
  - Domain/range constraints
  - Cardinality restrictions
  - Property characteristics (functional, transitive, etc.)
- [ ] Validate extracted entities against ontology

**Acceptance Criteria**:
- OWL 2 support
- Clear violation reports
- Suggestion generation

---

### Issue #7.2: SHACL Validation Engine
**Priority**: 🔴 Critical | **Estimate**: 6h

- [ ] Implement `SHACLValidator`:
  ```python
  class SHACLValidator:
      def load_shapes(self, shapes_graph: Graph) -> None: ...
      def validate(self, data_graph: Graph) -> ValidationReport: ...
  ```
- [ ] Support core SHACL constraints
- [ ] Generate human-readable violation reports
- [ ] Severity levels (Violation, Warning, Info)

**Acceptance Criteria**:
- SHACL shapes loadable
- Clear violation reports
- Integration with KG assembly

---

### Issue #7.3: Competency Question Validation
**Priority**: 🟡 Medium | **Estimate**: 6h

- [ ] Implement `CQValidator`:
  - Load competency questions
  - Generate SPARQL from CQs
  - Execute against KG
  - Score coverage
- [ ] Report unanswerable CQs
- [ ] Trigger refinement for gaps

**Acceptance Criteria**:
- CQ → SPARQL translation
- Coverage metrics
- Gap identification

---

### Issue #7.4: Validation Orchestrator
**Priority**: 🟡 Medium | **Estimate**: 4h

- [ ] Implement `ValidationPipeline`:
  - Run all validators in sequence
  - Aggregate results
  - Generate unified report
- [ ] Configurable validation levels
- [ ] Fail-fast or collect-all modes

**Acceptance Criteria**:
- Single entry point
- Comprehensive reports
- CI/CD integration ready

---

## 🤖 Epic 8: Specialized Agents

### Issue #8.1: DeepResearch Agent
**Priority**: 🔴 Critical | **Estimate**: 10h

- [ ] Implement ontology-guided research agent
- [ ] Capabilities:
  - Query vector index
  - Synthesize findings
  - Identify gaps
  - Request additional research
- [ ] Iterative refinement loop
- [ ] Web search integration (optional, logged)

**Acceptance Criteria**:
- Produces structured findings
- Respects ontology scope
- Full audit trail

---

### Issue #8.2: KG Builder Agent
**Priority**: 🔴 Critical | **Estimate**: 8h

- [ ] Implement agent that orchestrates:
  - Entity extraction
  - Relation extraction
  - KG assembly
  - Deduplication
- [ ] Uses DeepResearch findings as input
- [ ] Incremental KG construction

**Acceptance Criteria**:
- End-to-end KG building
- Quality checkpoints
- Resumable

---

### Issue #8.3: Validation Agent
**Priority**: 🟡 Medium | **Estimate**: 6h

- [ ] Implement agent that:
  - Runs validation pipeline
  - Interprets violations
  - Suggests fixes
  - Triggers re-research for gaps
- [ ] Feedback loop to KG Builder

**Acceptance Criteria**:
- Autonomous validation
- Actionable suggestions
- Refinement triggering

---

### Issue #8.4: Question-Asking Agent
**Priority**: 🟡 Medium | **Estimate**: 6h

- [ ] Generate research questions from:
  - Competency questions
  - Ontology gaps
  - Validation failures
- [ ] Prioritize questions by coverage impact
- [ ] Adaptive question generation

**Acceptance Criteria**:
- Questions aligned to CQs
- Priority scoring
- Logged and versioned

---

## 📊 Epic 9: Evaluation Framework

### Issue #9.1: Extraction Evaluation
**Priority**: 🟡 Medium | **Estimate**: 4h

- [ ] Implement evaluation metrics:
  - Precision / Recall / F1 for entities
  - Precision / Recall / F1 for relations
  - Ontology alignment score
- [ ] Support gold-standard comparison
- [ ] Error analysis tooling

**Acceptance Criteria**:
- Standard metrics computed
- Per-class breakdowns
- Error categorization

---

### Issue #9.2: Graph Quality Metrics
**Priority**: 🟡 Medium | **Estimate**: 4h

- [ ] Implement graph analysis:
  - Node/edge counts
  - Degree distribution
  - Centrality measures
  - Community detection
  - Connected components
- [ ] Compare against expected ontology structure

**Acceptance Criteria**:
- Comprehensive graph stats
- Visualization support
- Anomaly detection

---

### Issue #9.3: Coverage Reporting
**Priority**: 🟡 Medium | **Estimate**: 3h

- [ ] Report coverage per:
  - Ontology class
  - Ontology relation
  - Competency question
  - Source document
- [ ] Identify over/under-represented areas

**Acceptance Criteria**:
- Visual coverage reports
- Drill-down capability
- Trend tracking

---

## 🔧 Epic 10: CLI & DevOps

### Issue #10.1: CLI Application
**Priority**: 🟡 Medium | **Estimate**: 6h

- [ ] Implement CLI with `typer`:
  ```bash
  kgbuilder ingest --source ./docs --config config.yaml
  kgbuilder extract --ontology ./ontology.owl
  kgbuilder validate --shapes ./shapes.ttl
  kgbuilder export --format jsonld --output ./kg.json
  kgbuilder evaluate --gold ./gold.json
  ```
- [ ] Progress bars and logging
- [ ] Dry-run mode

**Acceptance Criteria**:
- All operations via CLI
- Help documentation
- Exit codes meaningful

---

### Issue #10.2: Docker Containerization
**Priority**: 🟡 Medium | **Estimate**: 4h

- [ ] Create `Dockerfile` for application
- [ ] Create `docker-compose.yml` with:
  - KGBuilder service
  - Ollama service
  - Neo4j service
  - Vector DB service (Qdrant/Chroma)
- [ ] Volume mounts for data persistence

**Acceptance Criteria**:
- One-command startup
- Services interconnected
- Dev and prod configs

---

### Issue #10.3: Testing Infrastructure
**Priority**: 🔴 Critical | **Estimate**: 6h

- [ ] Set up pytest with fixtures
- [ ] Unit test coverage for core modules
- [ ] Integration tests with test containers
- [ ] Mock LLM responses for deterministic tests
- [ ] CI pipeline (GitHub Actions)

**Acceptance Criteria**:
- 80%+ coverage target
- Tests run in CI
- Fast feedback loop

---

## 📚 Epic 11: Documentation

### Issue #11.1: API Documentation
**Priority**: 🟡 Medium | **Estimate**: 4h

- [ ] Docstrings for all public APIs
- [ ] Generate API docs (mkdocs/sphinx)
- [ ] Usage examples per module

**Acceptance Criteria**:
- Hosted documentation
- Examples runnable
- Auto-generated from code

---

### Issue #11.2: Architecture Documentation
**Priority**: 🟡 Medium | **Estimate**: 3h

- [ ] System architecture diagrams
- [ ] Component interaction docs
- [ ] Data flow documentation
- [ ] Decision records (ADRs)

**Acceptance Criteria**:
- Visual architecture
- Rationale documented
- Onboarding-ready

---

---

## � Epic 12: Experiment Tracking & Comparison Framework

> **Research Goal**: Compare RAG architectures and measure impact of ontology/CQ evolution on KG quality and QA performance.

### Issue #12.1: Experiment Configuration System
**Priority**: 🔴 Critical | **Estimate**: 6h

- [ ] Define experiment configuration schema:
  ```python
  @dataclass
  class ExperimentConfig:
      experiment_id: str
      name: str
      description: str
      
      # Ontology/CQ version
      ontology_version: str
      ontology_path: Path
      cq_version: str
      cq_path: Path
      
      # RAG architecture variant
      rag_variant: Literal["classic", "kg_only", "hybrid"]
      use_vector_store: bool
      use_knowledge_graph: bool
      
      # Model configs
      llm_config: LLMConfig
      embedding_config: EmbeddingConfig
      
      # Tracking
      created_at: datetime
      tags: list[str]
  ```
- [ ] Implement experiment registry (SQLite/JSON)
- [ ] Support experiment versioning and tagging
- [ ] CLI commands for experiment management

**Acceptance Criteria**:
- Experiments fully reproducible from config
- Version control for ontology/CQ pairs
- Easy experiment comparison

---

### Issue #12.2: Iteration-Level Metrics Tracking
**Priority**: 🔴 Critical | **Estimate**: 8h

- [ ] Track metrics at each DeepResearch iteration:
  ```python
  @dataclass
  class IterationMetrics:
      iteration_id: int
      experiment_id: str
      timestamp: datetime
      
      # Graph state
      node_count: int
      edge_count: int
      new_nodes_added: int
      new_edges_added: int
      entities_merged: int
      
      # Validation metrics
      shacl_violations: int
      shacl_warnings: int
      ontology_violations: int
      cq_coverage: float  # % of CQs answerable
      cq_scores: dict[str, float]  # per-CQ scores
      
      # Extraction quality
      avg_entity_confidence: float
      avg_relation_confidence: float
      low_confidence_count: int
      
      # Research progress
      questions_asked: int
      questions_answered: int
      findings_generated: int
      evidence_sources_used: int
      
      # Graph quality
      connected_components: int
      avg_degree: float
      orphan_nodes: int
  ```
- [ ] Implement `MetricsCollector` service
- [ ] Persist metrics to time-series store (SQLite + JSON)
- [ ] Real-time metrics streaming (optional WebSocket)

**Acceptance Criteria**:
- Every iteration logged with full metrics
- Queryable metrics history
- Export to CSV/JSON for analysis

---

### Issue #12.3: Ontology/CQ Version Comparison
**Priority**: 🔴 Critical | **Estimate**: 6h

- [ ] Implement ontology diff tool:
  - Classes added/removed/modified
  - Relations added/removed/modified
  - Constraints changed
- [ ] Implement CQ diff tool:
  - Questions added/removed/modified
  - Coverage changes
- [ ] Track KG building metrics across ontology versions:
  ```python
  @dataclass
  class OntologyComparison:
      base_version: str
      extended_version: str
      
      # Ontology diff
      classes_added: list[str]
      classes_removed: list[str]
      relations_added: list[str]
      relations_removed: list[str]
      
      # CQ diff
      cqs_added: list[str]
      cqs_removed: list[str]
      
      # Impact on KG building
      base_final_metrics: IterationMetrics
      extended_final_metrics: IterationMetrics
      
      # Improvements
      coverage_improvement: float
      validation_improvement: float
      convergence_speed_change: int  # iterations difference
  ```
- [ ] Generate comparison reports (Markdown + JSON)

**Acceptance Criteria**:
- Clear diff visualization
- Quantified impact metrics
- Automated comparison reports

---

### Issue #12.4: QA Evaluation Dataset Integration
**Priority**: 🔴 Critical | **Estimate**: 6h

- [ ] Define QA evaluation dataset schema:
  ```python
  @dataclass
  class QAExample:
      id: str
      question: str
      gold_answer: str | list[str]
      answer_type: Literal["exact", "list", "boolean", "freeform"]
      difficulty: Literal["easy", "medium", "hard"]
      requires_reasoning: bool
      hops_required: int  # for multi-hop questions
      source_documents: list[str]
      tags: list[str]
  
  @dataclass 
  class QADataset:
      name: str
      version: str
      examples: list[QAExample]
      metadata: dict[str, Any]
  ```
- [ ] Implement dataset loader (JSON/CSV/HuggingFace)
- [ ] Support dataset splits (train/val/test)
- [ ] Dataset statistics and analysis tools

**Acceptance Criteria**:
- Standard dataset format
- Easy to add new datasets
- Split management

---

### Issue #12.5: RAG Architecture Variants
**Priority**: 🔴 Critical | **Estimate**: 10h

- [ ] Implement three RAG variants for comparison:

  **Variant A: Classic AgenticRAG (No KG)**
  ```python
  class ClassicAgenticRAG:
      """RAG using only vector store retrieval."""
      def __init__(self, vector_store: VectorStore, llm: LLMProvider): ...
      def answer(self, question: str) -> RAGResponse: ...
  ```
  
  **Variant B: Hybrid AgenticRAG (Vector + KG)**
  ```python
  class HybridAgenticRAG:
      """RAG using both vector store and KG."""
      def __init__(
          self, 
          vector_store: VectorStore, 
          graph_store: GraphStore,
          llm: LLMProvider
      ): ...
      def answer(self, question: str) -> RAGResponse: ...
  ```
  
  **Variant C: KG-Only AgenticRAG**
  ```python
  class KGOnlyAgenticRAG:
      """RAG using only KG retrieval."""
      def __init__(self, graph_store: GraphStore, llm: LLMProvider): ...
      def answer(self, question: str) -> RAGResponse: ...
  ```

- [ ] Unified interface for all variants
- [ ] Configurable retrieval strategies per variant
- [ ] Response includes retrieval trace

**Acceptance Criteria**:
- All three variants functional
- Fair comparison (same LLM, same prompts where applicable)
- Full retrieval provenance

---

### Issue #12.6: QA Performance Metrics
**Priority**: 🔴 Critical | **Estimate**: 6h

- [ ] Implement QA evaluation metrics:
  ```python
  @dataclass
  class QAMetrics:
      # Accuracy metrics
      exact_match: float
      f1_score: float
      precision: float
      recall: float
      
      # Semantic metrics
      semantic_similarity: float  # embedding-based
      bertscore: float
      
      # RAG-specific metrics (deepeval compatible)
      faithfulness: float  # answer grounded in retrieved context
      relevance: float  # retrieved context relevant to question
      answer_completeness: float
      
      # Reasoning metrics
      reasoning_accuracy: float  # for multi-hop
      hop_accuracy: dict[int, float]  # accuracy by hop count
      
      # Efficiency metrics
      avg_latency_ms: float
      avg_tokens_used: int
      avg_retrieval_count: int
  ```
- [ ] Integration with `deepeval` library
- [ ] Per-question detailed results
- [ ] Aggregate statistics with confidence intervals

**Acceptance Criteria**:
- Standard QA metrics computed
- Breakdown by question type/difficulty
- Statistical significance testing

---

### Issue #12.7: Experiment Runner & Orchestration
**Priority**: 🔴 Critical | **Estimate**: 8h

- [ ] Implement experiment runner:
  ```python
  class ExperimentRunner:
      def run_kg_building_experiment(
          self,
          config: ExperimentConfig,
          documents: list[Path]
      ) -> KGBuildingResult:
          """Run KG building with full metrics tracking."""
          ...
      
      def run_qa_evaluation(
          self,
          config: ExperimentConfig,
          dataset: QADataset,
          rag_variant: str
      ) -> QAEvaluationResult:
          """Evaluate RAG variant on QA dataset."""
          ...
      
      def run_comparison_suite(
          self,
          configs: list[ExperimentConfig],
          dataset: QADataset
      ) -> ComparisonReport:
          """Run full comparison across configurations."""
          ...
  ```
- [ ] Parallel experiment execution (optional)
- [ ] Checkpointing for long experiments
- [ ] Notification on completion

**Acceptance Criteria**:
- One-command experiment execution
- Resumable experiments
- Comprehensive result logging

---

### Issue #12.8: Comparison Dashboard & Reporting
**Priority**: 🟡 Medium | **Estimate**: 8h

- [ ] Generate comparison reports:
  ```
  reports/
  ├── experiment_001/
  │   ├── config.json
  │   ├── iteration_metrics.csv
  │   ├── final_kg_stats.json
  │   ├── qa_results.json
  │   └── report.md
  ├── comparisons/
  │   ├── ontology_v1_vs_v2.md
  │   ├── rag_variants_comparison.md
  │   └── full_comparison_matrix.md
  ```
- [ ] Visualization plots:
  - Iteration metrics over time (line charts)
  - RAG variant comparison (bar charts)
  - Ontology version impact (before/after)
  - CQ coverage heatmaps
- [ ] Export to LaTeX tables (for papers)
- [ ] Interactive HTML dashboard (optional)

**Acceptance Criteria**:
- Publication-ready figures
- Automated report generation
- Easy drill-down into details

---

### Issue #12.9: Convergence Analysis
**Priority**: 🟡 Medium | **Estimate**: 4h

- [ ] Implement convergence detection:
  - Graph stability (no new nodes/edges)
  - Validation score plateau
  - CQ coverage saturation
- [ ] Track convergence metrics:
  ```python
  @dataclass
  class ConvergenceAnalysis:
      iterations_to_converge: int
      final_cq_coverage: float
      final_validation_score: float
      marginal_gain_history: list[float]
      convergence_trigger: str  # what caused stop
  ```
- [ ] Compare convergence across ontology versions
- [ ] Identify bottlenecks (which CQs never get answered)

**Acceptance Criteria**:
- Clear convergence criteria
- Bottleneck identification
- Comparison across experiments

---

### Issue #12.10: Ablation Study Support
**Priority**: 🟡 Medium | **Estimate**: 4h

- [ ] Support ablation configurations:
  - With/without specific ontology classes
  - With/without specific CQ groups
  - Different chunking strategies
  - Different embedding models
- [ ] Automated ablation experiment generation
- [ ] Impact analysis per component

**Acceptance Criteria**:
- Easy ablation setup
- Systematic component analysis
- Clear impact attribution

---

## �📅 Milestone Planning

### Milestone 1: Foundation (Week 1-2)
- [ ] #1.1 Project Scaffolding
- [ ] #1.2 Configuration Management
- [ ] #2.1 Document Ingestion Interface
- [ ] #3.1 Embedding Provider Interface
- [ ] #4.1 LLM Provider Interface

### Milestone 2: Document Pipeline (Week 3-4)
- [ ] #2.2 PDF Document Loader
- [ ] #2.3 Office Document Loaders
- [ ] #2.4 Chunking Strategy System
- [ ] #3.2 Vector Database Abstraction
- [ ] #3.3 Document Indexing Service

### Milestone 3: Extraction Engine (Week 5-6)
- [ ] #4.2 Tool Framework for Agents
- [ ] #4.3 Base Agent Framework
- [ ] #5.1 Entity Extraction Interface
- [ ] #5.2 LLM-Based Entity Extractor
- [ ] #5.3 LLM-Based Relation Extractor

### Milestone 4: KG Assembly (Week 7-8)
- [ ] #6.1 KG Assembly Engine
- [ ] #6.2 Graph Database Abstraction
- [ ] #6.4 KG Export Formats
- [ ] #7.1 Ontology Validation Service
- [ ] #7.2 SHACL Validation Engine

### Milestone 5: Agent Orchestration (Week 9-10)
- [ ] #4.4 Agent Orchestration System
- [ ] #8.1 DeepResearch Agent
- [ ] #8.2 KG Builder Agent
- [ ] #8.3 Validation Agent

### Milestone 6: Evaluation & Polish (Week 11-12)
- [ ] #9.1 Extraction Evaluation
- [ ] #9.2 Graph Quality Metrics
- [ ] #10.1 CLI Application
- [ ] #10.2 Docker Containerization
- [ ] #11.1 API Documentation

### Milestone 7: Experiment Framework (Week 13-14)
- [ ] #12.1 Experiment Configuration System
- [ ] #12.2 Iteration-Level Metrics Tracking
- [ ] #12.3 Ontology/CQ Version Comparison
- [ ] #12.4 QA Evaluation Dataset Integration

### Milestone 8: RAG Comparison & Analysis (Week 15-16)
- [ ] #12.5 RAG Architecture Variants
- [ ] #12.6 QA Performance Metrics
- [ ] #12.7 Experiment Runner & Orchestration
- [ ] #12.8 Comparison Dashboard & Reporting
- [ ] #12.9 Convergence Analysis
- [ ] #12.10 Ablation Study Support

---

## 🔄 Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-30 | Added Epic 12: Experiment Tracking & Comparison Framework | - |
| 2026-01-30 | Initial backlog created | Auto-generated |

