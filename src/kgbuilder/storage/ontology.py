"""Ontology service implementations for querying RDF stores.

Provides concrete implementations of OntologyService protocol for different
RDF backends (Fuseki, etc.). Implementations query actual ontology data
to guide KG construction and question generation.
"""

from __future__ import annotations

from typing import Any

import structlog

from kgbuilder.storage.rdf import FusekiStore

logger = structlog.get_logger(__name__)


class FusekiOntologyService:
    """Real ontology service querying Apache Fuseki RDF store.
    
    Implements the OntologyService protocol by executing SPARQL queries
    against a live Fuseki endpoint. Returns actual ontology data for
    driving KG construction.
    
    This is the canonical implementation for ontology queries. It should be
    used instead of mock services to ensure pipelines use real ontology data.
    """

    def __init__(self, fuseki_url: str, dataset_name: str):
        """Initialize with Fuseki connection.
        
        Args:
            fuseki_url: Base Fuseki URL (e.g., http://localhost:3030)
            dataset_name: Dataset/graph name (e.g., kgbuilder)
        """
        self.store = FusekiStore(url=fuseki_url, dataset_name=dataset_name)
        self._classes_cache = None
        logger.info(
            "fuseki_ontology_initialized",
            url=fuseki_url,
            dataset=dataset_name
        )

    def get_all_classes(self) -> list[str]:
        """Get all classes from Fuseki ontology.
        
        Executes SPARQL query for owl:Class instances and returns class labels/names
        that can be used as dict keys and identifiers.
        
        Returns:
            List of class labels (strings) from the ontology
            
        Raises:
            RuntimeError: If SPARQL query fails
        """
        if self._classes_cache is not None:
            return self._classes_cache

        try:
            # SPARQL query for all OWL classes
            sparql = """
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT DISTINCT ?class ?label ?comment
            WHERE {
                ?class a owl:Class .
                OPTIONAL { ?class rdfs:label ?label . }
                OPTIONAL { ?class rdfs:comment ?comment . }
            }
            ORDER BY ?class
            LIMIT 100
            """

            result = self.store.query_sparql(sparql)
            classes = []

            for binding in result.get("results", {}).get("bindings", []):
                class_uri = binding.get("class", {}).get("value", "")
                label = binding.get("label", {}).get("value")

                if class_uri:
                    # Use label if available, otherwise extract from URI
                    if not label:
                        label = class_uri.split("#")[-1].split("/")[-1]
                    
                    classes.append(label)

            self._classes_cache = classes
            logger.info("ontology_classes_loaded", count=len(classes))
            return classes

        except Exception as e:
            logger.error("ontology_load_failed")
            raise RuntimeError(f"Failed to load ontology from Fuseki: {e}") from e

    def get_class_properties(self, class_label: str) -> list[tuple[str, str, str]]:
        """Get data properties (attributes) for a specific class.
        
        Extracts owl:DatatypeProperty instances where this class is the domain.
        Returns list of (property_name, property_type, property_description) tuples.
        
        Args:
            class_label: Class label/name to query
            
        Returns:
            List of (property_name, property_type_string, description) tuples
        """
        try:
            sparql = f"""
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
            SELECT DISTINCT ?propLabel ?range ?comment
            WHERE {{
                ?class a owl:Class ;
                       rdfs:label ?classLabel .
                ?prop a owl:DatatypeProperty ;
                       rdfs:domain ?class ;
                       rdfs:label ?propLabel .
                OPTIONAL {{ ?prop rdfs:range ?range . }}
                OPTIONAL {{ ?prop rdfs:comment ?comment . }}
                FILTER(REGEX(STR(?classLabel), "{class_label}", "i"))
            }}
            ORDER BY ?propLabel
            """
            
            result = self.store.query_sparql(sparql)
            properties = []
            
            for binding in result.get("results", {}).get("bindings", []):
                prop_label = binding.get("propLabel", {}).get("value", "")
                range_uri = binding.get("range", {}).get("value", "xsd:string")
                comment = binding.get("comment", {}).get("value", "")
                
                # Map XSD types to simple strings
                type_map = {
                    "xsd:string": "string",
                    "xsd:date": "date",
                    "xsd:dateTime": "datetime",
                    "xsd:float": "float",
                    "xsd:double": "float",
                    "xsd:integer": "integer",
                    "xsd:boolean": "boolean",
                }
                data_type = type_map.get(range_uri, "string")
                
                if prop_label:
                    properties.append((prop_label, data_type, comment))
            
            logger.info("class_properties_loaded", class_label=class_label, count=len(properties))
            return properties
            
        except Exception as e:
            logger.warning("class_properties_load_failed", class_label=class_label, error=str(e))
            return []

    def get_class_relations(self, class_uri: str) -> list[str]:
        """Get relations/properties for a specific class.
        
        Executes SPARQL query for ObjectProperty instances that have domain
        or range matching the given class.
        
        Args:
            class_uri: Full URI of the class to query
            
        Returns:
            List of relation/property names
            
        Raises:
            RuntimeError: If SPARQL query fails
        """
        try:
            sparql = f"""
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT DISTINCT ?prop ?label
            WHERE {{
                ?prop a owl:ObjectProperty .
                OPTIONAL {{ ?prop rdfs:label ?label . }}
                {{
                    ?prop rdfs:domain <{class_uri}> .
                }} UNION {{
                    ?prop rdfs:range <{class_uri}> .
                }}
            }}
            LIMIT 100
            """

            result = self.store.query_sparql(sparql)
            relations = []

            for binding in result.get("results", {}).get("bindings", []):
                prop_uri = binding.get("prop", {}).get("value", "")
                if prop_uri:
                    label = binding.get("label", {}).get("value")
                    if not label:
                        label = prop_uri.split("#")[-1].split("/")[-1]
                    relations.append(label)

            logger.info(
                "class_relations_loaded",
                class_uri=class_uri,
                count=len(relations)
            )
            return relations

        except Exception as e:
            logger.warning("relations_load_failed", class_uri=class_uri, error=str(e))
            raise RuntimeError(f"Failed to load relations for {class_uri}: {e}") from e

    def get_class_hierarchy(self, class_name: str) -> dict[str, Any]:
        """Get hierarchy information for a class.
        
        Args:
            class_name: Class name or URI
            
        Returns:
            Dict with 'parents', 'children', 'depth'
        """
        # TODO: Implement full hierarchy traversal
        return {"parents": [], "children": [], "depth": 0}
