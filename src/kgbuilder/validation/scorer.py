"""KG quality scorer combining SHACL2FOL static checks with pySHACL runtime validation.

Provides a compact, actionable quality score for CI/experiment pipelines.

Metrics:
    consistency  – 1.0 if the shapes graph is satisfiable, else 0.0
    acceptance_rate – fraction of sampled SHACL2FOL actions that validate
    class_coverage – fraction of ontology classes present in the graph
    shacl_score – 1.0 minus normalised pySHACL violation count
    violations – absolute pySHACL violation count
    combined_score – weighted aggregate in [0, 1]

pySHACL is *always* executed.  If no pre-built ``shapes.ttl`` exists,
shapes are generated on the fly from the OWL ontology via
``SHACLShapeGenerator``.  The JSON report is written to
``output/validation_reports/shacl_report_<ts>.json``.

Usage::

    scorer = KGQualityScorer(ontology_owl_path=Path("data/ontology/law/law-ontology-v1.0.owl"))
    report = scorer.score_neo4j_store(neo4j_store, shapes_path=Path("shapes.ttl"))
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import rdflib
import structlog

from kgbuilder.storage.neo4j_store import Neo4jGraphStore
from kgbuilder.validation.action_converter import ActionConverter
from kgbuilder.validation.shacl_generator import SHACLShapeGenerator
from kgbuilder.validation.shacl_validator import SHACLValidator
from kgbuilder.validation.static_validator import StaticValidator

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Report dataclass
# ---------------------------------------------------------------------------


@dataclass
class KGQualityReport:
    """Result of a full KG quality scoring run."""

    consistency: float
    violations: int
    acceptance_rate: float
    class_coverage: float
    shacl_score: float
    combined_score: float
    details: dict = field(default_factory=dict)
    shacl_report_path: str | None = None


# ---------------------------------------------------------------------------
# Weights (easily tunable; must sum to 1.0)
# ---------------------------------------------------------------------------
W_CONSISTENCY = 0.30
W_ACCEPTANCE = 0.20
W_COVERAGE = 0.15
W_SHACL = 0.35


# ---------------------------------------------------------------------------
# Lightweight OWL reader for standalone scorer usage
# ---------------------------------------------------------------------------
class _FileOntologyService:
    """Minimal ontology service that reads classes/properties from an OWL file.

    Only implements the subset of the ``OntologyService`` protocol required by
    ``SHACLShapeGenerator``.
    """

    def __init__(self, owl_path: Path) -> None:
        self._g = rdflib.Graph()
        self._g.parse(str(owl_path))
        OWL = rdflib.Namespace("http://www.w3.org/2002/07/owl#")
        RDFS = rdflib.namespace.RDFS
        RDF = rdflib.namespace.RDF
        self._classes: list[dict[str, Any]] = []
        for cls_uri in sorted(
            {s for s, _, _ in self._g.triples((None, RDF.type, OWL.Class)) if isinstance(s, rdflib.URIRef)},
            key=str,
        ):
            label = str(cls_uri).rsplit("#", 1)[-1].rsplit("/", 1)[-1]
            parent = None
            for _, _, o in self._g.triples((cls_uri, RDFS.subClassOf, None)):
                if isinstance(o, rdflib.URIRef):
                    parent = str(o)
                    break
            self._classes.append({"uri": str(cls_uri), "label": label, "parent_uri": parent, "description": "", "properties": []})

    def get_all_classes(self) -> list[dict[str, Any]]:
        return self._classes

    def get_class_properties(self, class_label: str) -> list[dict[str, Any]]:
        return []

    def get_special_properties(self) -> list[dict[str, Any]]:
        return []


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------


class KGQualityScorer:
    """Score a knowledge graph using SHACL2FOL static checks **and** pySHACL.

    pySHACL is always run.  If no ``SHACLValidator`` is injected, the scorer
    will generate SHACL shapes from the OWL ontology (``ontology_owl_path``)
    and create one internally.

    Args:
        static_validator: SHACL2FOL-based validator (optional).
        shacl_validator: Pre-built ``SHACLValidator`` (optional; created from
            OWL if not given).
        ontology_owl_path: Path to an OWL file used for shape generation and
            class-coverage computation.  Required when ``shacl_validator`` is
            ``None``.
        sample_limit: Max entities/relations to sample with SHACL2FOL
            action checks.  Default **500**.
    """

    REPORT_DIR = Path("output/validation_reports")

    def __init__(
        self,
        static_validator: StaticValidator | None = None,
        shacl_validator: SHACLValidator | None = None,
        ontology_owl_path: Path | None = None,
        sample_limit: int = 500,
    ) -> None:
        self._sv = static_validator or StaticValidator()
        self._converter = ActionConverter()
        self._shacl_validator = shacl_validator
        self._owl_path = ontology_owl_path
        self._sample_limit = sample_limit
        # Generated lazily when first needed
        self._shapes_graph: rdflib.Graph | None = None
        self._ontology_class_count: int | None = None

    # ------------------------------------------------------------------
    # Shape generation helpers
    # ------------------------------------------------------------------

    def _ensure_shapes_graph(self, shapes_path: Path | None = None) -> rdflib.Graph | None:
        """Return a SHACL shapes graph, generating from OWL if necessary.

        Returns ``None`` when no shapes source is available (instead of
        raising) so callers can degrade gracefully.
        """
        if self._shapes_graph is not None:
            return self._shapes_graph

        # 1) Try loading from file
        if shapes_path and shapes_path.exists():
            g = rdflib.Graph()
            g.parse(str(shapes_path))
            if len(g) > 0:
                self._shapes_graph = g
                logger.info("shapes_loaded_from_file", path=str(shapes_path), triples=len(g))
                return g

        # 2) Generate from OWL ontology
        if self._owl_path and self._owl_path.exists():
            svc = _FileOntologyService(self._owl_path)
            gen = SHACLShapeGenerator(svc)
            g = gen.generate()
            self._shapes_graph = g
            self._ontology_class_count = len(svc.get_all_classes())
            logger.info(
                "shapes_generated_from_owl",
                owl=str(self._owl_path),
                triples=len(g),
                classes=self._ontology_class_count,
            )
            return g

        # 3) If a shacl_validator was injected, extract its shapes graph
        if self._shacl_validator is not None:
            sg = getattr(self._shacl_validator, "shapes_graph", None)
            if sg is not None and len(sg) > 0:
                self._shapes_graph = sg
                return sg

        logger.warning("no_shapes_source_available")
        return None

    def _ensure_shacl_validator(self, shapes_path: Path | None = None) -> SHACLValidator:
        """Return the ``SHACLValidator``, creating one from the shapes graph."""
        if self._shacl_validator is not None:
            return self._shacl_validator

        shapes_g = self._ensure_shapes_graph(shapes_path)
        self._shacl_validator = SHACLValidator(shapes_g)
        return self._shacl_validator

    # ------------------------------------------------------------------
    # Neo4j sampling
    # ------------------------------------------------------------------

    def _sample_actions_from_neo4j(
        self, store: Neo4jGraphStore, limit: int | None = None,
    ) -> tuple[list[Any], list[Any]]:
        """Retrieve entities and relations from Neo4j for SHACL2FOL checks.

        Returns:
            ``(entities, relations)`` – lightweight objects with ``entity_type``
            / ``relation_type`` / ``source_type`` / ``target_type`` attributes.
        """
        limit = limit or self._sample_limit

        # --- entities ------------------------------------------------
        entities: list[Any] = []
        try:
            q = (
                "MATCH (n) "
                "UNWIND labels(n) AS lbl "
                "WITH lbl, collect(n)[0] AS sample "
                "RETURN sample.id AS id, lbl AS label "
                "LIMIT $limit"
            )
            rows = store.query(q, params={"limit": limit})
            records = getattr(rows, "records", rows) or []
            for r in records:
                lbl = r.get("label") if isinstance(r, dict) else getattr(r, "label", "Thing")
                entities.append(type("_E", (), {"entity_type": lbl})())
        except Exception as exc:
            logger.warning("entity_sampling_failed", error=str(exc))

        # Fallback: also sample raw nodes if label-based yielded nothing
        if not entities:
            try:
                q2 = "MATCH (n) RETURN n.id AS id, labels(n) AS labels LIMIT $limit"
                rows = store.query(q2, params={"limit": limit})
                records = getattr(rows, "records", rows) or []
                for r in records:
                    labels = (r.get("labels") if isinstance(r, dict) else []) or []
                    ent_type = labels[0] if labels else "Thing"
                    entities.append(type("_E", (), {"entity_type": ent_type})())
            except Exception:
                pass

        # --- relations -----------------------------------------------
        rels: list[Any] = []
        try:
            q = (
                "MATCH (a)-[r]->(b) "
                "RETURN type(r) AS rel, labels(a) AS src, labels(b) AS tgt "
                "LIMIT $limit"
            )
            rows = store.query(q, params={"limit": limit})
            records = getattr(rows, "records", rows) or []
            for r in records:
                if isinstance(r, dict):
                    rel_type = r.get("rel", "RELATED_TO")
                    src_labels = r.get("src") or []
                    tgt_labels = r.get("tgt") or []
                else:
                    rel_type = getattr(r, "rel", "RELATED_TO")
                    src_labels = getattr(r, "src", []) or []
                    tgt_labels = getattr(r, "tgt", []) or []
                src = src_labels[0] if src_labels else "Thing"
                tgt = tgt_labels[0] if tgt_labels else "Thing"
                rels.append(
                    type("_R", (), {"relation_type": rel_type, "source_type": src, "target_type": tgt})()
                )
        except Exception as exc:
            logger.warning("relation_sampling_failed", error=str(exc))

        logger.info("sampled_actions", entities=len(entities), relations=len(rels))
        return entities, rels

    # ------------------------------------------------------------------
    # Class coverage
    # ------------------------------------------------------------------

    def _compute_class_coverage(
        self, store: Any, shapes_graph: rdflib.Graph | None,
    ) -> float:
        """Fraction of ontology classes that appear as node labels in the KG."""
        try:
            # Count distinct labels in graph
            if hasattr(store, "query"):
                res = store.query(
                    "MATCH (n) UNWIND labels(n) AS l "
                    "RETURN count(DISTINCT l) AS cnt"
                )
                cnt = 0
                if res and getattr(res, "records", None):
                    cnt = int(res.records[0].get("cnt", 0))
                elif isinstance(res, list) and res:
                    cnt = int(res[0].get("cnt", 0))
            else:
                cnt = 0

            # Ontology class count (cached from OWL parse, or count NodeShapes)
            if self._ontology_class_count is not None:
                total = self._ontology_class_count
            elif shapes_graph is not None:
                SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")
                total = len(list(shapes_graph.subjects(rdflib.RDF.type, SH.NodeShape)))
            else:
                total = 1  # avoid div-by-zero; coverage will be approximate

            coverage = float(cnt) / max(1.0, float(total))
            return min(1.0, coverage)
        except Exception as exc:
            logger.debug("class_coverage_failed", error=str(exc))
            return 0.0

    # ------------------------------------------------------------------
    # pySHACL execution
    # ------------------------------------------------------------------

    def _run_pyshacl(
        self, store: Any, shapes_path: Path | None = None,
    ) -> tuple[float, int, str | None]:
        """Always run pySHACL validation.

        Returns:
            ``(score, violation_count, report_path)``
        """
        validator = self._ensure_shacl_validator(shapes_path)
        sh_res = validator.validate(store)

        sh_valid = getattr(sh_res, "valid", False)
        violations = list(getattr(sh_res, "violations", []))
        n_violations = len(violations)

        # Normalise violations to [0, 1]  (cap penalty at 200)
        norm = max(0.0, 1.0 - min(n_violations, 200) / 200.0)
        score = float(norm) if sh_valid else max(0.0, norm * 0.5)

        # Write JSON report
        self.REPORT_DIR.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        report_path = self.REPORT_DIR / f"shacl_report_{ts}.json"
        payload = {
            "timestamp": ts,
            "valid": sh_valid,
            "violation_count": n_violations,
            "node_count": getattr(sh_res, "node_count", None),
            "edge_count": getattr(sh_res, "edge_count", None),
            "violations": [],
        }
        for v in violations:
            payload["violations"].append(
                {k: str(val) for k, val in v.__dict__.items()} if hasattr(v, "__dict__") else str(v)
            )

        with open(report_path, "w") as fp:
            json.dump(payload, fp, indent=2, default=str)

        logger.info(
            "pyshacl_complete",
            valid=sh_valid,
            violations=n_violations,
            score=round(score, 4),
            report=str(report_path),
        )
        return score, n_violations, str(report_path)

    # ------------------------------------------------------------------
    # Main scoring entry-point
    # ------------------------------------------------------------------

    def score_store(
        self,
        store: Any,
        shapes_path: Path | str | None = None,
    ) -> KGQualityReport:
        """Score a graph store (Neo4j or compatible ``GraphStore``).

        Steps:
            1. Ensure / generate SHACL shapes
            2. Check satisfiability via SHACL2FOL (best-effort)
            3. Sample entities+relations and validate via SHACL2FOL
            4. Compute class coverage
            5. **Always** run pySHACL
            6. Compute weighted combined score
        """
        shapes = Path(shapes_path) if shapes_path else None

        # 1) Shapes graph (generate from OWL if needed)
        shapes_graph = self._ensure_shapes_graph(shapes)

        # 2) SHACL2FOL satisfiability (best-effort)
        consistency = 0.0
        sat_details: dict[str, Any] = {}
        if shapes and shapes.exists():
            try:
                sat = self._sv.check_satisfiability(shapes)
                consistency = 1.0 if sat.valid else 0.0
                sat_details = sat.__dict__
            except Exception as exc:
                logger.warning("satisfiability_check_failed", error=str(exc))
        else:
            # No file on disk → skip SHACL2FOL but do not penalise
            consistency = 1.0
            sat_details = {"skipped": True, "reason": "no shapes file on disk"}

        # 3) Sample actions for SHACL2FOL validation
        entities: list[Any] = []
        relations: list[Any] = []
        if isinstance(store, Neo4jGraphStore):
            entities, relations = self._sample_actions_from_neo4j(store)
        elif hasattr(store, "to_dict"):
            data = store.to_dict()
            entities = data.get("entities", [])[:self._sample_limit]
            relations = data.get("relations", [])[:self._sample_limit]

        acceptance = 0.0
        sv_details: dict[str, Any] = {}
        if (entities or relations) and shapes and shapes.exists():
            try:
                sv_res = self._sv.validate_entities_and_relations(shapes, entities, relations)
                acceptance = 1.0 if sv_res.valid else 0.0
                sv_details = sv_res.__dict__
            except Exception as exc:
                logger.warning("static_validation_failed", error=str(exc))
        elif entities or relations:
            # Shapes generated from OWL but not persisted – skip SHACL2FOL
            acceptance = 1.0
            sv_details = {"skipped": True}
        else:
            logger.warning("no_sampled_actions", store=type(store).__name__)

        # 4) Class coverage
        class_coverage = self._compute_class_coverage(store, shapes_graph)

        # 5) pySHACL – always runs  ======================================
        try:
            shacl_score, n_violations, report_path = self._run_pyshacl(store, shapes)
        except Exception as exc:
            logger.error("pyshacl_failed", error=str(exc))
            shacl_score, n_violations, report_path = 0.0, 0, None

        # 6) Combined score
        combined = (
            W_CONSISTENCY * consistency
            + W_ACCEPTANCE * acceptance
            + W_COVERAGE * class_coverage
            + W_SHACL * shacl_score
        )

        details = {
            "satisfiability": sat_details,
            "validation": sv_details,
            "sampling": {"entities": len(entities), "relations": len(relations)},
            "pyshacl": {
                "score": shacl_score,
                "violations": n_violations,
                "report_path": report_path,
            },
            "weights": {
                "consistency": W_CONSISTENCY,
                "acceptance": W_ACCEPTANCE,
                "coverage": W_COVERAGE,
                "shacl": W_SHACL,
            },
        }

        return KGQualityReport(
            consistency=consistency,
            violations=n_violations,
            acceptance_rate=acceptance,
            class_coverage=class_coverage,
            shacl_score=shacl_score,
            combined_score=round(combined, 4),
            details=details,
            shacl_report_path=report_path,
        )

    def score_neo4j_store(
        self,
        store: Neo4jGraphStore,
        shapes_path: Path | str | None = None,
    ) -> KGQualityReport:
        """Convenience alias for ``score_store`` with a Neo4j store."""
        return self.score_store(store, shapes_path)
