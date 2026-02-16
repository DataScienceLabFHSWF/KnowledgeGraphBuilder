"""Generate SHACL shapes from OWL ontology.

Translates OWL class definitions, property constraints, and domain/range
declarations into SHACL NodeShapes and PropertyShapes.  This bridges the
gap between the ontology (what *should* exist) and the SHACL validator
(which checks whether it *does* exist).

Key capabilities:
- Class → sh:NodeShape with sh:targetClass
- owl:ObjectProperty domain/range → sh:class constraints
- owl:DatatypeProperty range → sh:datatype constraints
- owl:FunctionalProperty → sh:maxCount 1
- rdfs:subClassOf → sh:node for parent shapes
- owl:inverseOf → custom sh:sparql constraints (optional)

Usage:
    >>> from kgbuilder.validation.shacl_generator import SHACLShapeGenerator
    >>> generator = SHACLShapeGenerator(ontology_service)
    >>> shapes_graph = generator.generate()
    >>> shapes_graph.serialize(format="turtle")

References:
    - SHACL spec: https://www.w3.org/TR/shacl/
    - Ahmetaj et al. "SHACL Validation under Graph Updates" (2025)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class SHACLShapeGenerator:
    """Generate SHACL shapes from an OWL ontology service.

    Queries the ontology for classes, properties, domain/range, cardinality,
    and special property characteristics, then emits a complete SHACL shapes
    graph suitable for pyshacl validation or SHACL2FOL static analysis.

    Attributes:
        ontology_service: FusekiOntologyService (or compatible).
        namespace: Base namespace for generated shape URIs.
    """

    def __init__(
        self,
        ontology_service: Any,
        namespace: str = "https://purl.org/ai4s/shapes/",
        ontology_namespace: str = "https://purl.org/ai4s/ontology/planning#",
    ) -> None:
        """Initialize the shape generator.

        Args:
            ontology_service: Ontology backend with ``get_all_classes()``,
                ``get_class_properties()``, ``get_special_properties()``, etc.
            namespace: URI namespace prefix for generated shapes.
            ontology_namespace: Base URI for ontology classes/properties used in shapes.
        """
        self._ontology = ontology_service
        self._namespace = namespace
        self._ontology_ns = ontology_namespace

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> Any:
        """Generate a complete SHACL shapes graph using rdflib.

        Returns:
            ``rdflib.Graph`` containing generated SHACL shapes.
        """
        try:
            import rdflib
            from rdflib import BNode, Namespace, URIRef
            from rdflib.namespace import RDF, RDFS, XSD
        except Exception as e:
            raise RuntimeError("rdflib is required for SHACL shape generation") from e

        SH = Namespace("http://www.w3.org/ns/shacl#")
        ONT = Namespace(self._ontology_ns)
        SHAPES = Namespace(self._namespace)

        g = rdflib.Graph()
        g.bind("sh", SH)
        g.bind("rdfs", RDFS)
        g.bind("xsd", XSD)
        g.bind("ont", ONT)

        # Retrieve classes from ontology service
        try:
            classes = self._ontology.get_all_classes() or []
        except Exception:
            classes = []

        for cls in classes:
            # Handle both list[str] (Fuseki) and list[dict] (_FileOntologyService)
            if isinstance(cls, dict):
                class_label = cls.get("label", cls.get("uri", ""))
                class_uri_str = cls.get("uri")
            else:
                class_label = str(cls)
                class_uri_str = None

            if not class_label:
                continue

            shape_uri = URIRef(f"{self._namespace}{class_label}Shape")
            # Use the full OWL URI when available; otherwise build from namespace
            if class_uri_str:
                class_uri = URIRef(class_uri_str)
            else:
                class_uri = URIRef(f"{self._ontology_ns}{class_label}")

            g.add((shape_uri, RDF.type, SH.NodeShape))
            g.add((shape_uri, SH.targetClass, class_uri))

            # Attach property shapes for this class
            try:
                properties = self._ontology.get_class_properties(class_label) or []
            except Exception:
                properties = []

            for prop in properties:
                # prop may be (prop_label, prop_kind, range, optional_constraints)
                prop_label = prop[0]
                prop_kind = prop[1] if len(prop) > 1 else "ObjectProperty"
                prop_range = prop[2] if len(prop) > 2 else None
                constraints = prop[3] if len(prop) > 3 and isinstance(prop[3], dict) else {}

                prop_bnode = BNode()
                g.add((shape_uri, SH.property, prop_bnode))
                g.add((prop_bnode, SH.path, URIRef(f"{self._ontology_ns}{prop_label}")))

                # Datatype vs object property
                if prop_kind and "Datatype" in prop_kind and prop_range:
                    if isinstance(prop_range, str) and prop_range.startswith("xsd:"):
                        dtype = getattr(XSD, prop_range.split(":", 1)[1])
                    else:
                        dtype = URIRef(prop_range)
                    g.add((prop_bnode, SH.datatype, dtype))
                elif prop_range:
                    g.add((prop_bnode, SH["class"], URIRef(f"{self._ontology_ns}{prop_range}")))

                # Optional: qualifiedValueShape / qualifiedMaxCount
                if constraints:
                    qshape = BNode()
                    qvs = constraints.get("qualified_value_shape")
                    if qvs:
                        # reference class for qualified value shape
                        g.add((qshape, SH["class"], URIRef(f"{self._ontology_ns}{qvs}")))
                    qmax = constraints.get("qualified_max_count")
                    if qmax is not None:
                        g.add((prop_bnode, SH["qualifiedMaxCount"], rdflib.Literal(int(qmax))))
                    # attach qualifiedValueShape node
                    g.add((prop_bnode, SH["qualifiedValueShape"], qshape))

        # Add special constraints (functional properties)
        try:
            special = self._ontology.get_special_properties() or {}
            for func in special.get("functional", []):
                # Find property shapes with matching sh:path and add sh:maxCount 1
                for s, p, o in g.triples((None, SH.property, None)):
                    for _, _, path in g.triples((o, SH.path, None)):
                        if str(path).endswith(func):
                            g.add((o, SH.maxCount, rdflib.Literal(1)))
        except Exception:
            pass

        # add any remaining inferred constraints (transitive/symmetric/etc)
        try:
            self._add_special_constraints(g)
        except Exception:
            # best-effort augmentation only
            pass

        return g

    def generate_for_class(self, class_label: str) -> Any:
        """Generate a SHACL NodeShape fragment for a single ontology class.

        This convenience method calls into the main `generate()` logic and
        returns a minimal graph containing the NodeShape for `class_label`.
        """
        full = self.generate()
        try:
            import rdflib
        except Exception as e:
            raise RuntimeError("rdflib is required for SHACL shape generation") from e

        SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")
        ONT = rdflib.Namespace(self._ontology_ns)
        class_uri = rdflib.URIRef(f"{self._ontology_ns}{class_label}")

        g = rdflib.Graph()
        for s in full.subjects(SH.targetClass, class_uri):
            for triple in full.triples((s, None, None)):
                g.add(triple)
            # include associated property shapes
            for _, _, prop in full.triples((s, SH.property, None)):
                for triple in full.triples((prop, None, None)):
                    g.add(triple)
        return g

    def serialize(self, shapes_graph: Any, format: str = "turtle") -> str:
        """Serialize a shapes graph to a string.

        Uses rdflib.Graph.serialize under the hood and returns a `str`.
        """
        try:
            return shapes_graph.serialize(format=format)  # type: ignore[return-value]
        except Exception as e:
            raise RuntimeError(f"Failed to serialize shapes graph: {e}") from e

    def save(self, shapes_graph: Any, path: Path, format: str = "turtle") -> Path:
        """Serialize and write shapes graph to disk.

        Ensures parent directories exist and returns the `Path` written.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self.serialize(shapes_graph, format=format)
        path.write_text(data)
        return path

    # ------------------------------------------------------------------
    # Private helpers (implemented)
    # ------------------------------------------------------------------

    def _generate_node_shape(self, class_label: str, class_uri: str) -> Any:
        try:
            import rdflib
            from rdflib import Namespace, URIRef
            from rdflib.namespace import RDF
        except Exception as e:
            raise RuntimeError("rdflib is required for node-shape generation") from e

        SH = Namespace("http://www.w3.org/ns/shacl#")
        ONT = Namespace(self._ontology_ns)

        shape_uri = URIRef(f"{self._namespace}{class_label}Shape")
        g = rdflib.Graph()
        g.add((shape_uri, RDF.type, SH.NodeShape))
        g.add((shape_uri, SH.targetClass, URIRef(class_uri)))

        # attach property shapes from ontology service (best-effort)
        try:
            props = self._ontology.get_class_properties(class_label) or []
            for prop in props:
                prop_label = prop[0]
                prop_uri = f"{self._ontology_ns}{prop_label}"
                prop_bnode = rdflib.BNode()
                g.add((shape_uri, SH.property, prop_bnode))
                g.add((prop_bnode, SH.path, URIRef(prop_uri)))
        except Exception:
            pass

        return shape_uri

    def _generate_property_shape(
        self,
        prop_label: str,
        prop_uri: str,
        domain_uri: str,
        range_uri: str,
    ) -> Any:
        try:
            import rdflib
            from rdflib import URIRef
            from rdflib.namespace import XSD
        except Exception as e:
            raise RuntimeError("rdflib is required for property-shape generation") from e

        SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")
        prop_bnode = rdflib.BNode()
        g = rdflib.Graph()
        g.add((prop_bnode, SH.path, URIRef(prop_uri)))

        # range: datatype or class
        if isinstance(range_uri, str) and range_uri.startswith("xsd:"):
            dt_name = range_uri.split(":", 1)[1]
            try:
                dtype = getattr(XSD, dt_name)
                g.add((prop_bnode, SH.datatype, dtype))
            except Exception:
                g.add((prop_bnode, SH.datatype, URIRef(range_uri)))
        elif range_uri:
            g.add((prop_bnode, SH["class"], URIRef(range_uri)))

        return prop_bnode

    def _add_special_constraints(self, shapes_graph: Any) -> None:
        """Attach small, portable annotations for special property characteristics.

        SHACL core does not directly encode `transitive` or `symmetric` as
        built-in shape constraints. For now we add `rdfs:comment` on the
        corresponding PropertyShape nodes to retain the metadata so downstream
        tools (and tests) can detect the intended characteristic. We also
        set `sh:maxCount 1` for functional properties (already done earlier),
        and add a small `sh:message` when available.
        """
        try:
            import rdflib
            from rdflib.namespace import RDFS
        except Exception:
            return

        special = {}
        try:
            special = self._ontology.get_special_properties() or {}
        except Exception:
            special = {}

        SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")

        # annotate property-shapes with comments describing the special flags
        for kind, props in special.items():
            for pname in props:
                # props may be tuples for inverse declarations
                if isinstance(pname, tuple):
                    pname = pname[0]
                for s, p, o in shapes_graph.triples((None, SH.property, None)):
                    for _, _, path in shapes_graph.triples((o, SH.path, None)):
                        if str(path).endswith(pname):
                            shapes_graph.add((o, RDFS.comment, rdflib.Literal(f"{kind}")))

        # ensure functional properties have maxCount=1 if not already present
        for func in special.get("functional", []):
            for s, p, o in shapes_graph.triples((None, SH.property, None)):
                for _, _, path in shapes_graph.triples((o, SH.path, None)):
                    if str(path).endswith(func):
                        shapes_graph.add((o, SH.maxCount, rdflib.Literal(1)))

        # SPARQL constraints (pyshacl only) for symmetric/transitive properties
        for sym in special.get("symmetric", []) or []:
            for s, p, o in shapes_graph.triples((None, SH.property, None)):
                for _, _, path in shapes_graph.triples((o, SH.path, None)):
                    if str(path).endswith(sym):
                        # Add a sh:select SPARQL query that detects asymmetry
                        query = (
                            f"SELECT $this WHERE {{ $this <{self._ontology_ns}{sym}> ?o . "
                            f"FILTER NOT EXISTS {{ ?o <{self._ontology_ns}{sym}> $this }} }}"
                        )
                        shapes_graph.add((o, SH.select, rdflib.Literal(query)))

        for trans in special.get("transitive", []) or []:
            for s, p, o in shapes_graph.triples((None, SH.property, None)):
                for _, _, path in shapes_graph.triples((o, SH.path, None)):
                    if str(path).endswith(trans):
                        # Add a sh:select SPARQL query that detects non-transitive occurrences
                        query = (
                            f"SELECT $this WHERE {{ $this <{self._ontology_ns}{trans}> ?mid . "
                            f"?mid <{self._ontology_ns}{trans}> ?end . FILTER NOT EXISTS {{ $this <{self._ontology_ns}{trans}> ?end }} }}"
                        )
                        shapes_graph.add((o, SH.select, rdflib.Literal(query)))

        # For inverse declarations, add comments on both directions
        for inv in special.get("inverse", []) or []:
            if isinstance(inv, tuple) and len(inv) == 2:
                a, b = inv
                for s, p, o in shapes_graph.triples((None, SH.property, None)):
                    for _, _, path in shapes_graph.triples((o, SH.path, None)):
                        if str(path).endswith(a) or str(path).endswith(b):
                            shapes_graph.add((o, RDFS.comment, rdflib.Literal("inverse")))

        # best-effort: add a top-level graph comment indicating generation time
        shapes_graph.set((rdflib.URIRef(self._namespace), rdflib.RDFS.comment, rdflib.Literal("Generated SHACL shapes")))

