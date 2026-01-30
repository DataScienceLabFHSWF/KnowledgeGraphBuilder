# 📐 KnowledgeGraphBuilder – Interface Specifications

> **Version**: 1.0  
> **Last Updated**: 2026-01-30

This document defines all core interfaces (protocols) for the KnowledgeGraphBuilder system. All implementations must adhere to these contracts.

---

## Table of Contents

1. [Document Processing Interfaces](#1-document-processing-interfaces)
2. [Embedding Interfaces](#2-embedding-interfaces)
3. [Vector Store Interfaces](#3-vector-store-interfaces)
4. [LLM Provider Interfaces](#4-llm-provider-interfaces)
5. [Agent Interfaces](#5-agent-interfaces)
6. [Extraction Interfaces](#6-extraction-interfaces)
7. [Graph Store Interfaces](#7-graph-store-interfaces)
8. [Validation Interfaces](#8-validation-interfaces)
9. [Data Models](#9-data-models)
10. [Output Formats](#10-output-formats)
11. [Experiment & Evaluation Interfaces](#11-experiment--evaluation-interfaces)

---

## 1. Document Processing Interfaces

### 1.1 DocumentLoader Protocol

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol, runtime_checkable

@runtime_checkable
class DocumentLoader(Protocol):
    """Protocol for document loading implementations."""
    
    @property
    def supported_extensions(self) -> list[str]:
        """Return list of supported file extensions (e.g., ['.pdf', '.PDF'])."""
        ...
    
    def load(self, file_path: Path) -> "Document":
        """
        Load a document from file path.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Document object with content and metadata
            
        Raises:
            DocumentLoadError: If file cannot be loaded
            UnsupportedFormatError: If file type not supported
        """
        ...
    
    def load_batch(self, file_paths: list[Path]) -> list["Document"]:
        """Load multiple documents."""
        ...
```

### 1.2 ChunkingStrategy Protocol

```python
@runtime_checkable
class ChunkingStrategy(Protocol):
    """Protocol for document chunking strategies."""
    
    @property
    def name(self) -> str:
        """Strategy identifier."""
        ...
    
    def chunk(
        self, 
        document: "Document",
        chunk_size: int = 512,
        chunk_overlap: int = 50
    ) -> list["Chunk"]:
        """
        Split document into chunks.
        
        Args:
            document: Document to chunk
            chunk_size: Target chunk size (tokens or chars based on implementation)
            chunk_overlap: Overlap between consecutive chunks
            
        Returns:
            List of Chunk objects with provenance metadata
        """
        ...
```

### 1.3 DocumentLoaderFactory

```python
class DocumentLoaderFactory:
    """Factory for creating appropriate document loaders."""
    
    _loaders: dict[str, type[DocumentLoader]] = {}
    
    @classmethod
    def register(cls, loader_class: type[DocumentLoader]) -> None:
        """Register a loader class for its supported extensions."""
        ...
    
    @classmethod
    def get_loader(cls, file_path: Path) -> DocumentLoader:
        """Get appropriate loader for file type."""
        ...
    
    @classmethod
    def load(cls, file_path: Path) -> "Document":
        """Convenience method to load any supported document."""
        ...
```

---

## 2. Embedding Interfaces

### 2.1 EmbeddingProvider Protocol

```python
import numpy as np
from numpy.typing import NDArray

@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for embedding generation."""
    
    @property
    def model_name(self) -> str:
        """Name of the embedding model."""
        ...
    
    @property
    def dimension(self) -> int:
        """Embedding vector dimension."""
        ...
    
    @property
    def max_tokens(self) -> int:
        """Maximum input tokens supported."""
        ...
    
    def embed_text(self, text: str) -> NDArray[np.float32]:
        """
        Generate embedding for single text.
        
        Args:
            text: Input text to embed
            
        Returns:
            Embedding vector as numpy array
        """
        ...
    
    def embed_batch(
        self, 
        texts: list[str],
        batch_size: int = 32
    ) -> NDArray[np.float32]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of input texts
            batch_size: Batch size for processing
            
        Returns:
            2D array of shape (len(texts), dimension)
        """
        ...
```

### 2.2 OllamaEmbeddingProvider Implementation Signature

```python
class OllamaEmbeddingProvider:
    """Ollama-based embedding provider."""
    
    def __init__(
        self,
        model: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434",
        timeout: float = 30.0
    ) -> None:
        ...
```

---

## 3. Vector Store Interfaces

### 3.1 VectorStore Protocol

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class SearchResult:
    """Result from vector similarity search."""
    id: str
    score: float
    metadata: dict[str, Any]
    content: str | None = None

@dataclass 
class VectorRecord:
    """Record to store in vector database."""
    id: str
    vector: NDArray[np.float32]
    metadata: dict[str, Any]
    content: str | None = None

@runtime_checkable
class VectorStore(Protocol):
    """Protocol for vector database operations."""
    
    @property
    def collection_name(self) -> str:
        """Name of the current collection."""
        ...
    
    def create_collection(
        self,
        name: str,
        dimension: int,
        distance_metric: str = "cosine"
    ) -> None:
        """Create a new collection."""
        ...
    
    def delete_collection(self, name: str) -> None:
        """Delete a collection."""
        ...
    
    def add(
        self,
        records: list[VectorRecord]
    ) -> list[str]:
        """
        Add vectors to the store.
        
        Args:
            records: List of VectorRecord objects
            
        Returns:
            List of assigned IDs
        """
        ...
    
    def search(
        self,
        query_vector: NDArray[np.float32],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        include_content: bool = True
    ) -> list[SearchResult]:
        """
        Search for similar vectors.
        
        Args:
            query_vector: Query embedding
            top_k: Number of results to return
            filters: Metadata filters (implementation-specific)
            include_content: Whether to include content in results
            
        Returns:
            List of SearchResult objects sorted by similarity
        """
        ...
    
    def hybrid_search(
        self,
        query_vector: NDArray[np.float32],
        query_text: str,
        top_k: int = 10,
        alpha: float = 0.5,
        filters: dict[str, Any] | None = None
    ) -> list[SearchResult]:
        """
        Hybrid dense + sparse search.
        
        Args:
            query_vector: Dense query embedding
            query_text: Text for sparse/keyword search
            top_k: Number of results
            alpha: Weight for dense vs sparse (0=sparse, 1=dense)
            filters: Metadata filters
            
        Returns:
            Combined search results
        """
        ...
    
    def get(self, ids: list[str]) -> list[VectorRecord]:
        """Retrieve records by ID."""
        ...
    
    def delete(self, ids: list[str]) -> None:
        """Delete records by ID."""
        ...
    
    def count(self) -> int:
        """Return total number of vectors in collection."""
        ...
```

---

## 4. LLM Provider Interfaces

### 4.1 LLMProvider Protocol

```python
from dataclasses import dataclass
from enum import Enum
from typing import TypeVar, Generic, Iterator

class MessageRole(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"

@dataclass
class Message:
    """Chat message."""
    role: MessageRole
    content: str
    tool_calls: list["ToolCall"] | None = None
    tool_call_id: str | None = None

@dataclass
class ToolCall:
    """Tool call request from LLM."""
    id: str
    name: str
    arguments: dict[str, Any]

@dataclass
class GenerationConfig:
    """Configuration for text generation."""
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float = 0.9
    stop_sequences: list[str] | None = None
    json_mode: bool = False

T = TypeVar("T")

@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM interactions."""
    
    @property
    def model_name(self) -> str:
        """Name of the model."""
        ...
    
    @property
    def supports_tools(self) -> bool:
        """Whether the model supports tool/function calling."""
        ...
    
    @property
    def supports_json_mode(self) -> bool:
        """Whether the model supports structured JSON output."""
        ...
    
    def generate(
        self,
        prompt: str,
        config: GenerationConfig | None = None
    ) -> str:
        """
        Generate text completion.
        
        Args:
            prompt: Input prompt
            config: Generation configuration
            
        Returns:
            Generated text
        """
        ...
    
    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        config: GenerationConfig | None = None
    ) -> T:
        """
        Generate structured output matching schema.
        
        Args:
            prompt: Input prompt
            schema: Pydantic model or dataclass defining output structure
            config: Generation configuration
            
        Returns:
            Parsed output matching schema type
        """
        ...
    
    def chat(
        self,
        messages: list[Message],
        tools: list["Tool"] | None = None,
        config: GenerationConfig | None = None
    ) -> Message:
        """
        Multi-turn chat with optional tool use.
        
        Args:
            messages: Conversation history
            tools: Available tools for the model
            config: Generation configuration
            
        Returns:
            Assistant response message
        """
        ...
    
    def stream(
        self,
        prompt: str,
        config: GenerationConfig | None = None
    ) -> Iterator[str]:
        """Stream generated tokens."""
        ...
```

### 4.2 OllamaProvider Implementation Signature

```python
class OllamaProvider:
    """Ollama LLM provider implementation."""
    
    def __init__(
        self,
        model: str = "llama3.1:8b",
        base_url: str = "http://localhost:11434",
        timeout: float = 120.0,
        retry_attempts: int = 3
    ) -> None:
        ...
```

---

## 5. Agent Interfaces

### 5.1 Tool Protocol

```python
from dataclasses import dataclass

@dataclass
class ToolResult:
    """Result from tool execution."""
    success: bool
    output: Any
    error: str | None = None

@runtime_checkable
class Tool(Protocol):
    """Protocol for agent tools."""
    
    @property
    def name(self) -> str:
        """Unique tool name."""
        ...
    
    @property
    def description(self) -> str:
        """Human-readable description for LLM."""
        ...
    
    @property
    def parameters_schema(self) -> dict[str, Any]:
        """JSON Schema for tool parameters."""
        ...
    
    def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute the tool with given parameters.
        
        Args:
            **kwargs: Tool-specific parameters
            
        Returns:
            ToolResult with output or error
        """
        ...
```

### 5.2 Agent Protocol

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class AgentInput:
    """Input to an agent."""
    task: str
    context: dict[str, Any] = field(default_factory=dict)
    max_iterations: int = 10

@dataclass
class AgentStep:
    """Single step in agent execution."""
    thought: str
    action: str | None
    action_input: dict[str, Any] | None
    observation: str | None
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class AgentOutput:
    """Output from agent execution."""
    result: Any
    steps: list[AgentStep]
    success: bool
    error: str | None = None
    total_tokens: int = 0

@runtime_checkable
class Agent(Protocol):
    """Protocol for autonomous agents."""
    
    @property
    def name(self) -> str:
        """Agent identifier."""
        ...
    
    @property
    def tools(self) -> list[Tool]:
        """Available tools for this agent."""
        ...
    
    def run(self, input: AgentInput) -> AgentOutput:
        """
        Execute agent task.
        
        Args:
            input: Task description and context
            
        Returns:
            AgentOutput with result and execution trace
        """
        ...
```

### 5.3 AgentOrchestrator Protocol

```python
@dataclass
class PipelineStep:
    """Step in agent pipeline."""
    agent: Agent
    input_mapper: Callable[[Any], AgentInput]
    condition: Callable[[AgentOutput], bool] | None = None

@runtime_checkable
class AgentOrchestrator(Protocol):
    """Protocol for multi-agent orchestration."""
    
    def register_agent(self, agent: Agent) -> None:
        """Register an agent."""
        ...
    
    def create_pipeline(
        self,
        name: str,
        steps: list[PipelineStep]
    ) -> "Pipeline":
        """Create a sequential agent pipeline."""
        ...
    
    def run_pipeline(
        self,
        pipeline: "Pipeline",
        initial_input: Any
    ) -> list[AgentOutput]:
        """Execute pipeline and return all outputs."""
        ...
```

---

## 6. Extraction Interfaces

### 6.1 Entity Extractor Protocol

```python
from dataclasses import dataclass, field
from typing import Literal

@dataclass
class Evidence:
    """Evidence supporting an extraction."""
    source_type: Literal["local_doc", "web", "kg"]
    source_id: str  # chunk_id, url, or node_id
    text_span: str | None = None
    confidence: float = 1.0

@dataclass
class ExtractedEntity:
    """An extracted entity."""
    id: str
    label: str
    entity_type: str  # Ontology class URI or name
    description: str
    aliases: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    evidence: list[Evidence] = field(default_factory=list)

@runtime_checkable
class EntityExtractor(Protocol):
    """Protocol for entity extraction."""
    
    def extract(
        self,
        text: str,
        ontology_classes: list["OntologyClass"],
        existing_entities: list[ExtractedEntity] | None = None
    ) -> list[ExtractedEntity]:
        """
        Extract entities from text guided by ontology.
        
        Args:
            text: Source text
            ontology_classes: Target entity types from ontology
            existing_entities: Known entities for coreference
            
        Returns:
            List of extracted entities
        """
        ...
```

### 6.2 Relation Extractor Protocol

```python
@dataclass
class ExtractedRelation:
    """An extracted relation."""
    id: str
    source_entity_id: str
    target_entity_id: str
    predicate: str  # Ontology relation URI or name
    properties: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    evidence: list[Evidence] = field(default_factory=list)

@runtime_checkable
class RelationExtractor(Protocol):
    """Protocol for relation extraction."""
    
    def extract(
        self,
        text: str,
        entities: list[ExtractedEntity],
        ontology_relations: list["OntologyRelation"]
    ) -> list[ExtractedRelation]:
        """
        Extract relations between entities.
        
        Args:
            text: Source text
            entities: Entities found in text
            ontology_relations: Valid relation types
            
        Returns:
            List of extracted relations
        """
        ...
```

### 6.3 Research Finding Model

```python
@dataclass
class Claim:
    """A claim made in research findings."""
    text: str
    confidence: float
    evidence: list[Evidence]

@dataclass
class ResearchFinding:
    """Structured research finding from DeepResearch agent."""
    finding_id: str
    ontology_concepts: list[str]
    question: str
    claims: list[Claim]
    timestamp: datetime = field(default_factory=datetime.now)
    agent_id: str | None = None
```

---

## 7. Graph Store Interfaces

### 7.1 GraphStore Protocol

```python
@dataclass
class Node:
    """Graph node."""
    id: str
    labels: list[str]
    properties: dict[str, Any]

@dataclass
class Edge:
    """Graph edge."""
    id: str
    source_id: str
    target_id: str
    type: str
    properties: dict[str, Any]

@dataclass
class Subgraph:
    """A subgraph containing nodes and edges."""
    nodes: list[Node]
    edges: list[Edge]

class ExportFormat(Enum):
    JSON_LD = "json-ld"
    YARRRML = "yarrrml"
    TURTLE = "turtle"
    NTRIPLES = "n-triples"
    CYPHER = "cypher"
    GRAPHML = "graphml"

@runtime_checkable
class GraphStore(Protocol):
    """Protocol for graph database operations."""
    
    def add_node(self, node: Node) -> str:
        """Add node, return ID."""
        ...
    
    def add_edge(self, edge: Edge) -> str:
        """Add edge, return ID."""
        ...
    
    def get_node(self, node_id: str) -> Node | None:
        """Get node by ID."""
        ...
    
    def get_edge(self, edge_id: str) -> Edge | None:
        """Get edge by ID."""
        ...
    
    def update_node(self, node_id: str, properties: dict[str, Any]) -> None:
        """Update node properties."""
        ...
    
    def delete_node(self, node_id: str, cascade: bool = True) -> None:
        """Delete node (and optionally connected edges)."""
        ...
    
    def query(self, cypher: str, parameters: dict[str, Any] | None = None) -> list[dict]:
        """Execute Cypher query."""
        ...
    
    def get_subgraph(
        self,
        node_id: str,
        depth: int = 2,
        edge_types: list[str] | None = None
    ) -> Subgraph:
        """Get subgraph around a node."""
        ...
    
    def get_paths(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5
    ) -> list[list[str]]:
        """Find paths between two nodes."""
        ...
    
    def export(
        self,
        format: ExportFormat,
        subgraph: Subgraph | None = None
    ) -> str:
        """Export graph or subgraph to specified format."""
        ...
    
    def import_data(self, data: str, format: ExportFormat) -> None:
        """Import data from specified format."""
        ...
    
    def clear(self) -> None:
        """Clear all data."""
        ...
    
    def statistics(self) -> dict[str, Any]:
        """Get graph statistics."""
        ...
```

### 7.2 RDFStore Protocol

```python
from rdflib import Graph as RDFGraph, URIRef

@runtime_checkable
class RDFStore(Protocol):
    """Protocol for RDF/SPARQL operations."""
    
    def load_ontology(self, ontology_path: Path) -> None:
        """Load OWL ontology."""
        ...
    
    def add_triples(self, triples: list[tuple[URIRef, URIRef, Any]]) -> None:
        """Add RDF triples."""
        ...
    
    def query_sparql(self, sparql: str) -> list[dict]:
        """Execute SPARQL query."""
        ...
    
    def get_graph(self) -> RDFGraph:
        """Get underlying RDF graph."""
        ...
    
    def serialize(self, format: str = "turtle") -> str:
        """Serialize to RDF format."""
        ...
    
    def enable_reasoning(self, reasoner: str = "owlrl") -> None:
        """Enable OWL reasoning."""
        ...
```

---

## 8. Validation Interfaces

### 8.1 Validator Protocol

```python
from enum import Enum

class ViolationSeverity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

@dataclass
class Violation:
    """A validation violation."""
    severity: ViolationSeverity
    message: str
    source_node: str | None = None
    constraint: str | None = None
    suggestion: str | None = None

@dataclass
class ValidationReport:
    """Complete validation report."""
    is_valid: bool
    violations: list[Violation]
    stats: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)

@runtime_checkable
class Validator(Protocol):
    """Protocol for KG validation."""
    
    @property
    def name(self) -> str:
        """Validator identifier."""
        ...
    
    def validate(self, graph: GraphStore) -> ValidationReport:
        """
        Validate the graph.
        
        Args:
            graph: Graph store to validate
            
        Returns:
            ValidationReport with violations
        """
        ...
```

### 8.2 SHACLValidator Interface

```python
class SHACLValidator:
    """SHACL constraint validator."""
    
    def __init__(self, shapes_path: Path | None = None) -> None:
        """Initialize with optional shapes graph."""
        ...
    
    def load_shapes(self, shapes_path: Path) -> None:
        """Load SHACL shapes from file."""
        ...
    
    def add_shape(self, shape_ttl: str) -> None:
        """Add shape from Turtle string."""
        ...
    
    def validate(self, graph: GraphStore) -> ValidationReport:
        """Run SHACL validation."""
        ...
```

### 8.3 CompetencyQuestionValidator Interface

```python
@dataclass
class CompetencyQuestion:
    """A competency question for validation."""
    id: str
    question: str
    sparql: str | None = None  # Pre-defined SPARQL
    expected_answer_type: str | None = None  # e.g., "count > 0", "list"
    
@dataclass
class CQResult:
    """Result of CQ evaluation."""
    cq: CompetencyQuestion
    answerable: bool
    answer: Any | None
    confidence: float

class CQValidator:
    """Competency question validator."""
    
    def __init__(
        self, 
        cqs: list[CompetencyQuestion],
        llm: LLMProvider
    ) -> None:
        ...
    
    def validate(self, graph: GraphStore) -> ValidationReport:
        """Check CQ coverage."""
        ...
    
    def evaluate_cq(self, cq: CompetencyQuestion, graph: GraphStore) -> CQResult:
        """Evaluate single CQ."""
        ...
```

---

## 9. Data Models

### 9.1 Document Models

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

class FileType(Enum):
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    TXT = "txt"
    MARKDOWN = "markdown"
    HTML = "html"

@dataclass
class DocumentMetadata:
    """Metadata for a document."""
    title: str | None = None
    author: str | None = None
    created_at: datetime | None = None
    modified_at: datetime | None = None
    page_count: int | None = None
    word_count: int | None = None
    language: str | None = None
    custom: dict[str, Any] = field(default_factory=dict)

@dataclass
class ChunkMetadata:
    """Metadata for a chunk."""
    section_title: str | None = None
    page_number: int | None = None
    paragraph_index: int | None = None
    heading_level: int | None = None
    is_table: bool = False
    is_list: bool = False

@dataclass
class Chunk:
    """A document chunk."""
    id: str
    content: str
    document_id: str
    start_char: int
    end_char: int
    token_count: int
    metadata: ChunkMetadata = field(default_factory=ChunkMetadata)
    embedding: NDArray[np.float32] | None = None

@dataclass
class Document:
    """A loaded document."""
    id: str
    content: str
    source_path: Path
    file_type: FileType
    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)
    chunks: list[Chunk] = field(default_factory=list)
```

### 9.2 Ontology Models

```python
@dataclass
class OntologyClass:
    """An ontology class definition."""
    uri: str
    label: str
    description: str | None = None
    parent_uri: str | None = None
    properties: list[str] = field(default_factory=list)

@dataclass
class OntologyRelation:
    """An ontology relation/property definition."""
    uri: str
    label: str
    description: str | None = None
    domain: list[str] = field(default_factory=list)  # Class URIs
    range: list[str] = field(default_factory=list)   # Class URIs or datatypes
    is_functional: bool = False
    is_inverse_functional: bool = False
    is_transitive: bool = False
    is_symmetric: bool = False

@dataclass
class Ontology:
    """Complete ontology representation."""
    uri: str
    classes: list[OntologyClass]
    relations: list[OntologyRelation]
    prefixes: dict[str, str] = field(default_factory=dict)
```

---

## 10. Output Formats

### 10.1 JSON-LD Output

```json
{
  "@context": {
    "@vocab": "http://example.org/ontology#",
    "schema": "http://schema.org/",
    "prov": "http://www.w3.org/ns/prov#",
    "confidence": "http://example.org/kg#confidence",
    "evidence": "http://example.org/kg#evidence"
  },
  "@graph": [
    {
      "@id": "entity:E001",
      "@type": "RootCause",
      "label": "Process Failure",
      "description": "Failure in manufacturing process",
      "confidence": 0.85,
      "evidence": [
        {
          "@type": "prov:Entity",
          "source": "doc:DOC-112",
          "chunk": "chunk:DOC-112-CH-7"
        }
      ]
    },
    {
      "@id": "relation:R001",
      "@type": "causedBy",
      "source": "entity:E002",
      "target": "entity:E001",
      "confidence": 0.78
    }
  ]
}
```

### 10.2 YARRRML Output

```yaml
prefixes:
  ex: http://example.org/ontology#
  prov: http://www.w3.org/ns/prov#
  kg: http://example.org/kg#

mappings:
  entity:
    sources:
      - [entities.csv~csv]
    s: ex:entity/$(id)
    po:
      - [a, ex:$(entity_type)]
      - [rdfs:label, $(label)]
      - [ex:description, $(description)]
      - [kg:confidence, $(confidence), xsd:float]
  
  relation:
    sources:
      - [relations.csv~csv]
    s: ex:relation/$(id)
    po:
      - [a, ex:$(predicate)]
      - [ex:source, ex:entity/$(source_id)~iri]
      - [ex:target, ex:entity/$(target_id)~iri]
      - [kg:confidence, $(confidence), xsd:float]
```

### 10.3 RDF/Turtle Output

```turtle
@prefix ex: <http://example.org/ontology#> .
@prefix kg: <http://example.org/kg#> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ex:entity/E001 a ex:RootCause ;
    rdfs:label "Process Failure" ;
    ex:description "Failure in manufacturing process" ;
    kg:confidence "0.85"^^xsd:float ;
    prov:wasDerivedFrom ex:chunk/DOC-112-CH-7 .

ex:entity/E002 ex:causedBy ex:entity/E001 ;
    kg:relationConfidence "0.78"^^xsd:float .
```

### 10.4 Internal YAML Research Finding Format

```yaml
finding_id: FR-0231
timestamp: "2026-01-30T14:32:00Z"
agent_id: deep-research-agent-01

ontology_concepts:
  - ex:RootCause
  - ex:CorrectiveAction

question: "What are common root causes in 8D problem solving?"

claims:
  - text: "Root causes are often categorized as people, process, or system failures."
    confidence: 0.82
    evidence:
      - source_type: local_doc
        source_id: DOC-112
        chunk_id: DOC-112-CH-7
        text_span: "The 8D methodology categorizes root causes into three main areas..."
      
  - text: "Process failures account for approximately 60% of identified root causes."
    confidence: 0.71
    evidence:
      - source_type: local_doc
        source_id: DOC-089
        chunk_id: DOC-089-CH-12
        text_span: "Analysis of 500 8D reports showed process-related causes..."

related_entities:
  - id: E001
    type: ex:RootCause
    label: "Process Failure"
    
related_relations:
  - source: E001
    predicate: ex:categoryOf
    target: E000  # 8D Problem
```

---

## Implementation Notes

1. **All protocols use `@runtime_checkable`** for isinstance() checks
2. **Pydantic models** should be used for config and API boundaries
3. **Dataclasses** used for internal data structures (performance)
4. **Type hints** are mandatory for all public interfaces
5. **Async variants** can be added with `async` prefix (e.g., `async_generate`)

---

## 11. Experiment & Evaluation Interfaces

### 11.1 Experiment Configuration Models

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Literal, Any

class RAGVariant(Enum):
    """RAG architecture variants for comparison."""
    CLASSIC = "classic"       # Vector store only
    HYBRID = "hybrid"         # Vector store + KG
    KG_ONLY = "kg_only"       # Knowledge graph only

@dataclass
class OntologyVersion:
    """Ontology version metadata."""
    version: str
    path: Path
    description: str
    parent_version: str | None = None
    classes_count: int = 0
    relations_count: int = 0
    constraints_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class CQVersion:
    """Competency Questions version metadata."""
    version: str
    path: Path
    description: str
    parent_version: str | None = None
    cq_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class ExperimentConfig:
    """Complete experiment configuration."""
    experiment_id: str
    name: str
    description: str
    
    # Versioned inputs
    ontology_version: OntologyVersion
    cq_version: CQVersion
    
    # RAG configuration
    rag_variant: RAGVariant
    use_vector_store: bool
    use_knowledge_graph: bool
    
    # Model configurations
    llm_model: str
    embedding_model: str
    llm_temperature: float = 0.7
    
    # Experiment parameters
    max_iterations: int = 20
    convergence_threshold: float = 0.01
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    tags: list[str] = field(default_factory=list)
    notes: str = ""
```

### 11.2 Iteration Metrics Models

```python
@dataclass
class GraphStateMetrics:
    """Graph state at a given iteration."""
    node_count: int
    edge_count: int
    new_nodes_added: int
    new_edges_added: int
    entities_merged: int
    orphan_nodes: int

@dataclass
class ValidationMetrics:
    """Validation results at a given iteration."""
    shacl_violations: int
    shacl_warnings: int
    ontology_violations: int
    cq_coverage: float  # 0.0 to 1.0
    cq_scores: dict[str, float]  # CQ ID → score
    answerable_cqs: int
    total_cqs: int

@dataclass
class ExtractionMetrics:
    """Extraction quality at a given iteration."""
    entities_extracted: int
    relations_extracted: int
    avg_entity_confidence: float
    avg_relation_confidence: float
    low_confidence_count: int  # below threshold
    confidence_threshold: float

@dataclass
class ResearchMetrics:
    """Research activity at a given iteration."""
    questions_asked: int
    questions_answered: int
    findings_generated: int
    evidence_sources_used: int
    unique_documents_used: int
    web_queries_made: int  # if web search enabled

@dataclass
class GraphQualityMetrics:
    """Structural graph quality metrics."""
    connected_components: int
    largest_component_size: int
    avg_degree: float
    max_degree: int
    density: float
    avg_clustering_coefficient: float

@dataclass
class IterationMetrics:
    """Complete metrics for a single DeepResearch iteration."""
    iteration_id: int
    experiment_id: str
    timestamp: datetime
    
    # Sub-metrics
    graph_state: GraphStateMetrics
    validation: ValidationMetrics
    extraction: ExtractionMetrics
    research: ResearchMetrics
    graph_quality: GraphQualityMetrics
    
    # Timing
    duration_seconds: float
    llm_calls: int
    tokens_used: int
    
    # Convergence tracking
    marginal_gain: float  # improvement over previous iteration
    is_converged: bool = False
    convergence_reason: str | None = None
```

### 11.3 MetricsCollector Protocol

```python
@runtime_checkable
class MetricsCollector(Protocol):
    """Protocol for collecting and storing experiment metrics."""
    
    def start_experiment(self, config: ExperimentConfig) -> str:
        """
        Initialize a new experiment.
        
        Args:
            config: Experiment configuration
            
        Returns:
            Experiment ID
        """
        ...
    
    def record_iteration(self, metrics: IterationMetrics) -> None:
        """
        Record metrics for a single iteration.
        
        Args:
            metrics: Complete iteration metrics
        """
        ...
    
    def get_iteration_history(
        self, 
        experiment_id: str
    ) -> list[IterationMetrics]:
        """Get all iterations for an experiment."""
        ...
    
    def get_latest_metrics(
        self, 
        experiment_id: str
    ) -> IterationMetrics | None:
        """Get most recent iteration metrics."""
        ...
    
    def export_to_csv(
        self, 
        experiment_id: str, 
        output_path: Path
    ) -> None:
        """Export iteration metrics to CSV."""
        ...
    
    def export_to_json(
        self, 
        experiment_id: str, 
        output_path: Path
    ) -> None:
        """Export complete experiment data to JSON."""
        ...
```

### 11.4 QA Evaluation Models

```python
class AnswerType(Enum):
    """Types of expected answers."""
    EXACT = "exact"           # Single exact answer
    LIST = "list"             # List of items
    BOOLEAN = "boolean"       # Yes/No
    FREEFORM = "freeform"     # Open-ended

class Difficulty(Enum):
    """Question difficulty levels."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

@dataclass
class QAExample:
    """A single QA example from the dataset."""
    id: str
    question: str
    gold_answer: str | list[str]
    answer_type: AnswerType
    difficulty: Difficulty
    requires_reasoning: bool
    hops_required: int  # 1 for direct, 2+ for multi-hop
    source_documents: list[str]
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class QADataset:
    """Complete QA evaluation dataset."""
    name: str
    version: str
    description: str
    examples: list[QAExample]
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def get_by_difficulty(self, difficulty: Difficulty) -> list[QAExample]:
        """Filter examples by difficulty."""
        return [e for e in self.examples if e.difficulty == difficulty]
    
    def get_by_hops(self, min_hops: int, max_hops: int) -> list[QAExample]:
        """Filter examples by hop count."""
        return [e for e in self.examples 
                if min_hops <= e.hops_required <= max_hops]
```

### 11.5 QA Metrics Models

```python
@dataclass
class AccuracyMetrics:
    """Standard accuracy metrics."""
    exact_match: float
    f1_score: float
    precision: float
    recall: float

@dataclass
class SemanticMetrics:
    """Semantic similarity metrics."""
    semantic_similarity: float  # Embedding cosine similarity
    bertscore_precision: float
    bertscore_recall: float
    bertscore_f1: float

@dataclass
class RAGMetrics:
    """RAG-specific metrics (deepeval compatible)."""
    faithfulness: float      # Answer grounded in context
    relevance: float         # Context relevant to question
    answer_completeness: float
    context_precision: float
    context_recall: float

@dataclass
class ReasoningMetrics:
    """Multi-hop reasoning metrics."""
    overall_accuracy: float
    hop_accuracy: dict[int, float]  # hop_count → accuracy
    reasoning_trace_valid: float    # % with valid reasoning

@dataclass
class EfficiencyMetrics:
    """Performance/efficiency metrics."""
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    avg_tokens_used: int
    avg_retrieval_count: int
    avg_llm_calls: int

@dataclass
class QAEvaluationResult:
    """Complete QA evaluation results."""
    experiment_id: str
    dataset_name: str
    rag_variant: RAGVariant
    timestamp: datetime
    
    # Aggregate metrics
    accuracy: AccuracyMetrics
    semantic: SemanticMetrics
    rag: RAGMetrics
    reasoning: ReasoningMetrics
    efficiency: EfficiencyMetrics
    
    # Breakdown by category
    by_difficulty: dict[str, AccuracyMetrics]
    by_hop_count: dict[int, AccuracyMetrics]
    by_answer_type: dict[str, AccuracyMetrics]
    
    # Per-question results
    question_results: list["QuestionResult"]
    
    # Statistics
    total_questions: int
    successful_answers: int
    failed_answers: int
    error_count: int

@dataclass
class QuestionResult:
    """Result for a single question."""
    question_id: str
    question: str
    gold_answer: str | list[str]
    predicted_answer: str
    
    # Scores
    exact_match: bool
    f1_score: float
    semantic_similarity: float
    faithfulness: float
    
    # Retrieval info
    retrieved_context: list[str]
    retrieval_source: Literal["vector", "kg", "both"]
    
    # Efficiency
    latency_ms: float
    tokens_used: int
    
    # Error tracking
    is_error: bool = False
    error_message: str | None = None
```

### 11.6 RAG Variant Protocol

```python
@dataclass
class RAGResponse:
    """Response from a RAG system."""
    answer: str
    retrieved_context: list[str]
    retrieval_sources: list[dict[str, Any]]  # Source metadata
    reasoning_trace: list[str] | None = None
    confidence: float = 0.0
    latency_ms: float = 0.0
    tokens_used: int = 0

@runtime_checkable
class RAGSystem(Protocol):
    """Protocol for RAG system variants."""
    
    @property
    def variant(self) -> RAGVariant:
        """Return the RAG variant type."""
        ...
    
    def answer(
        self, 
        question: str,
        context: dict[str, Any] | None = None
    ) -> RAGResponse:
        """
        Answer a question using the RAG system.
        
        Args:
            question: The question to answer
            context: Optional additional context
            
        Returns:
            RAGResponse with answer and metadata
        """
        ...
    
    def batch_answer(
        self,
        questions: list[str]
    ) -> list[RAGResponse]:
        """Answer multiple questions."""
        ...
```

### 11.7 Comparison & Reporting Models

```python
@dataclass
class OntologyDiff:
    """Diff between two ontology versions."""
    base_version: str
    extended_version: str
    
    classes_added: list[str]
    classes_removed: list[str]
    classes_modified: list[str]
    
    relations_added: list[str]
    relations_removed: list[str]
    relations_modified: list[str]
    
    constraints_added: int
    constraints_removed: int

@dataclass
class CQDiff:
    """Diff between two CQ versions."""
    base_version: str
    extended_version: str
    
    cqs_added: list[str]
    cqs_removed: list[str]
    cqs_modified: list[str]

@dataclass
class KGBuildingComparison:
    """Comparison of KG building between experiments."""
    experiment_a_id: str
    experiment_b_id: str
    
    ontology_diff: OntologyDiff
    cq_diff: CQDiff
    
    # Final metrics comparison
    a_final_metrics: IterationMetrics
    b_final_metrics: IterationMetrics
    
    # Deltas
    node_count_delta: int
    edge_count_delta: int
    cq_coverage_delta: float
    validation_score_delta: float
    iterations_delta: int
    
    # Percentage improvements
    coverage_improvement_pct: float
    validation_improvement_pct: float
    graph_size_change_pct: float

@dataclass
class RAGComparisonResult:
    """Comparison of RAG variants on same dataset."""
    dataset_name: str
    timestamp: datetime
    
    # Results per variant
    classic_result: QAEvaluationResult | None
    hybrid_result: QAEvaluationResult | None
    kg_only_result: QAEvaluationResult | None
    
    # Winner per metric
    winners: dict[str, RAGVariant]  # metric_name → winning variant
    
    # Statistical significance
    significance_tests: dict[str, dict[str, float]]  # metric → (comparison → p-value)

@dataclass
class ExperimentReport:
    """Complete experiment report."""
    experiment_id: str
    config: ExperimentConfig
    
    # KG Building
    iteration_history: list[IterationMetrics]
    convergence_analysis: "ConvergenceAnalysis"
    
    # QA Evaluation (if run)
    qa_result: QAEvaluationResult | None
    
    # Timestamps
    started_at: datetime
    completed_at: datetime
    duration_seconds: float

@dataclass
class ConvergenceAnalysis:
    """Analysis of KG building convergence."""
    iterations_to_converge: int
    final_cq_coverage: float
    final_validation_score: float
    marginal_gain_history: list[float]
    convergence_trigger: str  # "coverage", "stability", "max_iterations"
    
    # Bottleneck analysis
    unanswered_cqs: list[str]
    low_coverage_classes: list[str]
    persistent_violations: list[str]
```

### 11.8 Experiment Runner Protocol

```python
@runtime_checkable
class ExperimentRunner(Protocol):
    """Protocol for running experiments."""
    
    def run_kg_building(
        self,
        config: ExperimentConfig,
        documents: list[Path],
        metrics_collector: MetricsCollector
    ) -> ExperimentReport:
        """
        Run KG building experiment with full metrics tracking.
        
        Args:
            config: Experiment configuration
            documents: Source documents
            metrics_collector: Metrics collector instance
            
        Returns:
            Complete experiment report
        """
        ...
    
    def run_qa_evaluation(
        self,
        config: ExperimentConfig,
        dataset: QADataset,
        rag_system: RAGSystem
    ) -> QAEvaluationResult:
        """
        Evaluate RAG system on QA dataset.
        
        Args:
            config: Experiment configuration
            dataset: QA evaluation dataset
            rag_system: RAG system to evaluate
            
        Returns:
            QA evaluation results
        """
        ...
    
    def run_comparison_suite(
        self,
        configs: list[ExperimentConfig],
        documents: list[Path],
        dataset: QADataset
    ) -> "ComparisonSuiteResult":
        """
        Run full comparison across configurations.
        
        Args:
            configs: List of experiment configurations
            documents: Source documents
            dataset: QA evaluation dataset
            
        Returns:
            Comparison suite results
        """
        ...
    
    def compare_ontology_versions(
        self,
        base_experiment_id: str,
        extended_experiment_id: str
    ) -> KGBuildingComparison:
        """Compare KG building across ontology versions."""
        ...
    
    def compare_rag_variants(
        self,
        experiment_ids: list[str],
        dataset: QADataset
    ) -> RAGComparisonResult:
        """Compare RAG variants on same dataset."""
        ...
```

### 11.9 Report Generator Protocol

```python
@runtime_checkable
class ReportGenerator(Protocol):
    """Protocol for generating experiment reports."""
    
    def generate_iteration_plot(
        self,
        experiment_id: str,
        metrics: list[str],
        output_path: Path
    ) -> None:
        """Generate line plots of metrics over iterations."""
        ...
    
    def generate_comparison_table(
        self,
        comparison: RAGComparisonResult,
        output_path: Path,
        format: Literal["markdown", "latex", "html"] = "markdown"
    ) -> None:
        """Generate comparison table."""
        ...
    
    def generate_ontology_impact_report(
        self,
        comparison: KGBuildingComparison,
        output_path: Path
    ) -> None:
        """Generate ontology extension impact report."""
        ...
    
    def generate_full_report(
        self,
        experiment_id: str,
        output_dir: Path
    ) -> None:
        """Generate complete experiment report with all artifacts."""
        ...
    
    def export_for_paper(
        self,
        experiment_ids: list[str],
        output_dir: Path
    ) -> None:
        """Export publication-ready figures and tables."""
        ...
```

---

## Implementation Notes

1. **All protocols use `@runtime_checkable`** for isinstance() checks
2. **Pydantic models** should be used for config and API boundaries
3. **Dataclasses** used for internal data structures (performance)
4. **Type hints** are mandatory for all public interfaces
5. **Async variants** can be added with `async` prefix (e.g., `async_generate`)

---

## Change Log

| Date | Version | Change |
|------|---------|--------|
| 2026-01-30 | 1.1 | Added Experiment & Evaluation Interfaces (Section 11) |
| 2026-01-30 | 1.0 | Initial interface specifications |

---

## 12. Knowledge Graph Versioning Interface

### 12.1 KGVersioningService Protocol

```python
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

@dataclass
class KGVersionMetadata:
    version: str
    timestamp: datetime
    trigger: str  # e.g., 'ingest:/data/file.pdf', 'manual', etc.
    documents: list[str] = field(default_factory=list)
    kg_hash: str = ""
    user: str = "auto-ingest"

@runtime_checkable
class KGVersioningService(Protocol):
    """Protocol for KG versioning and snapshot management."""

    def create_version(self, graph: "GraphStore", trigger: str, documents: list[str], user: str = "auto-ingest") -> KGVersionMetadata:
        """
        Create a new KG version snapshot after update.
        Args:
            graph: The current graph store
            trigger: What caused the update (file, batch, etc.)
            documents: List of document paths included
            user: User or agent triggering the update
        Returns:
            KGVersionMetadata for the new version
        """
        ...

    def list_versions(self) -> list[KGVersionMetadata]:
        """List all KG versions with metadata."""
        ...

    def restore_version(self, version: str) -> None:
        """Restore KG to a previous version."""
        ...

    def diff_versions(self, v1: str, v2: str) -> str:
        """Show diff between two KG versions."""
        ...
```

---

## 12.2 Versioning Workflow

1. After each KG update, call `KGVersioningService.create_version()`
2. Store KG export and metadata in `kg_versions/` (configurable)
3. Use `list_versions`, `restore_version`, and `diff_versions` for management and reproducibility

See [KG_VERSIONING.md] for details.
