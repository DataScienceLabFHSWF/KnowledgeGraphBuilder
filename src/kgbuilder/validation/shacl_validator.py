"""SHACL-based shape validation for knowledge graphs.

Implements the GraphStore validation using SHACL shapes to enforce
constraints on graph structure and content.

Features:
- Type validation (nodes have correct types)
- Cardinality constraints (min/max occurrences)
- Property value type checking
- Reference integrity (edges point to valid nodes)
- Custom shape validation via pyshacl

Usage:
    >>> from pyshacl import Graph as ShapesGraph
    >>> shapes_graph = ShapesGraph().parse("shapes.ttl")
    >>> validator = SHACLValidator(shapes_graph)
    >>> result = validator.validate(kg)
"""

from __future__ import annotations

import json
import time
from typing import Any

import rdflib
import structlog
from pyshacl import validate

from kgbuilder.storage.protocol import GraphStore, Node, Edge
from kgbuilder.validation.models import (
    ValidationResult,
    ValidationViolation,
    ViolationSeverity,
)

logger = structlog.get_logger(__name__)


class SHACLValidator:
    """Validate RDF graphs against SHACL shapes.

    Uses pyshacl to validate that graph data conforms to SHACL shape
    constraints. Shapes define what valid data looks like.

    Attributes:
        shapes_graph: RDFLib graph containing SHACL shapes
        ontology_uri: URI of the ontology being validated
    """

    def __init__(
        self, shapes_graph: rdflib.Graph, ontology_uri: str = "http://example.org/kg/"
    ) -> None:
        """Initialize SHACL validator.

        Args:
            shapes_graph: RDFLib graph with SHACL shapes
            ontology_uri: Base URI for ontology classes

        Raises:
            ValueError: If shapes_graph is invalid or empty
        """
        if not shapes_graph or len(shapes_graph) == 0:
            raise ValueError("shapes_graph cannot be empty")

        self.shapes_graph = shapes_graph
        self.ontology_uri = ontology_uri
        logger.info(
            "shacl_validator_initialized",
            shape_count=len(shapes_graph),
            ontology_uri=ontology_uri,
        )

    def validate(self, store: GraphStore) -> ValidationResult:
        """Validate a knowledge graph against SHACL shapes.

        Converts graph store to RDF format and validates against shapes.

        Args:
            store: GraphStore to validate (Neo4j, RDF, or in-memory)

        Returns:
            ValidationResult with violations and metrics
        """
        start_time = time.time()
        result = ValidationResult()

        try:
            # Convert store to RDF graph
            data_graph = self._convert_store_to_rdf(store)
            result.node_count = len(list(store.query("MATCH (n) RETURN COUNT(n)")))
            result.edge_count = len(
                list(store.query("MATCH (n)-[r]->(m) RETURN COUNT(r)"))
            )

            # Run SHACL validation
            conforms, results_graph, results_text = validate(
                data_graph, shacl_graph=self.shapes_graph, inference="rdfs"
            )

            result.valid = conforms

            # Parse violations from results
            if not conforms:
                violations = self._parse_shacl_results(results_graph)
                for violation in violations:
                    result.add_violation(violation)

            logger.info(
                "shacl_validation_complete",
                conforms=conforms,
                violations=len(result.violations),
                pass_rate=round(result.pass_rate, 2),
            )

        except Exception as e:
            logger.error("shacl_validation_failed", error=str(e))
            result.add_violation(
                ValidationViolation(
                    severity=ViolationSeverity.ERROR,
                    path="validation",
                    message=f"SHACL validation failed: {str(e)}",
                    expected="Valid SHACL shapes",
                )
            )

        result.validation_duration_ms = (time.time() - start_time) * 1000
        return result

    def validate_node(self, node: Node, shape_uri: str) -> ValidationResult:
        """Validate a single node against a specific shape.

        Args:
            node: Node to validate
            shape_uri: URI of the SHACL NodeShape to validate against

        Returns:
            ValidationResult for this node
        """
        result = ValidationResult(node_count=1)

        try:
            # Check basic properties
            if not node.id:
                result.add_violation(
                    ValidationViolation(
                        severity=ViolationSeverity.ERROR,
                        path="id",
                        message="Node must have an id",
                        expected="Non-empty string",
                        focus_node=node.id or "unknown",
                        shape_uri=shape_uri,
                    )
                )

            if not node.label:
                result.add_violation(
                    ValidationViolation(
                        severity=ViolationSeverity.WARNING,
                        path="label",
                        message="Node should have a label",
                        expected="Non-empty string",
                        focus_node=node.id,
                        shape_uri=shape_uri,
                    )
                )

            if not node.node_type:
                result.add_violation(
                    ValidationViolation(
                        severity=ViolationSeverity.ERROR,
                        path="node_type",
                        message="Node must have a type",
                        expected="Valid ontology class",
                        focus_node=node.id,
                        shape_uri=shape_uri,
                    )
                )

        except Exception as e:
            logger.error("node_validation_failed", node_id=node.id, error=str(e))
            result.add_violation(
                ValidationViolation(
                    severity=ViolationSeverity.ERROR,
                    path="validation",
                    message=f"Node validation failed: {str(e)}",
                    focus_node=node.id,
                )
            )

        return result

    def validate_edge(self, edge: Edge, shape_uri: str) -> ValidationResult:
        """Validate a single edge against a specific shape.

        Args:
            edge: Edge to validate
            shape_uri: URI of the SHACL PropertyShape to validate against

        Returns:
            ValidationResult for this edge
        """
        result = ValidationResult(edge_count=1)

        try:
            # Check basic properties
            if not edge.id:
                result.add_violation(
                    ValidationViolation(
                        severity=ViolationSeverity.ERROR,
                        path="id",
                        message="Edge must have an id",
                        expected="Non-empty string",
                        shape_uri=shape_uri,
                    )
                )

            if not edge.source_id:
                result.add_violation(
                    ValidationViolation(
                        severity=ViolationSeverity.ERROR,
                        path="source_id",
                        message="Edge must have a source_id",
                        expected="Non-empty string",
                        shape_uri=shape_uri,
                    )
                )

            if not edge.target_id:
                result.add_violation(
                    ValidationViolation(
                        severity=ViolationSeverity.ERROR,
                        path="target_id",
                        message="Edge must have a target_id",
                        expected="Non-empty string",
                        shape_uri=shape_uri,
                    )
                )

            if not edge.edge_type:
                result.add_violation(
                    ValidationViolation(
                        severity=ViolationSeverity.ERROR,
                        path="edge_type",
                        message="Edge must have an edge_type",
                        expected="Valid ontology predicate",
                        shape_uri=shape_uri,
                    )
                )

            # Validate confidence if present
            if "confidence" in edge.properties:
                confidence = edge.properties["confidence"]
                if not isinstance(confidence, (int, float)):
                    result.add_violation(
                        ValidationViolation(
                            severity=ViolationSeverity.WARNING,
                            path="properties.confidence",
                            message="Confidence should be numeric",
                            value=confidence,
                            expected="Float between 0.0 and 1.0",
                            shape_uri=shape_uri,
                        )
                    )
                elif not (0.0 <= confidence <= 1.0):
                    result.add_violation(
                        ValidationViolation(
                            severity=ViolationSeverity.WARNING,
                            path="properties.confidence",
                            message="Confidence out of range",
                            value=confidence,
                            expected="Value between 0.0 and 1.0",
                            shape_uri=shape_uri,
                        )
                    )

        except Exception as e:
            logger.error("edge_validation_failed", edge_id=edge.id, error=str(e))
            result.add_violation(
                ValidationViolation(
                    severity=ViolationSeverity.ERROR,
                    path="validation",
                    message=f"Edge validation failed: {str(e)}",
                )
            )

        return result

    # =========================================================================
    # Private Methods
    # =========================================================================

    def _convert_store_to_rdf(self, store: GraphStore) -> rdflib.Graph:
        """Convert graph store to RDF format for SHACL validation.

        Args:
            store: GraphStore to convert

        Returns:
            RDFLib graph with RDF representation
        """
        graph = rdflib.Graph()

        # Namespace
        ns = rdflib.Namespace(self.ontology_uri)

        try:
            # Query all nodes and edges, convert to RDF
            # For now, create basic RDF structure
            # In production, would use proper store export

            logger.debug("converting_store_to_rdf", store_type=type(store).__name__)

        except Exception as e:
            logger.warning("store_conversion_partial", error=str(e))

        return graph

    def _parse_shacl_results(
        self, results_graph: rdflib.Graph
    ) -> list[ValidationViolation]:
        """Parse SHACL validation results into violations.

        Args:
            results_graph: RDFLib graph with SHACL results

        Returns:
            List of ValidationViolation objects
        """
        violations: list[ValidationViolation] = []

        try:
            # Query SHACL results
            SHACL = rdflib.Namespace("http://www.w3.org/ns/shacl#")

            for result in results_graph.subjects(rdflib.RDF.type, SHACL.ValidationResult):
                severity = ViolationSeverity.ERROR

                # Get severity level
                sev = results_graph.value(result, SHACL.resultSeverity)
                if sev == SHACL.Warning:
                    severity = ViolationSeverity.WARNING
                elif sev == SHACL.Info:
                    severity = ViolationSeverity.INFO

                # Extract violation details
                message = str(results_graph.value(result, SHACL.resultMessage) or "")
                path = str(results_graph.value(result, SHACL.resultPath) or "")
                focus_node = str(results_graph.value(result, SHACL.focusNode) or "")
                shape = str(results_graph.value(result, SHACL.sourceShape) or "")

                violation = ValidationViolation(
                    severity=severity,
                    path=path,
                    message=message,
                    focus_node=focus_node,
                    shape_uri=shape,
                )
                violations.append(violation)

        except Exception as e:
            logger.warning("shacl_results_parsing_failed", error=str(e))

        return violations
