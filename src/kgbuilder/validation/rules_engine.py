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

    Backwards-compatibility: `name` and `description` are optional so rule
    subclasses can be instantiated with positional configuration args only.
    """

    name: str = ""
    description: str = ""
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

    @staticmethod
    def _find_missing_inverses(
        edges: list[Any],
        property_uri: str,
        inverse_uri: str,
        rule_name: str,
        rule_description: str,
    ) -> list[RuleViolation]:
        """Helper to identify missing inverse edges.

        Args:
            edges: List of Edge objects
            property_uri: URI being checked
            inverse_uri: URI of the expected inverse
            rule_name: Name for violation records
            rule_description: Description for violation records

        Returns:
            List of RuleViolation instances for each missing inverse edge.
        """
        violations: list[RuleViolation] = []
        for edge in edges:
            if edge.edge_type != property_uri:
                continue

            inverse_exists = any(
                other.edge_type == inverse_uri
                and other.source_id == edge.target_id
                and other.target_id == edge.source_id
                for other in edges
            )

            if not inverse_exists:
                violations.append(
                    RuleViolation(
                        rule_name=rule_name,
                        rule_description=rule_description,
                        subject_id=edge.target_id,
                        predicate=inverse_uri,
                        object_id=edge.source_id,
                        reason=f"Missing inverse relation: {inverse_uri}({edge.target_id}, {edge.source_id})",
                    )
                )
        return violations

    def check(self, store: GraphStore) -> list[RuleViolation]:
        """Check inverse property rule using helper.

        Args:
            store: GraphStore to check

        Returns:
            Violations where inverse property is missing
        """
        if not self.enabled:
            return []

        try:
            logger.debug("checking_inverse_property", rule=self.name)
            violations = InversePropertyRule._find_missing_inverses(
                store.get_all_edges(), self.property_uri, self.inverse_uri, self.name, self.description
            )
            logger.info(
                "inverse_property_checked",
                rule=self.name,
                violation_count=len(violations),
            )
            return violations
        except Exception as e:
            logger.warning(
                "inverse_property_check_failed", rule=self.name, error=str(e)
            )
            return []


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

    @staticmethod
    def _find_missing_transitives(
        edges: list[Any],
        property_uri: str,
        rule_name: str,
        rule_description: str,
    ) -> list[RuleViolation]:
        """Detect missing transitive closures among a list of edges.

        Looks for patterns A->B and B->C without a direct A->C edge.
        """
        violations: list[RuleViolation] = []
        prop_edges = [e for e in edges if e.edge_type == property_uri]
        for e1 in prop_edges:
            for e2 in prop_edges:
                if e1.target_id != e2.source_id:
                    continue
                direct_exists = any(
                    de.source_id == e1.source_id
                    and de.target_id == e2.target_id
                    for de in prop_edges
                )
                if not direct_exists:
                    violations.append(
                        RuleViolation(
                            rule_name=rule_name,
                            rule_description=rule_description,
                            subject_id=e1.source_id,
                            predicate=property_uri,
                            object_id=e2.target_id,
                            reason=(
                                f"Missing transitive closure: {property_uri}"
                                f"({e1.source_id}, {e2.target_id}) via {e1.target_id}"
                            ),
                        )
                    )
        return violations

    def check(self, store: GraphStore) -> list[RuleViolation]:
        """Check transitive rule.

        Delegates the heavy lifting to the static helper `_find_missing_transitives`.
        """
        if not self.enabled:
            return []

        try:
            logger.debug("checking_transitive_property", rule=self.name)
            violations = TransitiveRule._find_missing_transitives(
                store.get_all_edges(), self.property_uri, self.name, self.description
            )
            logger.info(
                "transitive_checked",
                rule=self.name,
                violation_count=len(violations),
            )
            return violations

        except Exception as e:
            logger.warning("transitive_check_failed", rule=self.name, error=str(e))
            return []


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

        Validates that all edges with this property:
        - Have source nodes of types in domain_types
        - Have target nodes of types in range_types

        Args:
            store: GraphStore to check

        Returns:
            Violations where domain/range is violated
        """
        violations: list[RuleViolation] = []

        if not self.enabled:
            return violations

        try:
            logger.debug("checking_domain_range", rule=self.name)

            edges = store.get_all_edges()
            nodes_by_id = {n.id: n for n in store.get_all_nodes()}

            for edge in edges:
                if edge.edge_type != self.property_uri:
                    continue

                # Check source node type (domain)
                source_node = nodes_by_id.get(edge.source_id)
                if source_node and self.domain_types:
                    if source_node.node_type not in self.domain_types:
                        violations.append(
                            RuleViolation(
                                rule_name=self.name,
                                rule_description=self.description,
                                subject_id=edge.source_id,
                                predicate=self.property_uri,
                                object_id=edge.target_id,
                                reason=f"Domain violation: {edge.source_id} is {source_node.node_type}, expected one of {self.domain_types}",
                            )
                        )

                # Check target node type (range)
                target_node = nodes_by_id.get(edge.target_id)
                if target_node and self.range_types:
                    if target_node.node_type not in self.range_types:
                        violations.append(
                            RuleViolation(
                                rule_name=self.name,
                                rule_description=self.description,
                                subject_id=edge.source_id,
                                predicate=self.property_uri,
                                object_id=edge.target_id,
                                reason=f"Range violation: {edge.target_id} is {target_node.node_type}, expected one of {self.range_types}",
                            )
                        )

            logger.info(
                "domain_range_checked",
                rule=self.name,
                violation_count=len(violations),
            )

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

        A functional property can appear at most once per subject.
        Creates violations for subjects with multiple values.

        Args:
            store: GraphStore to check

        Returns:
            Violations where property appears multiple times for same subject
        """
        violations: list[RuleViolation] = []

        if not self.enabled:
            return violations

        try:
            logger.debug("checking_functional_property", rule=self.name)

            # Count edges by source for this property
            edges = store.get_all_edges()
            property_edges = [e for e in edges if e.edge_type == self.property_uri]

            # Count occurrences per source
            source_counts: dict[str, list] = {}
            for edge in property_edges:
                if edge.source_id not in source_counts:
                    source_counts[edge.source_id] = []
                source_counts[edge.source_id].append(edge)

            # Check for subjects with multiple values
            for subject_id, subject_edges in source_counts.items():
                if len(subject_edges) > 1:
                    # Create violation for each excess edge
                    for edge in subject_edges[1:]:  # Skip first, report excess
                        violations.append(
                            RuleViolation(
                                rule_name=self.name,
                                rule_description=self.description,
                                subject_id=subject_id,
                                predicate=self.property_uri,
                                object_id=edge.target_id,
                                reason=f"Functional property violation: {subject_id} has {len(subject_edges)} values for {self.property_uri}",
                            )
                        )

            logger.info(
                "functional_checked",
                rule=self.name,
                violation_count=len(violations),
            )

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

    @classmethod
    def from_ontology_service(
        cls, ontology_service: Any, stop_on_error: bool = False
    ) -> RulesEngine:
        """Create RulesEngine with rules derived from an ontology service.

        Queries the ontology for OWL property characteristics
        (transitive, symmetric, functional, inverse) and creates
        corresponding semantic rules automatically.

        Args:
            ontology_service: FusekiOntologyService (or compatible) with
                ``get_special_properties()`` method.
            stop_on_error: Stop execution if a rule raises exception.

        Returns:
            RulesEngine pre-populated with ontology-derived rules.
        """
        rules: list[SemanticRule] = []

        try:
            special = ontology_service.get_special_properties()

            # Transitive properties
            for prop in special.get("transitive", []):
                rules.append(
                    TransitiveRule(
                        name=f"{prop}-transitive",
                        description=f"Enforce transitive property: {prop}",
                        property_uri=prop,
                    )
                )

            # Symmetric properties (modelled as self-inverse)
            for prop in special.get("symmetric", []):
                rules.append(
                    InversePropertyRule(
                        name=f"{prop}-symmetric",
                        description=f"Enforce symmetric property: {prop}",
                        property_uri=prop,
                        inverse_uri=prop,
                    )
                )

            # Functional properties
            for prop in special.get("functional", []):
                rules.append(
                    FunctionalPropertyRule(
                        name=f"{prop}-functional",
                        description=f"Enforce functional property: {prop}",
                        property_uri=prop,
                    )
                )

            # Inverse property pairs
            for pair in special.get("inverse", []):
                if isinstance(pair, (list, tuple)) and len(pair) == 2:
                    rules.append(
                        InversePropertyRule(
                            name=f"{pair[0]}-inverse-{pair[1]}",
                            description=f"Enforce inverse: {pair[0]} ↔ {pair[1]}",
                            property_uri=pair[0],
                            inverse_uri=pair[1],
                        )
                    )

            logger.info(
                "rules_derived_from_ontology",
                transitive=len(special.get("transitive", [])),
                symmetric=len(special.get("symmetric", [])),
                functional=len(special.get("functional", [])),
                inverse=len(special.get("inverse", [])),
                total_rules=len(rules),
            )

        except Exception as e:
            logger.warning("ontology_rule_derivation_failed", error=str(e))

        return cls(rules=rules, stop_on_error=stop_on_error)

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
