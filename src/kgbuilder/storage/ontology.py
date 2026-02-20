"""Ontology service implementations for querying RDF stores.

Provides concrete implementations of OntologyService protocol for different
RDF backends (Fuseki, etc.). Implementations query actual ontology data
to guide KG construction and question generation.
"""

from __future__ import annotations

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

    def __init__(self, fuseki_url: str, dataset_name: str, username: str | None = None, password: str | None = None):
        """Initialize with Fuseki connection.
        
        Args:
            fuseki_url: Base Fuseki URL (e.g., http://localhost:3030)
            dataset_name: Dataset/graph name (e.g., kgbuilder)
            username: Optional username for HTTP Basic Auth
            password: Optional password for HTTP Basic Auth
        """
        self.store = FusekiStore(
            url=fuseki_url,
            dataset_name=dataset_name,
            username=username,
            password=password
        )
        self._classes_cache = None
        logger.info(
            "fuseki_ontology_initialized",
            url=fuseki_url,
            dataset=dataset_name,
            authenticated=bool(username)
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
            # More robust SPARQL:
            # 1. Matches class by label OR by URI local name
            # 2. Makes property label optional (fallbacks to URI fragment in python code)
            sparql = f"""
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
            SELECT DISTINCT ?prop ?propLabel ?range ?comment
            WHERE {{
                ?class a owl:Class .
                OPTIONAL {{ ?class rdfs:label ?classLabel . }}
                
                ?prop a owl:DatatypeProperty ;
                       rdfs:domain ?class .
                
                OPTIONAL {{ ?prop rdfs:label ?propLabel . }}
                OPTIONAL {{ ?prop rdfs:range ?range . }}
                OPTIONAL {{ ?prop rdfs:comment ?comment . }}
                
                FILTER(
                    (BOUND(?classLabel) && REGEX(STR(?classLabel), "{class_label}", "i")) ||
                    REGEX(STR(?class), "{class_label}$", "i") ||
                    REGEX(STR(?class), "#{class_label}$", "i")
                )
            }}
            ORDER BY ?propLabel
            """

            result = self.store.query_sparql(sparql)
            properties = []

            for binding in result.get("results", {}).get("bindings", []):
                prop_uri = binding.get("prop", {}).get("value", "")
                prop_label = binding.get("propLabel", {}).get("value")

                # Fallback for property label
                if not prop_label and prop_uri:
                    prop_label = prop_uri.split("#")[-1].split("/")[-1]

                if not prop_label:
                    continue

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
                    "http://www.w3.org/2001/XMLSchema#string": "string",
                    "http://www.w3.org/2001/XMLSchema#integer": "integer",
                    "http://www.w3.org/2001/XMLSchema#float": "float",
                    "http://www.w3.org/2001/XMLSchema#boolean": "boolean",
                    "http://www.w3.org/2001/XMLSchema#nonNegativeInteger": "integer",
                }
                data_type = type_map.get(range_uri, "string")

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

    def get_all_relations(self) -> list[str]:
        """Get all ObjectProperties defined in the ontology.
        
        Returns:
            List of relation labels/names
        """
        try:
            sparql = """
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT DISTINCT ?prop ?label
            WHERE {
                ?prop a owl:ObjectProperty .
                OPTIONAL { ?prop rdfs:label ?label . }
            }
            LIMIT 200
            """
            result = self.store.query_sparql(sparql)
            relations = []
            for binding in result.get("results", {}).get("bindings", []):
                prop_uri = binding.get("prop", {}).get("value", "")
                label = binding.get("label", {}).get("value")
                if not label and prop_uri:
                    label = prop_uri.split("#")[-1].split("/")[-1]
                if label:
                    relations.append(label)
            return relations
        except Exception as e:
            logger.warning("all_relations_load_failed", error=str(e))
            return []

    def get_class_hierarchy(self, class_name: str | None = None) -> list[tuple[str, str]] | dict[str, any]:
        """Get class hierarchy information.

        Two behaviours are supported:
        - No argument: return list of (child_label, parent_label) tuples for the
          entire ontology (backwards-compatible behaviour).
        - `class_name` provided: return a dict with 'parents', 'children' and
          'depth' for the requested class (used by question generation).

        Args:
            class_name: Optional class label to query for (case-insensitive).

        Returns:
            If `class_name` is None: list[tuple[child, parent]]
            Otherwise: dict with keys: 'parents' (list[str]), 'children' (list[str]),
                       'depth' (int)
        """
        try:
            # Fetch full subclass graph once and reuse for both behaviours.
            sparql = """
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            SELECT DISTINCT ?child ?childLabel ?parent ?parentLabel
            WHERE {
                ?child rdfs:subClassOf ?parent .
                FILTER(isURI(?child) && isURI(?parent))
                OPTIONAL { ?child rdfs:label ?childLabel . }
                OPTIONAL { ?parent rdfs:label ?parentLabel . }
            }
            """
            res = self.store.query_sparql(sparql)
            hierarchy_pairs: list[tuple[str, str]] = []
            for binding in res.get("results", {}).get("bindings", []):
                child = (
                    binding.get("childLabel", {}).get("value")
                    or binding.get("child", {}).get("value").split("#")[-1]
                )
                parent = (
                    binding.get("parentLabel", {}).get("value")
                    or binding.get("parent", {}).get("value").split("#")[-1]
                )
                hierarchy_pairs.append((child, parent))

            # If no class requested, return full list (existing behaviour)
            if class_name is None:
                return hierarchy_pairs

            # Build quick lookup maps
            parents_map: dict[str, set[str]] = {}
            children_map: dict[str, set[str]] = {}
            nodes: set[str] = set()
            for child, parent in hierarchy_pairs:
                nodes.add(child)
                nodes.add(parent)
                parents_map.setdefault(child, set()).add(parent)
                children_map.setdefault(parent, set()).add(child)

            # Normalize requested class (try exact match first, then case-insensitive)
            target = None
            if class_name in nodes:
                target = class_name
            else:
                lowered = {n.lower(): n for n in nodes}
                target = lowered.get(class_name.lower())

            if not target:
                # Class not present in hierarchy — return empty info
                return {"parents": [], "children": [], "depth": 0}

            # Collect immediate parents and children
            parents = sorted(list(parents_map.get(target, [])))
            children = sorted(list(children_map.get(target, [])))

            # Compute depth (distance to root = number of ancestor hops)
            def _compute_depth(node: str, visited: set[str] | None = None) -> int:
                visited = visited or set()
                # If no parents -> root (depth 0)
                if not parents_map.get(node):
                    return 0
                max_depth = 0
                for p in parents_map.get(node, []):
                    if p in visited:
                        continue
                    visited.add(p)
                    d = 1 + _compute_depth(p, visited)
                    max_depth = max(max_depth, d)
                return max_depth

            depth = _compute_depth(target)

            return {"parents": parents, "children": children, "depth": depth}

        except Exception as e:
            logger.warning("hierarchy_load_failed", error=str(e))
            return [] if class_name is None else {"parents": [], "children": [], "depth": 0}

    def get_special_properties(self) -> dict[str, list[str]]:
        """Get properties with special OWL characteristics.
        
        Returns:
            Dict mapping characteristic (transitive, symmetric, inverse) to property lists
        """
        try:
            characteristics = {
                "transitive": "owl:TransitiveProperty",
                "symmetric": "owl:SymmetricProperty",
                "functional": "owl:FunctionalProperty",
            }

            results = {}
            for key, owl_type in characteristics.items():
                sparql = f"""
                PREFIX owl: <http://www.w3.org/2002/07/owl#>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                SELECT DISTINCT ?prop ?label
                WHERE {{
                    ?prop a {owl_type} .
                    OPTIONAL {{ ?prop rdfs:label ?label . }}
                }}
                """
                res = self.store.query_sparql(sparql)
                props = []
                for binding in res.get("results", {}).get("bindings", []):
                    # Prefer label, fallback to URI fragment
                    label = binding.get("label", {}).get("value")
                    if not label:
                        uri = binding.get("prop", {}).get("value", "")
                        label = uri.split("#")[-1].split("/")[-1]
                    if label:
                        props.append(label)
                results[key] = props

            # Inverse properties are different
            sparql = """
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT DISTINCT ?p1 ?p1Label ?p2 ?p2Label
            WHERE {
                ?p1 owl:inverseOf ?p2 .
                OPTIONAL { ?p1 rdfs:label ?p1Label . }
                OPTIONAL { ?p2 rdfs:label ?p2Label . }
            }
            """
            res = self.store.query_sparql(sparql)
            inverses = []
            for b in res.get("results", {}).get("bindings", []):
                l1 = b.get("p1Label", {}).get("value") or b.get("p1", {}).get("value").split("#")[-1]
                l2 = b.get("p2Label", {}).get("value") or b.get("p2", {}).get("value").split("#")[-1]
                inverses.append((l1, l2))
            results["inverse"] = inverses

            return results
        except Exception as e:
            logger.warning("special_properties_load_failed", error=str(e))
            return {"transitive": [], "symmetric": [], "functional": [], "inverse": []}
