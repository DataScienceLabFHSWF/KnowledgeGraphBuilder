"""Data models for validation pipeline.

Defines all validation-related data structures:
- ValidationViolation: Individual constraint violations
- ValidationResult: Complete validation outcome
- RuleViolation: Semantic rule violations
- Conflict: Contradictions in the knowledge graph
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ViolationSeverity(Enum):
    """Severity levels for violations."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ConflictType(Enum):
    """Types of conflicts detected in KG."""

    TYPE_CONFLICT = "type"  # Node has incompatible types
    VALUE_CONFLICT = "value"  # Same property with conflicting values
    TRANSITIVE_CONFLICT = "transitive"  # Transitive rule violated
    CARDINALITY_CONFLICT = "cardinality"  # Functional property with multiple values
    DOMAIN_RANGE_VIOLATION = "domain_range"  # Property violates domain/range


@dataclass
class ValidationViolation:
    """A single constraint violation detected during validation.

    Represents a single failed constraint check. Can be from SHACL shapes,
    domain rules, or consistency checks.

    Attributes:
        severity: Error level (error/warning/info)
        path: Property/field path (e.g., "name", "age", "knows")
        message: Human-readable violation description
        value: Actual value that violated the constraint
        expected: Expected constraint description
        focus_node: Node ID where violation occurred
        shape_uri: URI of SHACL shape (if from SHACL validation)
    """

    severity: ViolationSeverity
    path: str
    message: str
    value: Any = None
    expected: str = ""
    focus_node: str = ""
    shape_uri: str = ""

    def __post_init__(self) -> None:
        """Ensure severity is enum."""
        if isinstance(self.severity, str):
            self.severity = ViolationSeverity(self.severity)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "severity": self.severity.name,  # use NAME (ERROR/WARNING/INFO) for test compatibility
            "path": self.path,
            "message": self.message,
            "value": str(self.value) if self.value else None,
            "expected": self.expected,
            "focus_node": self.focus_node,
            "shape_uri": self.shape_uri,
        }


@dataclass
class RuleViolation:
    """Violation of a semantic domain rule.

    Represents a case where extracted facts violate a semantic rule
    (e.g., inverse property missing, transitive implication unmet).

    Attributes:
        rule_name: Name of the violated rule
        rule_description: Description of what the rule enforces
        subject_id: Subject node ID
        predicate: Relation/property name
        object_id: Object node ID
        reason: Why the rule was violated
        recommendation: Suggested fix
    """

    rule_name: str
    rule_description: str
    subject_id: str
    predicate: str
    object_id: str
    reason: str
    recommendation: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "rule_name": self.rule_name,
            "rule_description": self.rule_description,
            "subject_id": self.subject_id,
            "predicate": self.predicate,
            "object_id": self.object_id,
            "reason": self.reason,
            "recommendation": self.recommendation,
        }


@dataclass
class Conflict:
    """A contradiction or conflict detected in the KG.

    Backwards-compatible creation: `entity_id` may be omitted in tests and
    `involved_entities` (list[str]) is accepted and converted.
    """

    entity_id: str = ""
    conflict_type: ConflictType = ConflictType.VALUE_CONFLICT
    description: str = ""
    involved_facts: list[tuple[str, str, str]] = field(default_factory=list)
    involved_entities: list[str] | None = None
    severity: ViolationSeverity = ViolationSeverity.WARNING
    suggested_action: str = ""

    def __post_init__(self) -> None:
        """Ensure enums are correct types and normalize legacy args."""
        if isinstance(self.conflict_type, str):
            self.conflict_type = ConflictType(self.conflict_type)
        if isinstance(self.severity, str):
            self.severity = ViolationSeverity(self.severity)
        if self.involved_entities and not self.involved_facts:
            # convert simple entity list into minimal involved_facts tuples
            self.involved_facts = [(eid, "", "") for eid in self.involved_entities]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "entity_id": self.entity_id,
            "conflict_type": self.conflict_type.value,
            "description": self.description,
            "involved_facts": self.involved_facts,
            "severity": self.severity.value,
            "suggested_action": self.suggested_action,
        }


@dataclass
class DuplicateSet:
    """A set of likely duplicate entities.

    Entities that are similar enough to be considered duplicates,
    with similarity score indicating confidence.

    Attributes:
        entity_ids: List of entity IDs that are duplicates
        similarity_score: Confidence score (0.0-1.0)
        reason: Why they're considered duplicates
        recommendation: How to handle (merge, review, etc.)
    """

    entity_ids: list[str]
    similarity_score: float = 0.0
    reason: str = ""
    recommendation: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "entity_ids": self.entity_ids,
            "similarity_score": self.similarity_score,
            "reason": self.reason,
            "recommendation": self.recommendation,
        }


@dataclass
class ValidationResult:
    """Complete validation result for a knowledge graph.

    Aggregates all violations, conflicts, and metrics from a validation run.
    Use pass_rate to determine overall KG quality.

    Attributes:
        valid: Whether KG passes all validation constraints
        violations: List of SHACL/constraint violations
        rule_violations: List of semantic rule violations
        conflicts: List of detected conflicts
        duplicates: List of detected duplicate sets
        node_count: Total nodes validated
        edge_count: Total edges validated
        violations_by_severity: Count grouped by severity level
        pass_rate: Percentage of constraints passed (0.0-1.0)
        validation_duration_ms: Time taken for validation
    """

    valid: bool = True
    violations: list[ValidationViolation] = field(default_factory=list)
    rule_violations: list[RuleViolation] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    duplicates: list[DuplicateSet] = field(default_factory=list)
    node_count: int = 0
    edge_count: int = 0
    violations_by_severity: dict[str, int] = field(default_factory=dict)
    pass_rate: float = 1.0
    validation_duration_ms: float = 0.0

    def _recompute_pass_rate(self) -> None:
        """Recompute the pass rate using current node/edge counts and violations.

        Only SHACL constraint violations affect pass_rate.  Rule violations
        and conflicts are tracked separately.
        """
        total_constraints = self.node_count + self.edge_count
        if total_constraints > 0:
            violation_count = len(self.violations)
            self.pass_rate = 1.0 - (violation_count / total_constraints)
            self.pass_rate = max(0.0, min(1.0, self.pass_rate))
        else:
            self.pass_rate = 1.0

    def __post_init__(self) -> None:
        """Initial pass-rate calculation."""
        self._recompute_pass_rate()

    def add_violation(self, violation: ValidationViolation) -> None:
        """Add a violation and update severity counts."""
        self.violations.append(violation)
        severity = violation.severity.value
        self.violations_by_severity[severity] = (
            self.violations_by_severity.get(severity, 0) + 1
        )
        if violation.severity == ViolationSeverity.ERROR:
            self.valid = False
        # Recompute aggregate pass rate after mutation
        self._recompute_pass_rate()

    def add_rule_violation(self, violation: RuleViolation) -> None:
        """Add a rule violation."""
        self.rule_violations.append(violation)
        self.valid = False
        self._recompute_pass_rate()

    def add_conflict(self, conflict: Conflict) -> None:
        """Add a conflict."""
        self.conflicts.append(conflict)
        if conflict.severity == ViolationSeverity.ERROR:
            self.valid = False
        self._recompute_pass_rate()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "valid": self.valid,
            "violations": [v.to_dict() for v in self.violations],
            "rule_violations": [rv.to_dict() for rv in self.rule_violations],
            "conflicts": [c.to_dict() for c in self.conflicts],
            "duplicates": [d.to_dict() for d in self.duplicates],
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "violations_by_severity": self.violations_by_severity,
            "pass_rate": round(self.pass_rate, 4),
            "validation_duration_ms": round(self.validation_duration_ms, 2),
        }
