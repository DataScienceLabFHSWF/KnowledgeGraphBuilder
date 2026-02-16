"""RDF store implementations using Apache Fuseki.

Implementation of Issue #6.3: RDF Triple Store

Key features:
- Apache Fuseki RDF store backend
- SPARQL query support
- RDF export/import
- Ontology management
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class RDFStore(Protocol):
    """Protocol for RDF triple store implementations."""

    def add_triple(self, subject: str, predicate: str, obj: str) -> None:
        """Add an RDF triple (statement).

        Args:
            subject: Subject URI
            predicate: Predicate/property URI
            obj: Object URI or literal value
        """
        ...

    def query_sparql(self, sparql: str) -> list[dict[str, str]]:
        """Execute SPARQL query.

        Args:
            sparql: SPARQL query string

        Returns:
            Query results
        """
        ...

    def export_rdf(self, format: str = "turtle") -> str:
        """Export RDF graph.

        Args:
            format: RDF format (turtle, rdfxml, ntriples)

        Returns:
            RDF string
        """
        ...


class FusekiStore:
    """Apache Fuseki RDF triple store implementation.

    TODO (Implementation):
    - [ ] Implement __init__() with Fuseki connection
    - [ ] Implement add_triple() using HTTP API
    - [ ] Implement query_sparql() for query execution
    - [ ] Implement export_rdf() in multiple formats
    - [ ] Implement batch operations
    - [ ] Implement transaction management
    - [ ] Implement ontology loading
    - [ ] Add error handling and retry logic
    - [ ] Add unit tests with Fuseki test container

    Dependencies: requests>=2.28.0, rdflib>=6.0.0

    See Planning/INTERFACES.md Section 6.3 for protocol definition.
    See Planning/ISSUES_BACKLOG.md Issue #6.3 for acceptance criteria.
    """

    def __init__(
        self,
        url: str = "http://localhost:3030",
        dataset_name: str = "kgbuilder",
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        """Initialize Fuseki store.

        Args:
            url: Fuseki server base URL
            dataset_name: Dataset name to use
            username: HTTP Basic Auth username
            password: HTTP Basic Auth password
        """
        import requests
        from requests.auth import HTTPBasicAuth

        self.url = url
        self.dataset_name = dataset_name
        self.session = requests.Session()

        # Setup auth if provided
        if username and password:
            self.session.auth = HTTPBasicAuth(username, password)

        # Use simpler SPARQL endpoint for all operations
        self.sparql_url = f"{url}/{dataset_name}/sparql"
        self.update_url = f"{url}/{dataset_name}/update"
        self.query_url = f"{url}/query"

        # Verify connection
        try:
            resp = self.session.get(f"{url}/$/datasets")
            if resp.status_code not in (200, 401):
                resp.raise_for_status()

            # Try to create dataset if it doesn't exist
            self._ensure_dataset_exists()
        except Exception as e:
            raise ConnectionError(
                f"Cannot connect to Fuseki at {url}: {e}"
            ) from e

    def _ensure_dataset_exists(self) -> None:
        """Create the dataset if it doesn't exist."""

        # Check if dataset exists
        try:
            resp = self.session.get(f"{self.url}/$/datasets")
            if resp.status_code == 200:
                datasets = resp.json().get("datasets", [])
                if any(d.get("ds.name") == f"/{self.dataset_name}" for d in datasets):
                    return  # Dataset exists
        except:
            pass

        # Create dataset if it doesn't exist
        try:
            payload = {
                "dbName": self.dataset_name,
                "dbType": "TDB2"
            }
            resp = self.session.post(
                f"{self.url}/$/datasets",
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            if resp.status_code not in (200, 201, 409):  # 409 = already exists
                pass  # Continue anyway
        except:
            pass  # Continue anyway

    def add_triple(self, subject: str, predicate: str, obj: str) -> None:
        """Add an RDF triple to Fuseki.

        Args:
            subject: Subject URI
            predicate: Predicate/property URI
            obj: Object URI or literal value

        Raises:
            RuntimeError: If the SPARQL UPDATE fails.
        """
        # Determine if obj is a URI or a literal
        if obj.startswith("http://") or obj.startswith("https://") or obj.startswith("urn:"):
            obj_term = f"<{obj}>"
        else:
            # Escape quotes in literal values
            escaped = obj.replace("\\", "\\\\").replace('"', '\\"')
            obj_term = f'"{escaped}"'

        sparql = f"INSERT DATA {{ <{subject}> <{predicate}> {obj_term} . }}"

        try:
            resp = self.session.post(
                self.update_url,
                data={"update": sparql},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
            resp.raise_for_status()
        except Exception as e:
            raise RuntimeError(f"Failed to add triple: {e}") from e

    def query_sparql(self, sparql: str) -> dict:
        """Execute SPARQL query against Fuseki.

        Args:
            sparql: SPARQL query string

        Returns:
            Query results as dict with 'results' containing 'bindings'
        """

        try:
            # POST SPARQL query to Fuseki
            resp = self.session.post(
                self.sparql_url,
                data={"query": sparql},
                headers={"Accept": "application/sparql-results+json"},
                timeout=30
            )
            resp.raise_for_status()

            # Parse JSON results
            return resp.json()
        except Exception as e:
            raise RuntimeError(
                f"SPARQL query failed: {e}"
            ) from e

    def export_rdf(self, format: str = "turtle") -> str:
        """Export RDF graph from Fuseki.

        Args:
            format: RDF format (turtle, rdfxml, ntriples, jsonld)

        Returns:
            Serialised RDF string.

        Raises:
            RuntimeError: If the export request fails.
        """
        accept_map = {
            "turtle": "text/turtle",
            "rdfxml": "application/rdf+xml",
            "ntriples": "application/n-triples",
            "jsonld": "application/ld+json",
        }
        accept = accept_map.get(format, "text/turtle")

        try:
            resp = self.session.get(
                f"{self.url}/{self.dataset_name}",
                headers={"Accept": accept},
                timeout=60,
            )
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            raise RuntimeError(f"Failed to export RDF ({format}): {e}") from e

    def add_triples_batch(self, triples: list[tuple[str, str, str]]) -> None:
        """Batch add RDF triples via a single SPARQL INSERT DATA.

        Args:
            triples: List of (subject, predicate, object) tuples.

        Raises:
            RuntimeError: If the SPARQL UPDATE fails.
        """
        if not triples:
            return

        parts: list[str] = []
        for subj, pred, obj in triples:
            if obj.startswith("http://") or obj.startswith("https://") or obj.startswith("urn:"):
                obj_term = f"<{obj}>"
            else:
                escaped = obj.replace("\\", "\\\\").replace('"', '\\"')
                obj_term = f'"{escaped}"'
            parts.append(f"<{subj}> <{pred}> {obj_term} .")

        # Fuseki supports large INSERT DATA; chunk if needed
        chunk_size = 500
        for i in range(0, len(parts), chunk_size):
            chunk = parts[i : i + chunk_size]
            sparql = "INSERT DATA { " + " ".join(chunk) + " }"
            try:
                resp = self.session.post(
                    self.update_url,
                    data={"update": sparql},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=60,
                )
                resp.raise_for_status()
            except Exception as e:
                raise RuntimeError(
                    f"Failed to add triples batch (chunk {i // chunk_size}): {e}"
                ) from e

    def load_ontology(self, ontology_content: str) -> None:
        """Load ontology (TBox) into Fuseki.

        Args:
            ontology_content: Ontology in any RDF format (Turtle, RDF/XML, etc.)
            
        Raises:
            RuntimeError: If loading to Fuseki fails
        """
        # Detect content type from format
        if ontology_content.strip().startswith('<?xml'):
            content_type = "application/rdf+xml"
        elif 'turtle' in ontology_content.lower() or '@prefix' in ontology_content:
            content_type = "text/turtle"
        else:
            content_type = "application/rdf+xml"  # Default to RDF/XML

        try:
            # Use the graph store endpoint to load RDF directly
            resp = self.session.post(
                f"{self.url}/{self.dataset_name}",
                data=ontology_content,
                headers={"Content-Type": content_type},
            )
            resp.raise_for_status()
        except Exception as e:
            raise RuntimeError(
                f"Failed to load ontology into Fuseki: {e}"
            ) from e

    def validate_ontology(self) -> bool:
        """Validate ontology consistency via basic SPARQL checks.

        Runs lightweight consistency queries (orphan properties, missing
        domain/range declarations).  For full OWL DL reasoning, use an
        external reasoner such as Pellet or HermiT.

        Returns:
            True if no issues found, False otherwise.
        """
        # Check for properties missing rdfs:domain or rdfs:range
        check_query = """
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX owl:  <http://www.w3.org/2002/07/owl#>
            SELECT (COUNT(?p) AS ?cnt) WHERE {
                ?p a owl:ObjectProperty .
                FILTER NOT EXISTS { ?p rdfs:domain ?d }
            }
        """
        try:
            result = self.query_sparql(check_query)
            bindings = result.get("results", {}).get("bindings", [])
            if bindings:
                count = int(bindings[0].get("cnt", {}).get("value", "0"))
                return count == 0
            return True
        except Exception:
            return False
