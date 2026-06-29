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

import time
from urllib.parse import quote

import rdflib
import structlog
from pyshacl import validate

from kgbuilder.storage.protocol import Edge, GraphStore, Node
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
            shapes_graph: RDFLib graph with SHACL shapes (may be empty for tests)
            ontology_uri: Base URI for ontology classes

        Notes:
            Allow empty rdflib.Graph() for unit tests — actual validation is
            performed by `pyshacl.validate()` which will be mocked in tests.
        """
        # Accept an rdflib.Graph instance (tests may pass an empty Graph).
        if shapes_graph is None:
            raise ValueError("shapes_graph cannot be None")

        self.shapes_graph = shapes_graph
        self.ontology_uri = ontology_uri.rstrip("/")
        logger.info(
            "shacl_validator_initialized",
            shape_count=len(shapes_graph),
            ontology_uri=self.ontology_uri,
        )

    def _make_uri(self, *parts: object) -> rdflib.URIRef:
        """Build a valid URIRef under the configured ontology base URI."""
        encoded = [quote(str(p), safe="") for p in parts if p is not None]
        return rdflib.URIRef(f"{self.ontology_uri}/{'/'.join(encoded)}")

    def validate(
        self, store: GraphStore, run_id: str | None = None,
    ) -> ValidationResult:
        """Validate a knowledge graph against SHACL shapes.

        Converts graph store to RDF format and validates against shapes.

        Args:
            store: GraphStore to validate (Neo4j, RDF, or in-memory)
            run_id: Optional experiment run identifier. When provided and the
                store exposes Cypher querying, only nodes and edges tagged with
                this ``run_id`` (top-level property) are converted to RDF and
                validated. This avoids contamination from prior runs that
                share the same Neo4j database.

        Returns:
            ValidationResult with violations and metrics
        """
        start_time = time.time()
        result = ValidationResult()

        try:
            # Convert store to RDF graph (optionally scoped by run_id)
            data_graph = self._convert_store_to_rdf(store, run_id=run_id)

            # Prefer using store.get_statistics() (implemented by stores such as Neo4j). Fall
            # back to SPARQL/Cypher queries if unavailable.
            try:
                stats = store.get_statistics()
                result.node_count = getattr(stats, "node_count", 0)
                result.edge_count = getattr(stats, "edge_count", 0)
            except Exception:
                try:
                    qr = store.query("MATCH (n) RETURN COUNT(n) AS cnt")
                    result.node_count = int(qr.records[0].get("cnt", 0)) if qr.records else 0
                except Exception:
                    result.node_count = 0
                try:
                    qr2 = store.query("MATCH (n)-[r]->(m) RETURN COUNT(r) AS cnt")
                    result.edge_count = int(qr2.records[0].get("cnt", 0)) if qr2.records else 0
                except Exception:
                    result.edge_count = 0

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

    def validate_node(self, node: Node, shape_uri: str = "") -> ValidationResult:
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

    def validate_edge(self, edge: Edge, shape_uri: str = "") -> ValidationResult:
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

    def _scoped_nodes_edges(
        self, store: GraphStore, run_id: str,
    ) -> tuple[list[Any], list[Any]]:
        """Materialize nodes and edges restricted to ``run_id`` via Cypher.

        Returns lightweight stand-in objects with the same attributes the
        downstream RDF conversion expects (``id``, ``label``, ``node_type``,
        ``properties`` for nodes; ``source_id``, ``target_id``, ``edge_type``,
        ``properties`` for edges).
        """
        # ---- nodes ----------------------------------------------------------
        node_q = (
            "MATCH (n {run_id: $run_id}) "
            "RETURN n.id AS id, labels(n) AS labels, n.label AS label, "
            "       n.node_type AS node_type, n.properties AS properties"
        )
        node_rows = store.query(node_q, params={"run_id": run_id})
        node_records = getattr(node_rows, "records", node_rows) or []

        nodes: list[Any] = []
        for r in node_records:
            get = r.get if isinstance(r, dict) else (lambda k, _r=r: getattr(_r, k, None))
            labels = get("labels") or []
            node_type = get("node_type") or (labels[0] if labels else "Thing")
            raw_props = get("properties")
            if isinstance(raw_props, str):
                try:
                    import json as _json
                    raw_props = _json.loads(raw_props)
                except Exception:
                    raw_props = {}
            properties = raw_props if isinstance(raw_props, dict) else {}
            nodes.append(
                type(
                    "_ScopedNode",
                    (),
                    {
                        "id": get("id"),
                        "label": get("label") or "",
                        "node_type": node_type,
                        "properties": properties,
                    },
                )()
            )

        # ---- edges ----------------------------------------------------------
        edge_q = (
            "MATCH (a {run_id: $run_id})-[r {run_id: $run_id}]->(b {run_id: $run_id}) "
            "RETURN r.id AS id, a.id AS source_id, b.id AS target_id, "
            "       type(r) AS edge_type, r.properties AS properties"
        )
        edge_rows = store.query(edge_q, params={"run_id": run_id})
        edge_records = getattr(edge_rows, "records", edge_rows) or []

        edges: list[Any] = []
        for r in edge_records:
            get = r.get if isinstance(r, dict) else (lambda k, _r=r: getattr(_r, k, None))
            raw_props = get("properties")
            if isinstance(raw_props, str):
                try:
                    import json as _json
                    raw_props = _json.loads(raw_props)
                except Exception:
                    raw_props = {}
            properties = raw_props if isinstance(raw_props, dict) else {}
            edges.append(
                type(
                    "_ScopedEdge",
                    (),
                    {
                        "id": get("id") or "",
                        "source_id": get("source_id"),
                        "target_id": get("target_id"),
                        "edge_type": get("edge_type") or "RELATED_TO",
                        "properties": properties,
                    },
                )()
            )

        logger.info(
            "scoped_store_materialized",
            run_id=run_id,
            nodes=len(nodes),
            edges=len(edges),
        )
        return nodes, edges

    def _convert_store_to_rdf(
        self, store: GraphStore, run_id: str | None = None,
    ) -> rdflib.Graph:
        """Convert graph store to RDF format for SHACL validation.

        Supports Neo4j, RDF, and in-memory graph stores. Creates RDF triples
        from KG nodes and edges, mapping them to ontology concepts.

        Args:
            store: GraphStore to convert (Neo4j, RDF, or in-memory)
            run_id: Optional experiment run id. When set and the store supports
                Cypher querying, conversion is restricted to nodes/edges with a
                matching top-level ``run_id`` property.

        Returns:
            RDFLib graph with RDF representation

        Raises:
            ValueError: If store conversion fails
        """
        graph = rdflib.Graph()
        ns = rdflib.Namespace(self.ontology_uri)

        try:
            logger.debug(
                "converting_store_to_rdf",
                store_type=type(store).__name__,
                run_id=run_id,
            )

            # Resolve nodes/edges with optional run_id scoping. We try a
            # Cypher-scoped path first (Neo4j); on any failure we fall back
            # to the unscoped store iterators so non-Neo4j stores still work.
            nodes: list[Any] = []
            edges: list[Any] = []
            scoped = False
            if run_id and hasattr(store, "query"):
                try:
                    nodes, edges = self._scoped_nodes_edges(store, run_id)
                    scoped = True
                except Exception as exc:
                    logger.warning(
                        "run_scoped_conversion_failed_falling_back",
                        run_id=run_id,
                        error=str(exc),
                    )
            if not scoped:
                # Get all nodes from store (materialize iterator so we can log counts)
                nodes = list(store.get_all_nodes())
            for node in nodes:
                # Create RDF URI for node
                node_uri = self._make_uri(node.node_type, node.id)

                # Add node type triple
                node_type_uri = self._make_uri(node.node_type)
                graph.add((node_uri, rdflib.RDF.type, node_type_uri))

                # Add node properties
                if node.label:
                    graph.add(
                        (
                            node_uri,
                            rdflib.RDFS.label,
                            rdflib.Literal(node.label),
                        )
                    )

                # Add custom properties
                for key, value in node.properties.items():
                    if value is not None:
                        prop_uri = self._make_uri(key)
                        literal_value = rdflib.Literal(value)
                        graph.add((node_uri, prop_uri, literal_value))

            # Get all edges from store (materialize iterator) unless we already
            # collected scoped edges above.
            if not scoped:
                edges = list(store.get_all_edges())
            for edge in edges:
                # Determine source/target node types: prefer explicit attrs on Edge,
                # otherwise look up nodes from the store (Neo4jGraphStore yields
                # edges without node-type attrs).
                src_type = getattr(edge, "source_node_type", None)
                tgt_type = getattr(edge, "target_node_type", None)

                if not src_type:
                    try:
                        src_node = store.get_node(getattr(edge, "source_id"))
                        src_type = getattr(src_node, "node_type", "Thing") if src_node else "Thing"
                    except Exception:
                        src_type = "Thing"

                if not tgt_type:
                    try:
                        tgt_node = store.get_node(getattr(edge, "target_id"))
                        tgt_type = getattr(tgt_node, "node_type", "Thing") if tgt_node else "Thing"
                    except Exception:
                        tgt_type = "Thing"

                source_uri = self._make_uri(src_type, edge.source_id)
                target_uri = self._make_uri(tgt_type, edge.target_id)
                predicate_uri = self._make_uri(edge.edge_type)

                # Add edge triple
                graph.add((source_uri, predicate_uri, target_uri))

                # Add edge properties
                for key, value in edge.properties.items():
                    if value is not None:
                        prop_uri = self._make_uri(f"{edge.edge_type}_{key}")
                        graph.add((source_uri, prop_uri, rdflib.Literal(value)))

            logger.info(
                "store_converted_to_rdf",
                nodes=len(nodes),
                edges=len(edges),
                triples=len(graph),
            )

        except AttributeError as e:
            logger.error("store_attribute_error", error=str(e), store_type=type(store).__name__)
            raise ValueError(f"Unsupported store type: {type(store).__name__}") from e
        except Exception as e:
            logger.error("store_conversion_failed", error=str(e))
            raise ValueError(f"Failed to convert store to RDF: {str(e)}") from e

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
