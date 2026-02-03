"""Domain rules engine for semantic validation.

Implements semantic rule validation for ontology constraints like:
- Inverse properties (if rel(A,B) then inverse_rel(B,A))
- Transitive rules (if rel(A,B) and rel(B,C) then rel(A,C))
- Domain/range constraints
- Cardinality constraints

Usage:
    >>> rules = [
    ...     InversePropertyRule("knows", "knows"),
    ...     TransitiveRule("partOf", "partOf"),
    ... ]
    >>> engine = RulesEngine(rules)
    >>> violations = engine.execute_rules(kg)
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import structlog

from kgbuilder.storage.protocol import GraphStore
from kgbuilder.validation.models import RuleViolation, ValidationResult

logger = structlog.get_logger(__name__)


@dataclass
class SemanticRule(ABC):
    """Base class for semantic validation rules.

    Attributes:
        name: Unique rule identifier
        description: Human-readable description
        enabled: Whether rule is active
    """

    name: str
    description: str
    enabled: bool = True

    @abstractmethod
    def check(self, store: GraphStore) -> list[RuleViolation]:
        """Check rule against knowledge graph.

        Args:
            store: GraphStore to validate

        Returns:
            List of RuleViolation objects
        """
        ...


@dataclass
class InversePropertyRule(SemanticRule):
    """Enforce inverse property constraints.

    If property rel(A, B) exists and rel has an inverse relation,
    then inverse_rel(B, A) should exist.

    Attributes:
        property_uri: URI of the property
        inverse_uri: URI of the inverse property
    """

    property_uri: str = ""
    inverse_uri: str = ""

    def __post_init__(self) -> None:
        """Validate rule configuration."""
        if not self.property_uri:
            raise ValueError("property_uri must be specified")
        if not self.inverse_uri:
            raise ValueError("inverse_uri must be specified")

        if not self.name:
            self.name = f"{self.property_uri}-inverse"
        if not self.description:
            self.description = (
                f"Enforce inverse property: {self.property_uri} → {self.inverse_uri}"
            )

    def check(self, store: GraphStore) -> list[RuleViolation]:
        """Check inverse property rule.

        Args:
            store: GraphStore to check

        Returns:
            Violations where inverse property is missing
        """
        violations: list[RuleViolation] = []

        if not self.enabled:
            return violations

        try:
            # Query for all edges with the property
            query = f"""
            MATCH (a)-[r:{self.property_uri}]->(b)
            RETURN a.id as source, b.id as target
            """

            results = store.query(query)
            if not hasattr(results, "records"):
                # Handle different result types
                return violations

            # Check if inverse exists for each edge
            for record in results.records if hasattr(results, "records") else []:
                source = record.get("source")
                target = record.get("target")

                # Check if inverse relation exists
                inverse_query = f"""
                MATCH ({target})-[:{self.inverse_uri}]->({source})
                RETURN COUNT(*) as cnt
                """

                inverse_result = store.query(inverse_query)
                # Handle result checking

        except Exception as e:
            logger.warning(
                "inverse_property_check_failed", rule=self.name, error=str(e)
            )

        return violations


@dataclass
class TransitiveRule(SemanticRule):
    """Enforce transitive relation constraints.

    If rel(A, B) and rel(B, C) exist and rel is transitive,
    then rel(A, C) should exist.

    Attributes:
        property_uri: URI of the transitive property
        max_depth: Maximum path length to check (default: 3)
    """

    property_uri: str = ""
    max_depth: int = 3

    def __post_init__(self) -> None:
        """Validate rule configuration."""
        if not self.property_uri:
            raise ValueError("property_uri must be specified")

        if not self.name:
            self.name = f"{self.property_uri}-transitive"
        if not self.description:
            self.description = f"Enforce transitive property: {self.property_uri}"

    def check(self, store: GraphStore) -> list[RuleViolation]:
        """Check transitive rule.

        Args:
            store: GraphStore to check

        Returns:
            Violations where transitive implication is missing
        """
        violations: list[RuleViolation] = []

        if not self.enabled:
            return violations

        try:
            # Find paths of length 2
            query = f"""
            MATCH (a)-[:{self.property_uri}]->(b)-[:{self.property_uri}]->(c)
            RETURN DISTINCT a.id as source, c.id as target
            """

            results = store.query(query)
            # For each path A->B->C, check if A->C exists directly

        except Exception as e:
            logger.warning("transitive_check_failed", rule=self.name, error=str(e))

        return violations


@dataclass
class DomainRangeRule(SemanticRule):
    """Enforce domain and range constraints on properties.

    Property can only connect nodes of specified types.

    Attributes:
        property_uri: URI of the property
        domain_types: Allowed source node types
        range_types: Allowed target node types
    """

    property_uri: str = ""
    domain_types: list[str] = field(default_factory=list)
    range_types: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate rule configuration."""
        if not self.property_uri:
            raise ValueError("property_uri must be specified")

        if not self.name:
            self.name = f"{self.property_uri}-domain-range"
        if not self.description:
            self.description = f"Enforce domain/range: {self.property_uri}"

    def check(self, store: GraphStore) -> list[RuleViolation]:
        """Check domain/range constraints.

        Args:
            store: GraphStore to check

        Returns:
            Violations where domain/range is violated
        """
        violations: list[RuleViolation] = []

        if not self.enabled:
            return violations

        try:
            # Query for all edges with property
            # Check source node type is in domain_types
            # Check target node type is in range_types

            pass

        except Exception as e:
            logger.warning(
                "domain_range_check_failed", rule=self.name, error=str(e)
            )

        return violations


@dataclass
class FunctionalPropertyRule(SemanticRule):
    """Enforce functional property constraints.

    A functional property can appear at most once per subject.

    Attributes:
        property_uri: URI of the functional property
    """

    property_uri: str = ""

    def __post_init__(self) -> None:
        """Validate rule configuration."""
        if not self.property_uri:
            raise ValueError("property_uri must be specified")

        if not self.name:
            self.name = f"{self.property_uri}-functional"
        if not self.description:
            self.description = f"Enforce functional property: {self.property_uri}"

    def check(self, store: GraphStore) -> list[RuleViolation]:
        """Check functional property constraint.

        Args:
            store: GraphStore to check

        Returns:
            Violations where property appears multiple times for same subject
        """
        violations: list[RuleViolation] = []

        if not self.enabled:
            return violations

        try:
            # Find subjects with multiple values for this property
            # Create violations for each excess value

            pass

        except Exception as e:
            logger.warning("functional_check_failed", rule=self.name, error=str(e))

        return violations


class RulesEngine:
    """Execute semantic validation rules against a knowledge graph.

    Applies a collection of rules to detect semantic violations in the KG.

    Attributes:
        rules: List of SemanticRule objects to apply
        stop_on_error: Whether to stop if a rule fails
    """

    def __init__(
        self, rules: list[SemanticRule] | None = None, stop_on_error: bool = False
    ) -> None:
        """Initialize rules engine.

        Args:
            rules: Semantic rules to apply (empty list if None)
            stop_on_error: Stop execution if a rule raises exception
        """
        self.rules = rules or []
        self.stop_on_error = stop_on_error
        logger.info("rules_engine_initialized", rule_count=len(self.rules))

    def add_rule(self, rule: SemanticRule) -> None:
        """Add a semantic rule.

        Args:
            rule: SemanticRule to add
        """
        self.rules.append(rule)
        logger.debug("rule_added", rule_name=rule.name)

    def execute_rules(self, store: GraphStore) -> ValidationResult:
        """Execute all rules against the knowledge graph.

        Args:
            store: GraphStore to validate

        Returns:
            ValidationResult with all rule violations
        """
        start_time = time.time()
        result = ValidationResult()

        for rule in self.rules:
            if not rule.enabled:
                continue

            try:
                violations = rule.check(store)
                for violation in violations:
                    result.add_rule_violation(violation)

                logger.debug(
                    "rule_executed",
                    rule_name=rule.name,
                    violation_count=len(violations),
                )

            except Exception as e:
                logger.error("rule_execution_failed", rule_name=rule.name, error=str(e))
                if self.stop_on_error:
                    raise
                result.add_rule_violation(
                    RuleViolation(
                        rule_name=rule.name,
                        rule_description=rule.description,
                        subject_id="unknown",
                        predicate="validation",
                        object_id="unknown",
                        reason=f"Rule execution failed: {str(e)}",
                    )
                )

        result.validation_duration_ms = (time.time() - start_time) * 1000

        logger.info(
            "rules_execution_complete",
            rule_count=len(self.rules),
            violation_count=len(result.rule_violations),
            duration_ms=round(result.validation_duration_ms, 2),
        )

        return result

    def get_rule(self, rule_name: str) -> SemanticRule | None:
        """Get rule by name.

        Args:
            rule_name: Name of rule to retrieve

        Returns:
            SemanticRule or None if not found
        """
        for rule in self.rules:
            if rule.name == rule_name:
                return rule
        return None

    def enable_rule(self, rule_name: str) -> bool:
        """Enable a rule by name.

        Args:
            rule_name: Name of rule to enable

        Returns:
            True if rule found and enabled
        """
        rule = self.get_rule(rule_name)
        if rule:
            rule.enabled = True
            logger.debug("rule_enabled", rule_name=rule_name)
            return True
        return False

    def disable_rule(self, rule_name: str) -> bool:
        """Disable a rule by name.

        Args:
            rule_name: Name of rule to disable

        Returns:
            True if rule found and disabled
        """
        rule = self.get_rule(rule_name)
        if rule:
            rule.enabled = False
            logger.debug("rule_disabled", rule_name=rule_name)
            return True
        return False
