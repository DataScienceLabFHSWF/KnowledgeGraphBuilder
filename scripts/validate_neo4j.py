"""Validate the live Neo4j KG against SHACL shapes generated from OWL.

- Generates SHACL shapes (best-effort) from the OWL ontology.
- Uses `SHACLValidator` (pyshacl) to validate the Neo4jGraphStore.
- Prints a summary and writes a detailed report to /tmp.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

# Minimal FileOntologyService (copied from scripts/validate_kg_ttl.py) - lightweight OWL reader
import rdflib

from kgbuilder.storage.neo4j_store import Neo4jGraphStore
from kgbuilder.validation.shacl_generator import SHACLShapeGenerator
from kgbuilder.validation.shacl_validator import SHACLValidator


class FileOntologyService:
    def __init__(self, owl_path: Path, ontology_namespace: str | None = None) -> None:
        self._g = rdflib.Graph()
        self._g.parse(str(owl_path))
        self._ns = ontology_namespace

    def _local(self, uri) -> str:
        try:
            return rdflib.URIRef(uri).split('#')[-1]
        except Exception:
            return str(uri)

    def get_all_classes(self) -> list[str]:
        CLASSES = set()
        for s in self._g.subjects(rdflib.RDF.type, rdflib.OWL.Class):
            CLASSES.add(self._local(s))
        for s in self._g.subjects(rdflib.RDF.type, rdflib.RDFS.Class):
            CLASSES.add(self._local(s))
        return sorted([c for c in CLASSES if c])

    def get_class_properties(self, class_label: str) -> list[tuple]:
        out = []
        for prop in set(self._g.subjects(rdflib.RDF.type, rdflib.OWL.ObjectProperty)) | set(
            self._g.subjects(rdflib.RDF.type, rdflib.OWL.DatatypeProperty)
        ):
            domains = [self._local(o) for o in self._g.objects(prop, rdflib.RDFS.domain)]
            if class_label in domains:
                ranges = [self._local(o) for o in self._g.objects(prop, rdflib.RDFS.range)]
                kind = "DatatypeProperty" if (prop, rdflib.RDF.type, rdflib.OWL.DatatypeProperty) in self._g else "ObjectProperty"
                rng = ranges[0] if ranges else None
                out.append((self._local(prop), kind, rng, {}))
        return out

    def get_special_properties(self) -> dict:
        special = {"functional": [], "inverse": []}
        for p in self._g.subjects(rdflib.RDF.type, rdflib.OWL.FunctionalProperty):
            special["functional"].append(self._local(p))
        for s, o in self._g.subject_objects(rdflib.OWL.inverseOf):
            special["inverse"].append((self._local(s), self._local(o)))
        return special

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("validate_neo4j")


def main() -> None:
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    pwd = os.getenv("NEO4J_PASSWORD", "changeme")

    owl = Path(os.getenv("LAW_ONTOLOGY_PATH", "data/ontology/law/law-ontology-v1.0.owl"))
    if not owl.exists():
        logger.error("Ontology OWL not found: %s", owl)
        return

    logger.info("Connecting to Neo4j: %s", uri)
    store = Neo4jGraphStore(uri, (user, pwd))

    logger.info("Generating shapes from OWL: %s", owl)
    onto = FileOntologyService(owl)
    gen = SHACLShapeGenerator(onto, namespace="http://example.org/shapes/", ontology_namespace="http://example.org/ontology#")
    shapes = gen.generate()

    # Save shapes for inspection
    shapes_path = Path("/tmp/generated_shapes_from_owl.ttl")
    shapes.serialize(destination=str(shapes_path), format="turtle")
    logger.info("Shapes written to %s", shapes_path)

    logger.info("Validating Neo4j graph against generated shapes (pyshacl)")
    validator = SHACLValidator(shapes)
    result = validator.validate(store)

    logger.info("Validation result: valid=%s, violations=%d", result.valid, len(result.violations))
    if not result.valid:
        for v in result.violations:
            logger.info("- %s", v)

    out = Path("/tmp/neo4j_shacl_report.json")
    with open(out, "w") as f:
        f.write(str(result))
    logger.info("Wrote validation summary to %s", out)


if __name__ == "__main__":
    main()
