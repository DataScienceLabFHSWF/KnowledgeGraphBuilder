"""KG quality scorer using SHACL2FOL static checks.

Provides a compact, actionable quality score produced from static
validation outcomes. The scorer is intentionally lightweight and intended
for CI/experiments rather than exhaustive formal assessment.

Metrics computed:
- consistency: 1.0 if shapes graph is satisfiable, else 0.0
- violations: number of failing validation actions (approximate)
- acceptance_rate: fraction of sampled actions that validate
- class_coverage: fraction of ontology classes present in the KG
- combined_score: weighted aggregate in [0,1]

Usage example:
    scorer = KGQualityScorer(static_validator=StaticValidator())
    report = scorer.score_neo4j_store(neo4j_store, shapes_path=Path("shapes.ttl"))

"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import structlog

from kgbuilder.validation import StaticValidator
from kgbuilder.validation.action_converter import ActionConverter
from kgbuilder.validation.shacl_generator import SHACLShapeGenerator
from kgbuilder.storage.neo4j_store import Neo4jGraphStore

logger = structlog.get_logger(__name__)


@dataclass
class KGQualityReport:
    consistency: float
    violations: int
    acceptance_rate: float
    class_coverage: float
    combined_score: float
    details: dict


class KGQualityScorer:
    """Score a knowledge graph using SHACL2FOL static checks.

    The scorer samples a small set of entities/relations from the graph
    store, converts them to SHACL2FOL actions and uses `StaticValidator`
    to determine whether those updates would be accepted by the
    ontology+shapes. This yields lightweight, reproducible quality
    indicators suitable for experiments and CI.
    """

    def __init__(self, static_validator: StaticValidator | None = None) -> None:
        self._sv = static_validator or StaticValidator()
        self._converter = ActionConverter()

    def _sample_actions_from_neo4j(self, store: Neo4jGraphStore, limit: int = 50) -> tuple[list[Any], list[Any]]:
        """Retrieve a small sample of entities and relations from Neo4j.

        Returns (entities, relations) lists compatible with
        ActionConverter.from_entities_and_relations()."""
        # Defensive: Neo4jGraphStore exposes `query()` for ad-hoc reads.
        try:
            q_nodes = "MATCH (n:Entity) RETURN n.id AS id, labels(n) AS labels LIMIT $limit"
            rows = store.query(q_nodes, parameters={"limit": limit})
        except Exception:
            # Fallback: use store.to_dict() export if query unsupported
            dump = store.to_dict() if hasattr(store, "to_dict") else {"entities": []}
            rows = dump.get("entities", [])[:limit]

        entities: list[Any] = []
        for r in rows:
            # normalize different return formats
            if isinstance(r, dict):
                labels = r.get("labels") or [l for l in r.get("label",[])]
                ent_type = labels[0] if labels else "Thing"
                entity = type("_E", (), {"entity_type": ent_type})()
            else:
                # py2neo/neo4j record-like
                labels = getattr(r, "labels", None) or r.get("labels", [])
                ent_type = labels[0] if labels else "Thing"
                entity = type("_E", (), {"entity_type": ent_type})()
            entities.append(entity)

        # Relations: sample edges and map to simple relation objects
        rels: list[Any] = []
        try:
            q_rels = "MATCH (a)-[r]->(b) RETURN type(r) AS rel, labels(a) AS src_labels, labels(b) AS tgt_labels LIMIT $limit"
            rows = store.query(q_rels, parameters={"limit": limit})
        except Exception:
            rows = []

        for r in rows:
            rel_type = r.get("rel") if isinstance(r, dict) else getattr(r, "rel", None) or r[0]
            src_labels = r.get("src_labels") if isinstance(r, dict) else (r[1] if len(r) > 1 else [])
            tgt_labels = r.get("tgt_labels") if isinstance(r, dict) else (r[2] if len(r) > 2 else [])
            src = src_labels[0] if src_labels else "Thing"
            tgt = tgt_labels[0] if tgt_labels else "Thing"
            relation = type("_R", (), {"relation_type": rel_type, "source_type": src, "target_type": tgt})()
            rels.append(relation)

        return entities, rels

    def score_store(self, store: Any, shapes_path: Path | str) -> KGQualityReport:
        """Score a graph store (Neo4j or other GraphStore).

        Steps:
        1. Ensure shapes are satisfiable (consistency)
        2. Sample actions and run validate_entities_and_relations()
        3. Compute simple metrics and aggregate
        """
        shapes = Path(shapes_path)
        # 1) satisfiability
        sat = self._sv.check_satisfiability(shapes)
        consistency = 1.0 if sat.valid else 0.0

        # 2) sample actions
        entities: list[Any] = []
        relations: list[Any] = []
        if isinstance(store, Neo4jGraphStore):
            entities, relations = self._sample_actions_from_neo4j(store, limit=100)
        else:
            # try to call export or to_dict
            if hasattr(store, "to_dict"):
                data = store.to_dict()
                entities = data.get("entities", [])[:100]
                relations = data.get("relations", [])[:100]

        if not entities and not relations:
            logger.warning("no_sampled_actions", store=type(store).__name__)

        # 3) validate sampled actions
        sv_res = self._sv.validate_entities_and_relations(shapes, entities, relations)

        # acceptance_rate approximated by whether static validator accepted the combined action set
        accepted = 1 if sv_res.valid else 0
        violations = 0 if sv_res.valid else 1

        # 4) class coverage: fraction of ontology classes present in graph (best-effort)
        class_coverage = 0.0
        try:
            if hasattr(store, "query"):
                total_classes_q = "CALL db.labels() YIELD label RETURN count(label) AS cnt"
                # best-effort: count distinct labels in Neo4j
                res = store.query("MATCH (n) UNWIND labels(n) AS l RETURN count(DISTINCT l) AS cnt")
                cnt = res[0][0] if res and len(res) and isinstance(res[0], (list, tuple)) else (res[0].get("cnt") if res and isinstance(res[0], dict) else 0)
                # approximate ontology class count by reading shapes file (count sh:NodeShape)
                try:
                    from rdflib import Graph
                    g = Graph()
                    g.parse(shapes)
                    ns = "http://www.w3.org/ns/shacl#"
                    node_shapes = len(list(g.triples((None, None, None))))
                    # avoid division by zero; use simple heuristic
                    class_coverage = float(cnt) / max(1.0, float(node_shapes))
                    class_coverage = min(1.0, class_coverage)
                except Exception:
                    class_coverage = 0.0
        except Exception:
            class_coverage = 0.0

        # 5) combined score (weights): consistency 0.5, acceptance 0.3, coverage 0.2
        combined = 0.5 * consistency + 0.3 * accepted + 0.2 * class_coverage

        details = {
            "satisfiability": sat.__dict__,
            "validation": sv_res.__dict__,
        }

        return KGQualityReport(
            consistency=consistency,
            violations=violations,
            acceptance_rate=float(accepted),
            class_coverage=float(class_coverage),
            combined_score=float(combined),
            details=details,
        )

    def score_neo4j_store(self, store: Neo4jGraphStore, shapes_path: Path | str) -> KGQualityReport:
        return self.score_store(store, shapes_path)
