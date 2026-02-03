"""Validation pipeline for Knowledge Graph quality assurance.

Provides a comprehensive validation framework with:
- SHACL shape-based constraint validation
- Semantic rule execution engine
- Conflict and duplicate detection
- Multi-format reporting

Phase 8 Implementation: Comprehensive KG Validation Pipeline
See Planning/PHASE_8_PLAN.md for detailed specifications.

Public API:
    Models:
    - ValidationResult: Aggregated validation outcome
    - ValidationViolation: Individual constraint violation
    - RuleViolation: Semantic rule violation
    - Conflict: Detected conflict in KG
    - DuplicateSet: Duplicate entity group
    - ViolationSeverity: Severity enum
    - ConflictType: Conflict type enum

    Validators:
    - SHACLValidator: SHACL constraint validation
    - RulesEngine: Semantic rule execution
    - ConsistencyChecker: Conflict detection

    Semantic Rules:
    - SemanticRule: Base class for custom rules
    - InversePropertyRule: Validate inverse relations
    - TransitiveRule: Validate transitive closure
    - DomainRangeRule: Validate domain/range constraints
    - FunctionalPropertyRule: Validate functional properties
"""

from kgbuilder.validation.consistency_checker import ConsistencyChecker, ConsistencyReport
from kgbuilder.validation.models import (
    Conflict,
    ConflictType,
    DuplicateSet,
    RuleViolation,
    ValidationResult,
    ValidationViolation,
    ViolationSeverity,
)
from kgbuilder.validation.rules_engine import (
    DomainRangeRule,
    FunctionalPropertyRule,
    InversePropertyRule,
    RulesEngine,
    SemanticRule,
    TransitiveRule,
)
from kgbuilder.validation.shacl_validator import SHACLValidator

__all__ = [
    "ValidationResult",
    "ValidationViolation",
    "ViolationSeverity",
    "RuleViolation",
    "Conflict",
    "ConflictType",
    "DuplicateSet",
    "SHACLValidator",
    "RulesEngine",
    "SemanticRule",
    "InversePropertyRule",
    "TransitiveRule",
    "DomainRangeRule",
    "FunctionalPropertyRule",
    "ConsistencyChecker",
    "ConsistencyReport",
]

__all__ = [
    "Validator",
    "ValidationReport",
    "ValidationViolation",
    "SHACLValidator",
    "OntologyValidator",
    "CompetencyQuestionValidator",
]

__all__ = []
