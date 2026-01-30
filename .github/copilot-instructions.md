# GitHub Copilot Instructions for KnowledgeGraphBuilder

## Project Overview

This repository implements an **ontology-driven Knowledge Graph construction pipeline** that:
- Ingests documents (PDF, DOCX, PPTX, etc.)
- Extracts entities and relations guided by an ontology
- Builds and validates a Knowledge Graph
- Exports KG in various formats (JSON-LD, YARRRML, RDF)

**Language**: Python 3.11+  
**Primary Use**: KG building and validation (NOT the frontend/QA system)


## Repository Organization & Documentation Philosophy

- **Do NOT over-document**: Only document public APIs, protocols, and complex logic. Avoid excessive docstrings or comments for trivial code.
- **Keep the repo human-friendly**: The base directory should remain clean, containing only essential files (README.md, docker-compose.yml, .env.example, etc.).
- All detailed documentation, planning, and specs go in the `Planning/` folder.
- Implementation code lives in `src/`.
- Tests in `tests/`.
- Scripts/utilities in `scripts/`.
- No clutter or redundant files in the root.

---

## VS Code Settings

### General Python Style

- **Follow PEP 8** with line length of 100 characters
- **Use `ruff`** for linting and formatting
- **Use `black`** for code formatting (compatible with ruff)
- **Use `mypy`** for static type checking in strict mode

### Type Hints

- **All functions must have complete type hints** (parameters and return types)
- Use `from __future__ import annotations` for forward references
- Prefer `X | None` over `Optional[X]`
- Prefer `list[T]` over `List[T]` (Python 3.9+ style)
- Use `TypeVar` for generic functions
- Use `Protocol` for structural typing (duck typing with type safety)

```python
# Good
def process_documents(paths: list[Path], config: Config | None = None) -> list[Document]:
    ...

# Bad
def process_documents(paths, config=None):
    ...
```

### Docstrings

- Use **Google-style docstrings**
- All public functions, classes, and modules must have docstrings
- Include `Args`, `Returns`, `Raises` sections where applicable

```python
def extract_entities(
    text: str,
    ontology: Ontology,
    confidence_threshold: float = 0.5
) -> list[ExtractedEntity]:
    """Extract entities from text guided by ontology.
    
    Uses LLM-based extraction with ontology class definitions
    to identify and classify entities in the source text.
    
    Args:
        text: Source text to extract entities from.
        ontology: Ontology defining valid entity types.
        confidence_threshold: Minimum confidence for inclusion.
    
    Returns:
        List of extracted entities with provenance metadata.
    
    Raises:
        ExtractionError: If LLM call fails after retries.
        OntologyError: If ontology is invalid or empty.
    """
```

### Naming Conventions

- **Classes**: `PascalCase` (e.g., `DocumentLoader`, `EntityExtractor`)
- **Functions/Methods**: `snake_case` (e.g., `extract_entities`, `load_document`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_CHUNK_SIZE`, `MAX_RETRIES`)
- **Private members**: Single underscore prefix (e.g., `_internal_method`)
- **Module-level "protected"**: Single underscore (e.g., `_helper_function`)

### Project-Specific Naming

- **Protocols/Interfaces**: Name describes capability (e.g., `DocumentLoader`, `EmbeddingProvider`)
- **Implementations**: Provider name + capability (e.g., `OllamaEmbeddingProvider`, `Neo4jGraphStore`)
- **Exceptions**: End with `Error` (e.g., `DocumentLoadError`, `ValidationError`)
- **Config classes**: End with `Config` (e.g., `LLMConfig`, `ChunkingConfig`)

---

## Architecture Patterns

### Dependency Injection

- Use constructor injection for dependencies
- Define dependencies as protocols/interfaces
- Enable easy testing with mock implementations

```python
class EntityExtractor:
    def __init__(
        self,
        llm: LLMProvider,  # Protocol, not concrete class
        ontology_service: OntologyService,
        config: ExtractionConfig
    ) -> None:
        self._llm = llm
        self._ontology = ontology_service
        self._config = config
```

### Protocol-Based Design

- Define `Protocol` classes for all major interfaces
- Use `@runtime_checkable` for protocols that need isinstance() checks
- Prefer composition over inheritance

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class DocumentLoader(Protocol):
    def load(self, path: Path) -> Document: ...
    def supported_extensions(self) -> list[str]: ...
```

### Dataclasses for Data Models

- Use `@dataclass` for internal data structures
- Use `Pydantic BaseModel` for external APIs and configuration
- Use `field(default_factory=...)` for mutable defaults

```python
from dataclasses import dataclass, field

@dataclass
class ExtractedEntity:
    id: str
    label: str
    entity_type: str
    confidence: float = 0.0
    evidence: list[Evidence] = field(default_factory=list)
```

### Error Handling

- Define domain-specific exception hierarchy
- Always include context in error messages
- Use `from` for exception chaining

```python
class KGBuilderError(Exception):
    """Base exception for KGBuilder."""

class DocumentLoadError(KGBuilderError):
    """Error loading a document."""
    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(f"Failed to load {path}: {reason}")
        self.path = path
        self.reason = reason

# Usage
try:
    doc = loader.load(path)
except IOError as e:
    raise DocumentLoadError(path, str(e)) from e
```

---

## Module Organization

```
src/kgbuilder/
├── __init__.py
├── core/                 # Shared abstractions
│   ├── __init__.py
│   ├── protocols.py      # All Protocol definitions
│   ├── models.py         # Shared data models
│   ├── exceptions.py     # Exception hierarchy
│   └── config.py         # Configuration models
├── document/             # Document processing
│   ├── __init__.py
│   ├── loaders/          # Document loaders
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── pdf.py
│   │   └── office.py
│   ├── chunking/         # Chunking strategies
│   │   ├── __init__.py
│   │   └── strategies.py
│   └── service.py        # DocumentService orchestrator
├── embedding/            # Embedding operations
├── extraction/           # Entity/relation extraction
├── assembly/             # KG assembly
├── validation/           # Validation pipeline
├── storage/              # Database connectors
└── agents/               # Agent implementations
```

### Import Guidelines

- Use absolute imports from package root
- Group imports: stdlib, third-party, local
- Use `__all__` to define public API

```python
# Good
from kgbuilder.core.protocols import DocumentLoader
from kgbuilder.document.loaders import PDFLoader

# In __init__.py
__all__ = ["DocumentLoader", "Document", "load_document"]
```

---

## Testing Guidelines

### Test Structure

- Mirror source structure in tests/
- Use `pytest` with fixtures
- Name test files `test_<module>.py`
- Name test functions `test_<function>_<scenario>`

```python
# tests/document/test_loaders.py

import pytest
from pathlib import Path
from kgbuilder.document.loaders import PDFLoader

class TestPDFLoader:
    @pytest.fixture
    def loader(self) -> PDFLoader:
        return PDFLoader()
    
    @pytest.fixture
    def sample_pdf(self, tmp_path: Path) -> Path:
        # Create or copy test PDF
        ...
    
    def test_load_valid_pdf_returns_document(
        self, 
        loader: PDFLoader, 
        sample_pdf: Path
    ) -> None:
        doc = loader.load(sample_pdf)
        assert doc.content
        assert doc.file_type == FileType.PDF
    
    def test_load_missing_file_raises_error(self, loader: PDFLoader) -> None:
        with pytest.raises(DocumentLoadError):
            loader.load(Path("/nonexistent.pdf"))
```

### Mocking LLM Calls

- Always mock LLM calls in unit tests
- Use deterministic responses for reproducibility
- Create reusable fixtures for common mocks

```python
@pytest.fixture
def mock_llm() -> MagicMock:
    llm = MagicMock(spec=LLMProvider)
    llm.generate.return_value = '{"entities": []}'
    llm.model_name = "test-model"
    return llm
```

---

## Configuration

### Pydantic Settings

```python
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

class LLMConfig(BaseModel):
    model: str = "llama3.1:8b"
    base_url: str = "http://localhost:11434"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=1)

class Settings(BaseSettings):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    vector_db_url: str = "http://localhost:6333"
    neo4j_uri: str = "bolt://localhost:7687"
    
    class Config:
        env_prefix = "KGBUILDER_"
        env_nested_delimiter = "__"
```

---

## Logging

- Use `structlog` for structured logging
- Include context in log messages
- Use appropriate log levels

```python
import structlog

logger = structlog.get_logger(__name__)

def process_document(doc: Document) -> None:
    logger.info("processing_document", doc_id=doc.id, file_type=doc.file_type)
    try:
        # Process
        logger.debug("chunks_created", doc_id=doc.id, chunk_count=len(chunks))
    except Exception as e:
        logger.error("processing_failed", doc_id=doc.id, error=str(e))
        raise
```

---

## Async Guidelines

- Use `async/await` for I/O-bound operations
- Provide both sync and async variants where appropriate
- Use `asyncio.gather` for concurrent operations

```python
async def embed_batch_async(
    self,
    texts: list[str],
    concurrency: int = 10
) -> list[NDArray[np.float32]]:
    semaphore = asyncio.Semaphore(concurrency)
    
    async def embed_one(text: str) -> NDArray[np.float32]:
        async with semaphore:
            return await self._embed_async(text)
    
    return await asyncio.gather(*[embed_one(t) for t in texts])
```

---

## Git Commit Guidelines

- Use conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`
- Reference issues: `feat: add PDF loader (#12)`
- Keep commits atomic and focused

---

## Pre-commit Hooks

The project uses these pre-commit hooks:
- `ruff` - Linting and formatting
- `mypy` - Type checking
- `pytest` - Run fast tests

---

## VS Code Settings

Recommended settings for this project:

```json
{
  "python.analysis.typeCheckingMode": "strict",
  "python.formatting.provider": "black",
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  },
  "[python]": {
    "editor.rulers": [100]
  }
}
```
