"""Knowledge Graph Export - export KG to various formats.

This module provides export functionality for knowledge graphs.
Supported formats:
- JSON: Simple JSON representation
- JSON-LD: Linked Data JSON with context
- RDF/Turtle: Semantic web format
- Cypher: Neo4j import statements
- GraphML: XML graph format for visualization tools

Usage:
    from kgbuilder.storage.export import KGExporter
    from kgbuilder.storage.protocol import InMemoryGraphStore
    
    # Build graph
    store = InMemoryGraphStore()
    # ... add nodes and edges ...
    
    # Export to various formats
    exporter = KGExporter(store)
    
    json_ld = exporter.to_jsonld()
    turtle = exporter.to_turtle()
    cypher = exporter.to_cypher()
    graphml = exporter.to_graphml()

File Export:
    exporter.export_to_file("output/kg.jsonld", format="jsonld")
    exporter.export_to_file("output/kg.ttl", format="turtle")
    exporter.export_to_file("output/kg.cypher", format="cypher")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator
import json
import xml.etree.ElementTree as ET

import structlog

from kgbuilder.storage.protocol import GraphStore, Node, Edge

logger = structlog.get_logger(__name__)


# =============================================================================
# EXPORT CONFIG
# =============================================================================


@dataclass
class ExportConfig:
    """Configuration for KG export.
    
    Attributes:
        base_uri: Base URI for RDF/JSON-LD exports
        include_metadata: Include node/edge metadata in export
        include_provenance: Include provenance information
        pretty_print: Format output for readability
        max_evidence_samples: Max evidence text samples to include
    """
    
    base_uri: str = "http://kgbuilder.io/kg/"
    ontology_uri: str = "http://kgbuilder.io/ontology#"
    include_metadata: bool = True
    include_provenance: bool = True
    pretty_print: bool = True
    max_evidence_samples: int = 3


# =============================================================================
# KG EXPORTER
# =============================================================================


class KGExporter:
    """Export knowledge graph to multiple formats.
    
    This class provides export functionality for any GraphStore.
    It can export to JSON-LD, RDF/Turtle, Cypher, and GraphML formats.
    
    Example:
        >>> store = InMemoryGraphStore()
        >>> # ... populate store ...
        >>> exporter = KGExporter(store)
        >>> exporter.export_to_file("kg.jsonld", format="jsonld")
        >>> exporter.export_to_file("kg.ttl", format="turtle")
    """
    
    def __init__(
        self,
        graph_store: GraphStore,
        config: ExportConfig | None = None,
    ) -> None:
        """Initialize exporter with a graph store.
        
        Args:
            graph_store: The GraphStore to export from
            config: Export configuration options
        """
        self._store = graph_store
        self._config = config or ExportConfig()
        logger.info("kg_exporter_initialized", store_type=type(graph_store).__name__)
    
    # -------------------------------------------------------------------------
    # Main Export Methods
    # -------------------------------------------------------------------------
    
    def export_to_file(
        self,
        filepath: str | Path,
        format: str = "json",
    ) -> None:
        """Export graph to a file in the specified format.
        
        Args:
            filepath: Output file path
            format: Export format ("json", "jsonld", "turtle", "cypher", "graphml")
            
        Raises:
            ValueError: If format is not supported
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        format_lower = format.lower()
        
        if format_lower == "json":
            content = self.to_json()
        elif format_lower == "jsonld":
            content = self.to_jsonld()
        elif format_lower in ("turtle", "ttl", "rdf"):
            content = self.to_turtle()
        elif format_lower == "cypher":
            content = self.to_cypher()
        elif format_lower == "graphml":
            content = self.to_graphml()
        else:
            raise ValueError(f"Unsupported format: {format}. Use json, jsonld, turtle, cypher, or graphml")
        
        filepath.write_text(content)
        logger.info("kg_exported", filepath=str(filepath), format=format)
    
    # -------------------------------------------------------------------------
    # JSON Export
    # -------------------------------------------------------------------------
    
    def to_json(self) -> str:
        """Export to simple JSON format.
        
        Returns:
            JSON string with nodes and edges arrays
        """
        data = {
            "metadata": {
                "exported_at": datetime.utcnow().isoformat(),
                "format": "kgbuilder-json",
                "version": "1.0",
            },
            "statistics": self._store.get_statistics().__dict__,
            "nodes": [self._node_to_dict(n) for n in self._store.get_all_nodes()],
            "edges": [self._edge_to_dict(e) for e in self._store.get_all_edges()],
        }
        
        indent = 2 if self._config.pretty_print else None
        return json.dumps(data, indent=indent, default=str)
    
    # -------------------------------------------------------------------------
    # JSON-LD Export
    # -------------------------------------------------------------------------
    
    def to_jsonld(self) -> str:
        """Export to JSON-LD format for Linked Data applications.
        
        JSON-LD is JSON with semantic context that makes it compatible
        with RDF and Linked Data ecosystems.
        
        Returns:
            JSON-LD string with @context and @graph
        """
        context = {
            "@base": self._config.base_uri,
            "kg": self._config.ontology_uri,
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
            "xsd": "http://www.w3.org/2001/XMLSchema#",
            "label": "rdfs:label",
            "type": "@type",
            "confidence": {
                "@id": "kg:confidence",
                "@type": "xsd:decimal"
            },
            "description": "kg:description",
            "evidence_count": "kg:evidenceCount",
        }
        
        graph = []
        
        # Add nodes
        for node in self._store.get_all_nodes():
            node_obj = {
                "@id": f"kg:{node.id}",
                "@type": f"kg:{node.node_type}",
                "label": node.label,
            }
            
            # Add properties
            if "confidence" in node.properties:
                node_obj["confidence"] = node.properties["confidence"]
            if "description" in node.properties:
                node_obj["description"] = node.properties["description"]
            if "evidence_count" in node.properties:
                node_obj["evidence_count"] = node.properties["evidence_count"]
            
            graph.append(node_obj)
        
        # Add edges as properties on source nodes
        # (JSON-LD represents edges as nested references)
        edges_by_source: dict[str, list[Edge]] = {}
        for edge in self._store.get_all_edges():
            if edge.source_id not in edges_by_source:
                edges_by_source[edge.source_id] = []
            edges_by_source[edge.source_id].append(edge)
        
        for node_obj in graph:
            node_id = node_obj["@id"].replace("kg:", "")
            if node_id in edges_by_source:
                for edge in edges_by_source[node_id]:
                    predicate = f"kg:{edge.edge_type}"
                    target_ref = {"@id": f"kg:{edge.target_id}"}
                    
                    if predicate in node_obj:
                        # Multiple values - make it an array
                        if not isinstance(node_obj[predicate], list):
                            node_obj[predicate] = [node_obj[predicate]]
                        node_obj[predicate].append(target_ref)
                    else:
                        node_obj[predicate] = target_ref
        
        data = {
            "@context": context,
            "@graph": graph,
        }
        
        indent = 2 if self._config.pretty_print else None
        return json.dumps(data, indent=indent, default=str)
    
    # -------------------------------------------------------------------------
    # RDF/Turtle Export
    # -------------------------------------------------------------------------
    
    def to_turtle(self) -> str:
        """Export to RDF/Turtle format for semantic web applications.
        
        Turtle is a compact, human-readable RDF syntax.
        
        Returns:
            Turtle format string
        """
        lines = [
            f"@prefix kg: <{self._config.ontology_uri}> .",
            f"@prefix : <{self._config.base_uri}> .",
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
            "",
            "# Knowledge Graph exported by KGBuilder",
            f"# Exported: {datetime.utcnow().isoformat()}",
            "",
        ]
        
        # Add nodes
        def _node_ref(nid: str) -> str:
            """Return a Turtle-safe reference for a node id.

            - If the node id is a safe local name, use `:localName`.
            - Otherwise return a full <…> URI using the export base URI + percent-encoded id.
            """
            import re
            from urllib.parse import quote

            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_\-]*", nid):
                return f":{nid}"
            return f"<{self._config.base_uri.rstrip('/')}/{quote(nid, safe='')}>"

        for node in self._store.get_all_nodes():
            node_uri = _node_ref(node.id)
            lines.append(f"# Node: {node.label}")
            lines.append(f"{node_uri} a kg:{self._sanitize_uri(node.node_type)} ;")
            lines.append(f'    rdfs:label "{self._escape_turtle(node.label)}" ;')
            
            if "confidence" in node.properties:
                lines.append(f'    kg:confidence "{node.properties["confidence"]}"^^xsd:decimal ;')
            
            if "description" in node.properties:
                desc = self._escape_turtle(str(node.properties["description"]))
                lines.append(f'    kg:description "{desc}" ;')
            
            if "evidence_count" in node.properties:
                lines.append(f'    kg:evidenceCount "{node.properties["evidence_count"]}"^^xsd:integer ;')
            
            # Remove trailing semicolon and add period
            lines[-1] = lines[-1].rstrip(" ;") + " ."
            lines.append("")
        
        # Add edges
        lines.append("# Relationships")
        for edge in self._store.get_all_edges():
            source_uri = _node_ref(edge.source_id)
            target_uri = _node_ref(edge.target_id)
            predicate = f"kg:{self._sanitize_uri(edge.edge_type)}"
            lines.append(f"{source_uri} {predicate} {target_uri} .")
        
        return "\n".join(lines)
    
    # -------------------------------------------------------------------------
    # Cypher Export (Neo4j)
    # -------------------------------------------------------------------------
    
    def to_cypher(self) -> str:
        """Export to Cypher statements for Neo4j import.
        
        Generates CREATE statements that can be run in Neo4j
        to recreate the graph.
        
        Returns:
            Cypher statements string
        """
        lines = [
            "// Knowledge Graph Cypher Export",
            f"// Generated: {datetime.utcnow().isoformat()}",
            "// Import with: cat kg.cypher | cypher-shell",
            "",
            "// Clear existing data (optional - uncomment if needed)",
            "// MATCH (n) DETACH DELETE n;",
            "",
            "// Create nodes",
        ]
        
        # Create nodes
        for node in self._store.get_all_nodes():
            label = self._sanitize_cypher_label(node.node_type)
            props = self._cypher_properties(node.properties)
            props["id"] = node.id
            props["label"] = node.label
            
            props_str = ", ".join(f"{k}: {self._cypher_value(v)}" for k, v in props.items())
            lines.append(f"CREATE (:{label} {{{props_str}}});")
        
        lines.append("")
        lines.append("// Create indexes for fast lookup")
        
        # Collect unique labels for indexing
        labels = set(self._sanitize_cypher_label(n.node_type) for n in self._store.get_all_nodes())
        for label in labels:
            lines.append(f"CREATE INDEX IF NOT EXISTS FOR (n:{label}) ON (n.id);")
        
        lines.append("")
        lines.append("// Create relationships")
        
        # Create relationships
        for edge in self._store.get_all_edges():
            rel_type = self._sanitize_cypher_label(edge.edge_type)
            props = self._cypher_properties(edge.properties)
            
            props_str = ""
            if props:
                props_str = " {" + ", ".join(f"{k}: {self._cypher_value(v)}" for k, v in props.items()) + "}"
            
            lines.append(
                f"MATCH (a {{id: '{edge.source_id}'}}), (b {{id: '{edge.target_id}'}}) "
                f"CREATE (a)-[:{rel_type}{props_str}]->(b);"
            )
        
        return "\n".join(lines)
    
    # -------------------------------------------------------------------------
    # GraphML Export
    # -------------------------------------------------------------------------
    
    def to_graphml(self) -> str:
        """Export to GraphML format for visualization tools.
        
        GraphML is an XML format supported by tools like Gephi, yEd,
        Cytoscape, and NetworkX.
        
        Returns:
            GraphML XML string
        """
        # Create root element with namespaces
        graphml = ET.Element("graphml")
        graphml.set("xmlns", "http://graphml.graphdrawing.org/xmlns")
        graphml.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        
        # Define keys for node/edge attributes
        keys = [
            ("label", "node", "string"),
            ("type", "node", "string"),
            ("confidence", "node", "double"),
            ("description", "node", "string"),
            ("edge_type", "edge", "string"),
            ("confidence", "edge", "double"),
        ]
        
        for key_id, for_type, type_name in keys:
            key_elem = ET.SubElement(graphml, "key")
            key_elem.set("id", key_id)
            key_elem.set("for", for_type)
            key_elem.set("attr.name", key_id)
            key_elem.set("attr.type", type_name)
        
        # Create graph element
        graph = ET.SubElement(graphml, "graph")
        graph.set("id", "G")
        graph.set("edgedefault", "directed")
        
        # Add nodes
        for node in self._store.get_all_nodes():
            node_elem = ET.SubElement(graph, "node")
            node_elem.set("id", node.id)
            
            # Add data elements
            self._add_graphml_data(node_elem, "label", node.label)
            self._add_graphml_data(node_elem, "type", node.node_type)
            if "confidence" in node.properties:
                self._add_graphml_data(node_elem, "confidence", str(node.properties["confidence"]))
            if "description" in node.properties:
                self._add_graphml_data(node_elem, "description", str(node.properties["description"])[:500])
        
        # Add edges
        for i, edge in enumerate(self._store.get_all_edges()):
            edge_elem = ET.SubElement(graph, "edge")
            edge_elem.set("id", edge.id or f"e{i}")
            edge_elem.set("source", edge.source_id)
            edge_elem.set("target", edge.target_id)
            
            self._add_graphml_data(edge_elem, "edge_type", edge.edge_type)
            if "confidence" in edge.properties:
                self._add_graphml_data(edge_elem, "confidence", str(edge.properties["confidence"]))
        
        # Convert to string with pretty printing
        if self._config.pretty_print:
            ET.indent(graphml, space="  ")
        
        return ET.tostring(graphml, encoding="unicode", xml_declaration=True)
    
    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------
    
    def _node_to_dict(self, node: Node) -> dict[str, Any]:
        """Convert node to dictionary."""
        return node.to_dict()
    
    def _edge_to_dict(self, edge: Edge) -> dict[str, Any]:
        """Convert edge to dictionary."""
        return edge.to_dict()
    
    def _sanitize_uri(self, s: str) -> str:
        """Sanitize string for use in URI local-name.

        Replace whitespace and common unsafe characters and percent-encode any
        remaining characters that are not alphanumeric or underscore so the
        resulting token is safe for use as `kg:LocalName` in Turtle.
        """
        import re
        from urllib.parse import quote

        if not s:
            return ""
        # Replace common separators with underscore
        s = s.replace(" ", "_").replace("-", "_").replace("/", "_")
        # If remaining string is a safe local name, return it; otherwise percent-encode
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", s):
            return s
        return quote(s, safe='')

    
    def _escape_turtle(self, s: str) -> str:
        """Escape string for Turtle format."""
        return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    
    def _sanitize_cypher_label(self, s: str) -> str:
        """Sanitize string for Cypher label."""
        # Remove spaces, replace hyphens, ensure starts with letter
        result = s.replace(" ", "_").replace("-", "_").replace("/", "_")
        if result[0].isdigit():
            result = "_" + result
        return result
    
    def _cypher_properties(self, props: dict[str, Any]) -> dict[str, Any]:
        """Filter and prepare properties for Cypher."""
        # Only include simple types
        return {
            k: v for k, v in props.items()
            if isinstance(v, (str, int, float, bool))
        }
    
    def _cypher_value(self, v: Any) -> str:
        """Convert value to Cypher literal."""
        if isinstance(v, str):
            return f"'{v.replace(chr(39), chr(39)+chr(39))}'"
        elif isinstance(v, bool):
            return "true" if v else "false"
        elif isinstance(v, (int, float)):
            return str(v)
        else:
            return f"'{str(v)}'"
    
    def _add_graphml_data(self, parent: ET.Element, key: str, value: str) -> None:
        """Add a data element to GraphML node/edge."""
        data = ET.SubElement(parent, "data")
        data.set("key", key)
        data.text = value


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def export_kg(
    graph_store: GraphStore,
    filepath: str | Path,
    format: str = "json",
    config: ExportConfig | None = None,
) -> None:
    """Convenience function to export a knowledge graph.
    
    Args:
        graph_store: The graph store to export
        filepath: Output file path
        format: Export format
        config: Optional export configuration
        
    Example:
        >>> export_kg(store, "output/kg.jsonld", format="jsonld")
    """
    exporter = KGExporter(graph_store, config)
    exporter.export_to_file(filepath, format)
