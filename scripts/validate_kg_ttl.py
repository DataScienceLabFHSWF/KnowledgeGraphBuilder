"""Validate an exported KG Turtle file against SHACL shapes generated from an OWL ontology.

- Finds the KG TTL (defaults to `output/comparison/with_law_context/kg_export.ttl`).
- Loads the law OWL ontology (defaults to `data/ontology/law/law-ontology-v1.0.owl`).
- Generates SHACL shapes using `SHACLShapeGenerator` (best-effort).
- Runs `pyshacl.validate()` and prints a summary + writes a report file.

Usage:
    python scripts/validate_kg_ttl.py \
        --kg output/comparison/with_law_context/kg_export.ttl \
        --owl data/ontology/law/law-ontology-v1.0.owl
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import rdflib
from pyshacl import validate

from kgbuilder.validation.shacl_generator import SHACLShapeGenerator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("validate_kg_ttl")


class FileOntologyService:
    """Minimal ontology accessor backed by an RDFLib graph (OWL file).

    Provides the small API SHACLShapeGenerator expects: `get_all_classes()`,
    `get_class_properties(class_label)`, and `get_special_properties()`.
    This is intentionally conservative (best-effort extraction).
    """

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
        # Find properties with this class in their rdfs:domain
        out = []
        for p in self._g.subjects(rdflib.RDFS.domain, None):
            pass
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
        # inverseOf pairs
        for s, o in self._g.subject_objects(rdflib.OWL.inverseOf):
            special["inverse"].append((self._local(s), self._local(o)))
        return special


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kg", type=Path, default=Path("output/comparison/with_law_context/kg_export.ttl"))
    ap.add_argument("--owl", type=Path, default=Path("data/ontology/law/law-ontology-v1.0.owl"))
    ap.add_argument("--out-shapes", type=Path, default=Path("/tmp/generated_shapes.ttl"))
    args = ap.parse_args()

    if not args.kg.exists():
        logger.error("KG TTL not found: %s", args.kg)
        raise SystemExit(1)
    if not args.owl.exists():
        logger.error("OWL ontology not found: %s", args.owl)
        raise SystemExit(1)

    logger.info("Loading KG TTL: %s", args.kg)

    # Try parsing the TTL; if rdflib fails due to invalid prefixed names we
    # perform a best-effort cleanup (expand problematic `kg:` qnames to
    # full <...> URIs with URL-encoded local part) and re-parse.
    def _clean_ttl(path: Path) -> str:
        text = path.read_text(encoding="utf-8")
        import re
        from urllib.parse import quote

        # Replace kg:LOCAL where LOCAL contains characters outside [A-Za-z0-9_-]
        def _replace(match: re.Match[str]) -> str:
            local = match.group(1)
            if re.fullmatch(r"[A-Za-z0-9_-]+", local):
                return match.group(0)
            return f"<http://example.org/kg{quote(local, safe='')}>"

        # Match kg: followed by any run of non-whitespace, non-terminator
        cleaned = re.sub(r"\bkg:([^\s;.,{}]+)", _replace, text)
        return cleaned

    data_g = rdflib.Graph()
    try:
        data_g.parse(str(args.kg), format="turtle")
    except Exception as e:
        logger.warning("Initial parse failed (%s), attempting TTL cleanup", e)
        cleaned = _clean_ttl(args.kg)
        tmp_out = args.kg.with_suffix(".cleaned.ttl")
        tmp_out.write_text(cleaned, encoding="utf-8")
        logger.info("Wrote cleaned TTL to %s", tmp_out)

        # Aggressive second-pass: replace any remaining invalid qnames of the
        # form `kg:...` that contain characters outside the safe set. This
        # handles parentheses, commas, and other punctuation produced by the
        # exporter.
        import re
        from urllib.parse import quote

        def _aggressive_replace(m: re.Match[str]) -> str:
            local = m.group(1)
            if re.fullmatch(r"[A-Za-z0-9_-]+", local):
                return m.group(0)
            return f"<http://example.org/kg/{quote(local, safe='')}>"

        cleaned2 = re.sub(r"\bkg:([^\s;.,{}]+)", _aggressive_replace, cleaned)
        tmp_out2 = args.kg.with_suffix(".cleaned2.ttl")
        tmp_out2.write_text(cleaned2, encoding="utf-8")
        logger.info("Wrote aggressively cleaned TTL to %s", tmp_out2)

        # Try parsing the aggressively cleaned file
        data_g.parse(str(tmp_out2), format="turtle")
        # continue using cleaned2 for validation
        args.kg = tmp_out2

    logger.info("Loading ontology OWL: %s", args.owl)
    onto = FileOntologyService(args.owl, ontology_namespace=None)

    logger.info("Generating SHACL shapes from ontology (best-effort)")
    gen = SHACLShapeGenerator(onto, namespace="http://example.org/shapes/", ontology_namespace="http://example.org/ontology#")
    shapes = gen.generate()
    args.out_shapes.parent.mkdir(parents=True, exist_ok=True)
    shapes.serialize(destination=str(args.out_shapes), format="turtle")
    logger.info("Shapes written to %s", args.out_shapes)

    logger.info("Running pyshacl validation (this may take a moment)")
    conforms, results_graph, results_text = validate(data_g, shacl_graph=shapes, inference="rdfs")

    logger.info("Conforms: %s", conforms)
    if not conforms:
        logger.info("SHACL results:\n%s", results_text)
        # write results
        with open(str(args.out_shapes.with_suffix(".report.txt")), "w") as f:
            f.write(results_text)
        logger.info("Wrote SHACL report to %s", args.out_shapes.with_suffix(".report.txt"))
    else:
        logger.info("No SHACL violations found.")


if __name__ == "__main__":
    main()
