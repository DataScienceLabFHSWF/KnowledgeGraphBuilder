# ontology-hitl — Core Data Models

These go in `src/ontology_hitl/core/models.py`.

```python
"""Core data models for ontology extension workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal


class ProposalStatus(str, Enum):
    """Status of an ontology class proposal."""
    PROPOSED = "proposed"
    UNDER_REVIEW = "under_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


@dataclass
class ExtractedEntitySummary:
    """Lightweight entity reference from KGB extraction checkpoint."""
    label: str
    entity_type: str
    confidence: float
    frequency: int  # How many chunks/documents mention this
    source_documents: list[str] = field(default_factory=list)
    evidence_snippets: list[str] = field(default_factory=list)


@dataclass
class GapCandidate:
    """Entity type not covered by current ontology."""
    entity_type: str
    representative_label: str
    examples: list[str]
    frequency: int
    avg_confidence: float
    closest_seed_class: str | None = None
    semantic_distance: float = 1.0  # 0 = identical, 1 = unrelated


@dataclass
class PropertyDef:
    """Proposed property for a class."""
    name: str
    datatype: str  # "xsd:string", "xsd:integer", etc.
    description: str
    required: bool = False
    max_count: int | None = None


@dataclass
class RelationDef:
    """Proposed relation (ObjectProperty)."""
    name: str
    domain: str  # class label
    range: str  # class label
    description: str
    inverse_name: str | None = None
    cardinality: str = "0..*"  # "1..1", "0..1", "0..*", "1..*"


@dataclass
class ProposedClass:
    """Candidate new ontology class."""
    id: str
    label: str
    definition: str
    parent_uri: str  # URI of seed class to be subClassOf
    parent_label: str
    examples: list[str] = field(default_factory=list)
    frequency: int = 0
    confidence: float = 0.0
    suggested_properties: list[PropertyDef] = field(default_factory=list)
    suggested_relations: list[RelationDef] = field(default_factory=list)
    status: ProposalStatus = ProposalStatus.PROPOSED
    source_gap_candidates: list[str] = field(default_factory=list)


@dataclass
class ReviewDecision:
    """Expert feedback on a proposed class."""
    proposal_id: str
    reviewer: str
    timestamp: datetime = field(default_factory=datetime.now)
    decision: Literal["accepted", "rejected", "needs_revision"] = "needs_revision"
    rationale: str = ""
    suggested_changes: dict[str, str] = field(default_factory=dict)
    confidence_in_decision: float = 0.5


@dataclass
class OntologyVersion:
    """Metadata for an ontology version."""
    version_id: str
    parent_version: str | None
    timestamp: datetime = field(default_factory=datetime.now)
    added_classes: list[str] = field(default_factory=list)
    removed_classes: list[str] = field(default_factory=list)
    added_relations: list[str] = field(default_factory=list)
    total_classes: int = 0
    total_relations: int = 0
    notes: str = ""


@dataclass
class OntologyDiff:
    """Change summary between two ontology versions."""
    from_version: str
    to_version: str
    added_classes: list[str] = field(default_factory=list)
    removed_classes: list[str] = field(default_factory=list)
    added_relations: list[tuple[str, str, str]] = field(default_factory=list)
    removed_relations: list[tuple[str, str, str]] = field(default_factory=list)
    cq_coverage_before: float = 0.0
    cq_coverage_after: float = 0.0
    entity_coverage_before: float = 0.0
    entity_coverage_after: float = 0.0


@dataclass
class GapReport:
    """Output of gap analysis."""
    ontology_version: str
    total_extracted_entities: int
    covered_entities: int
    uncovered_entities: int
    coverage_pct: float
    gap_candidates: list[GapCandidate] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class IterationResult:
    """Summary of one iteration cycle."""
    iteration_id: str
    ontology_version_before: str
    ontology_version_after: str
    proposals_generated: int
    proposals_accepted: int
    proposals_rejected: int
    cq_coverage_before: float
    cq_coverage_after: float
    entity_coverage_before: float
    entity_coverage_after: float
    timestamp: datetime = field(default_factory=datetime.now)
```

---

## Protocols — `src/ontology_hitl/core/protocols.py`

```python
"""Protocol definitions for ontology extension components."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from ontology_hitl.core.models import (
    ExtractedEntitySummary,
    GapCandidate,
    GapReport,
    ProposedClass,
    ReviewDecision,
)


@runtime_checkable
class OntologyProvider(Protocol):
    """Interface to ontology store (Fuseki)."""

    def get_all_classes(self) -> list[str]: ...
    def get_class_hierarchy(self) -> dict[str, list[str]]: ...
    def add_class(self, owl_turtle: str) -> None: ...
    def remove_class(self, class_uri: str) -> None: ...
    def sparql_query(self, query: str) -> list[dict]: ...


@runtime_checkable
class LLMProvider(Protocol):
    """Interface to LLM for definition generation."""

    def generate(self, prompt: str, **kwargs: object) -> str: ...


@runtime_checkable
class CheckpointReader(Protocol):
    """Reads KGB extraction checkpoints."""

    def load_entities(self, path: Path) -> list[ExtractedEntitySummary]: ...


@runtime_checkable
class ReviewBackend(Protocol):
    """Stores and retrieves review decisions."""

    def save_decision(self, decision: ReviewDecision) -> None: ...
    def get_decisions(self, proposal_id: str) -> list[ReviewDecision]: ...
    def get_all_decisions(self) -> list[ReviewDecision]: ...
```

---

## Config — `src/ontology_hitl/core/config.py`

```python
"""Configuration for ontology-hitl."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # Fuseki
    fuseki_url: str = "http://localhost:3030"
    fuseki_dataset: str = "kgbuilder"
    fuseki_staging_dataset: str = "kgbuilder-staging"
    fuseki_user: str = "admin"
    fuseki_password: str = ""

    # LLM (for definition generation)
    ollama_url: str = "http://localhost:18134"
    ollama_model: str = "qwen3:8b"
    llm_temperature: float = 0.5

    # Gap Analysis
    min_entity_frequency: int = 3
    semantic_similarity_threshold: float = 0.65
    gap_confidence_threshold: float = 0.6

    # Review
    min_reviewers_per_class: int = 1
    require_min_expert_agreement: float = 0.75

    # Evaluation targets
    cq_answerability_target: float = 0.80
    entity_coverage_target: float = 0.80

    # Paths
    seed_ontology_path: str = "data/seed_ontology/plan-ontology-v1.0.owl"
    iterations_dir: str = "data/iterations"
    exports_dir: str = "data/exports"

    class Config:
        env_prefix = "HITL_"
        env_file = ".env"
```

---

## Exceptions — `src/ontology_hitl/core/exceptions.py`

```python
"""Exception hierarchy for ontology-hitl."""

from __future__ import annotations


class OntologyHITLError(Exception):
    """Base exception."""


class GapAnalysisError(OntologyHITLError):
    """Error during gap analysis."""


class SchemaUpdateError(OntologyHITLError):
    """Error updating ontology schema."""


class SHACLValidationError(OntologyHITLError):
    """SHACL constraint violation."""

    def __init__(self, violations: list[str]) -> None:
        super().__init__(f"SHACL validation failed: {len(violations)} violations")
        self.violations = violations


class ReviewError(OntologyHITLError):
    """Error in review workflow."""


class CheckpointLoadError(OntologyHITLError):
    """Error loading KGB checkpoint."""

    def __init__(self, path: str, reason: str) -> None:
        super().__init__(f"Failed to load checkpoint {path}: {reason}")
        self.path = path
        self.reason = reason
```
