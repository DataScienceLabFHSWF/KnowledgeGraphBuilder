#!/usr/bin/env python3
"""Build a Legal Knowledge Graph from German federal law XML files.

Structure-first pipeline that exploits the highly structured XML format
from gesetze-im-internet.de. No competency questions or iterative
discovery needed — the XML structure IS the knowledge.

Pipeline:
1. Parse XML → LawDocument objects (§, sections, cross-references)
2. Create entities from structure (Gesetzbuch, Paragraf, Abschnitt)
3. Create relations from structure (teilVon, referenziert)
4. Embed paragraph text into Qdrant (for later retrieval/QA)
5. Store entities + relations in Neo4j
6. Export results

Usage::

    # Full pipeline (all laws in data/law_html/)
    python scripts/build_law_graph.py

    # Specific laws only
    python scripts/build_law_graph.py --laws AtG StrlSchG StrlSchV

    # Skip embedding (faster, no Qdrant needed)
    python scripts/build_law_graph.py --skip-embed

    # Dry run (parse + extract, don't write to databases)
    python scripts/build_law_graph.py --dry-run

    # Background with logging
    nohup python scripts/build_law_graph.py > law_graph.log 2>&1 &
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
from dotenv import load_dotenv

load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kgbuilder.core.models import (
    ExtractedEntity,
    ExtractedRelation,
)
from kgbuilder.document.loaders.law_adapter import LawDocumentAdapter
from kgbuilder.document.loaders.law_xml import LawDocument, LawXMLReader
from kgbuilder.logging_config import setup_logging
from kgbuilder.storage.protocol import Edge, Node

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class LawGraphConfig:
    """Configuration for the law graph pipeline."""

    law_data_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("LAW_DATA_DIR", "data/law_html")
        )
    )
    ontology_path: Path = field(
        default_factory=lambda: Path(
            os.environ.get(
                "LAW_ONTOLOGY_PATH",
                "data/ontology/legal/legal-foundations-merged.owl",
            )
        )
    )
    output_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("LAW_OUTPUT_DIR", "output/law_results")
        )
    )
    vector_collection: str = "lawgraph"
    neo4j_uri: str = field(
        default_factory=lambda: os.environ.get(
            "NEO4J_URI", "bolt://localhost:7687"
        )
    )
    neo4j_user: str = field(
        default_factory=lambda: os.environ.get("NEO4J_USER", "neo4j")
    )
    neo4j_password: str = field(
        default_factory=lambda: os.environ.get("NEO4J_PASSWORD", "kgbuilder")
    )
    qdrant_url: str = field(
        default_factory=lambda: os.environ.get(
            "QDRANT_URL", "http://localhost:6333"
        )
    )
    ollama_url: str = field(
        default_factory=lambda: os.environ.get(
            "OLLAMA_URL", "http://localhost:18134"
        )
    )
    # Filter to specific law abbreviations (None = all)
    laws: list[str] | None = None
    skip_embed: bool = False
    dry_run: bool = False
    chunking_strategy: str = "paragraph"


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

@dataclass
class LawGraphResult:
    """Tracks pipeline execution results."""

    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    laws_parsed: int = 0
    entities_created: int = 0
    relations_created: int = 0
    documents_embedded: int = 0
    nodes_stored: int = 0
    edges_stored: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    quality: dict[str, Any] = field(default_factory=dict)
    execution_time_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class LawGraphPipeline:
    """Structure-first pipeline for building a law knowledge graph.

    No CQs, no iterative discovery — uses XML structure directly.
    """

    def __init__(self, config: LawGraphConfig) -> None:
        self.config = config
        self.result = LawGraphResult()
        self.reader = LawXMLReader()
        self.adapter = LawDocumentAdapter(chunking_strategy=config.chunking_strategy)

        # Lazy-init storage services
        self._neo4j: Any = None
        self._qdrant: Any = None
        self._embedder: Any = None

    # ------------------------------------------------------------------
    # Storage initialization (lazy)
    # ------------------------------------------------------------------

    def _get_neo4j(self) -> Any:
        """Lazy-init Neo4j connection."""
        if self._neo4j is None:
            from kgbuilder.storage.neo4j_store import Neo4jGraphStore

            self._neo4j = Neo4jGraphStore(
                uri=self.config.neo4j_uri,
                auth=(self.config.neo4j_user, self.config.neo4j_password),
            )
            logger.info("neo4j_connected", uri=self.config.neo4j_uri)
        return self._neo4j

    def _get_qdrant(self) -> Any:
        """Lazy-init Qdrant connection."""
        if self._qdrant is None:
            from kgbuilder.storage.vector import QdrantStore

            self._qdrant = QdrantStore(
                url=self.config.qdrant_url,
                collection_name=self.config.vector_collection,
            )
            logger.info(
                "qdrant_connected",
                url=self.config.qdrant_url,
                collection=self.config.vector_collection,
            )
        return self._qdrant

    def _get_embedder(self) -> Any:
        """Lazy-init embedding provider."""
        if self._embedder is None:
            from kgbuilder.embedding.ollama import OllamaProvider

            self._embedder = OllamaProvider(base_url=self.config.ollama_url)
            logger.info(
                "embedder_connected",
                url=self.config.ollama_url,
                dimension=self._embedder.dimension,
            )
        return self._embedder

    # ------------------------------------------------------------------
    # Main run
    # ------------------------------------------------------------------

    def run(self) -> LawGraphResult:
        """Execute the full law graph pipeline."""
        start = time.time()
        logger.info(
            "law_graph_pipeline_start",
            law_data_dir=str(self.config.law_data_dir),
            laws_filter=self.config.laws,
            dry_run=self.config.dry_run,
            skip_embed=self.config.skip_embed,
        )

        try:
            # 1. Parse XML
            laws = self._parse_laws()

            # 2. Extract entities + relations from structure
            all_entities, all_relations = self._extract_structure(laws)

            # 3. Embed paragraph text into Qdrant
            if not self.config.skip_embed:
                self._embed_documents(laws)

            # 4. Store in Neo4j
            if not self.config.dry_run:
                self._store_graph(all_entities, all_relations)

                # 4b. Quality scoring (pySHACL + SHACL2FOL)
                self._score_quality()

            # 5. Export results
            self._export_results(all_entities, all_relations, laws)

        except Exception as e:
            logger.error("pipeline_failed", error=str(e))
            self.result.errors.append(str(e))
            raise
        finally:
            self.result.execution_time_seconds = time.time() - start
            self._cleanup()

        logger.info(
            "law_graph_pipeline_complete",
            laws=self.result.laws_parsed,
            entities=self.result.entities_created,
            relations=self.result.relations_created,
            embedded=self.result.documents_embedded,
            time_s=round(self.result.execution_time_seconds, 1),
        )
        return self.result

    # ------------------------------------------------------------------
    # Step 1: Parse XML
    # ------------------------------------------------------------------

    def _parse_laws(self) -> list[LawDocument]:
        """Parse all law XML files."""
        logger.info("parsing_laws", dir=str(self.config.law_data_dir))

        all_laws = self.reader.parse_directory(self.config.law_data_dir)

        # Filter if specific laws requested
        if self.config.laws:
            filter_set = set(self.config.laws)
            all_laws = [law for law in all_laws if law.abbreviation in filter_set]
            logger.info(
                "laws_filtered",
                requested=self.config.laws,
                matched=len(all_laws),
            )

        self.result.laws_parsed = len(all_laws)
        for law in all_laws:
            logger.info(
                "law_parsed",
                abbreviation=law.abbreviation,
                paragraphs=len(law.paragraphs()),
                sections=len(law.structure_nodes()),
                cross_refs=len(law.all_cross_references()),
            )

        return all_laws

    # ------------------------------------------------------------------
    # Step 2: Extract structure → entities + relations
    # ------------------------------------------------------------------

    def _extract_structure(
        self, laws: list[LawDocument]
    ) -> tuple[list[ExtractedEntity], list[ExtractedRelation]]:
        """Extract entities and relations from XML structure."""
        logger.info("extracting_structure", law_count=len(laws))

        all_entities: list[ExtractedEntity] = []
        all_relations: list[ExtractedRelation] = []

        for law in laws:
            entities = self.adapter.to_structural_entities(law)
            relations = self.adapter.to_structural_relations(law)
            all_entities.extend(entities)
            all_relations.extend(relations)

            logger.info(
                "law_extracted",
                abbreviation=law.abbreviation,
                entities=len(entities),
                relations=len(relations),
            )

        self.result.entities_created = len(all_entities)
        self.result.relations_created = len(all_relations)

        logger.info(
            "extraction_complete",
            total_entities=len(all_entities),
            total_relations=len(all_relations),
        )
        return all_entities, all_relations

    # ------------------------------------------------------------------
    # Step 3: Embed paragraph text into Qdrant
    # ------------------------------------------------------------------

    def _embed_documents(self, laws: list[LawDocument]) -> None:
        """Embed paragraph text and store in Qdrant."""
        embedder = self._get_embedder()
        qdrant = self._get_qdrant()

        # Collect all paragraph texts and IDs
        texts: list[str] = []
        ids: list[str] = []
        metadata_list: list[dict[str, Any]] = []

        for law in laws:
            for norm in law.paragraphs():
                doc_id = (
                    f"{law.abbreviation}_{norm.enbez}"
                    .replace(" ", "_")
                    .replace("§", "S")
                )
                content = (
                    f"{norm.title}\n\n{norm.text}" if norm.title else norm.text
                )
                texts.append(content)
                ids.append(doc_id)
                metadata_list.append({
                    "law": law.abbreviation,
                    "paragraph": norm.enbez,
                    "title": norm.title or "",
                    "text": content[:500],  # truncate for metadata
                    "graph_type": "law",
                })

        logger.info("embedding_paragraphs", count=len(texts))

        if not texts:
            return

        # Embed in batches
        batch_size = 32
        failed_count = 0
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]
            batch_ids = ids[i : i + batch_size]
            batch_meta = metadata_list[i : i + batch_size]

            # Retry up to 3 times per batch; skip individual failures
            embeddings: list[Any] = []
            for text_item in batch_texts:
                emb = None
                for attempt in range(3):
                    try:
                        emb = embedder.embed_query(text_item)
                        break
                    except Exception as exc:
                        logger.warning(
                            "embed_retry",
                            attempt=attempt + 1,
                            error=str(exc)[:100],
                        )
                        import time as _time
                        _time.sleep(1.0 * (attempt + 1))
                if emb is None:
                    logger.error("embed_skipped", text=text_item[:60])
                    failed_count += 1
                    # Use zero vector as placeholder to keep alignment
                    import numpy as np
                    emb = np.zeros(embedder.dimension, dtype=np.float32)
                embeddings.append(emb)

            if not self.config.dry_run:
                qdrant.store(
                    ids=batch_ids,
                    embeddings=embeddings,
                    metadata=batch_meta,
                )

            logger.debug(
                "batch_embedded",
                batch=i // batch_size + 1,
                size=len(batch_texts),
            )

        self.result.documents_embedded = len(texts) - failed_count
        logger.info(
            "embedding_complete",
            embedded=len(texts) - failed_count,
            failed=failed_count,
        )

    # ------------------------------------------------------------------
    # Step 4: Store in Neo4j
    # ------------------------------------------------------------------

    def _store_graph(
        self,
        entities: list[ExtractedEntity],
        relations: list[ExtractedRelation],
    ) -> None:
        """Store entities and relations in Neo4j."""
        neo4j = self._get_neo4j()

        # Convert entities → nodes
        nodes = []
        for ent in entities:
            nodes.append(Node(
                id=ent.id,
                label=ent.label,
                node_type=ent.entity_type,
                properties={
                    **ent.properties,
                    "description": ent.description,
                    "confidence": ent.confidence,
                    "graph_type": "law",
                },
            ))

        logger.info("storing_nodes", count=len(nodes))
        stored_ids = neo4j.batch_create_nodes(nodes)
        self.result.nodes_stored = len(stored_ids)

        # Convert relations → edges
        edges = []
        # Build set of known entity IDs for validation
        entity_ids = {ent.id for ent in entities}
        skipped = 0

        for rel in relations:
            # Only create edges where both endpoints exist
            if (
                rel.source_entity_id in entity_ids
                and rel.target_entity_id in entity_ids
            ):
                edges.append(Edge(
                    id=rel.id,
                    source_id=rel.source_entity_id,
                    target_id=rel.target_entity_id,
                    edge_type=rel.predicate,
                    properties={
                        **rel.properties,
                        "confidence": rel.confidence,
                    },
                ))
            else:
                skipped += 1

        if skipped:
            logger.info("edges_skipped_missing_endpoints", count=skipped)

        logger.info("storing_edges", count=len(edges))
        stored_edge_ids = neo4j.batch_create_edges(edges)
        self.result.edges_stored = len(stored_edge_ids)

        logger.info(
            "graph_stored",
            nodes=self.result.nodes_stored,
            edges=self.result.edges_stored,
        )

    # ------------------------------------------------------------------
    # Step 4b: Quality scoring
    # ------------------------------------------------------------------

    def _score_quality(self) -> None:
        """Run KG quality scoring (pySHACL + SHACL2FOL) after graph store."""
        try:
            from kgbuilder.validation.scorer import KGQualityScorer

            owl_path = self.config.ontology_path
            scorer = KGQualityScorer(
                ontology_owl_path=owl_path if owl_path.exists() else None,
                sample_limit=500,
            )
            neo4j = self._get_neo4j()
            report = scorer.score_neo4j_store(neo4j)

            logger.info(
                "quality_scoring_complete",
                combined_score=report.combined_score,
                consistency=report.consistency,
                acceptance=report.acceptance_rate,
                coverage=report.class_coverage,
                shacl=report.shacl_score,
                violations=report.violations,
            )
            self.result.quality = {
                "combined_score": report.combined_score,
                "consistency": report.consistency,
                "acceptance_rate": report.acceptance_rate,
                "class_coverage": report.class_coverage,
                "shacl_score": report.shacl_score,
                "violations": report.violations,
                "shacl_report": report.shacl_report_path,
            }
        except Exception as e:
            logger.warning("quality_scoring_failed", error=str(e))
            self.result.warnings.append(f"Quality scoring failed: {e}")

    # ------------------------------------------------------------------
    # Step 5: Export results
    # ------------------------------------------------------------------

    def _export_results(
        self,
        entities: list[ExtractedEntity],
        relations: list[ExtractedRelation],
        laws: list[LawDocument],
    ) -> None:
        """Export results to JSON files."""
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        # Export entities
        entities_file = self.config.output_dir / "law_entities.json"
        entities_data = [
            {
                "id": e.id,
                "label": e.label,
                "type": e.entity_type,
                "description": e.description,
                "properties": e.properties,
                "confidence": e.confidence,
            }
            for e in entities
        ]
        entities_file.write_text(
            json.dumps(entities_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Export relations
        relations_file = self.config.output_dir / "law_relations.json"
        relations_data = [
            {
                "id": r.id,
                "source": r.source_entity_id,
                "target": r.target_entity_id,
                "predicate": r.predicate,
                "properties": r.properties,
                "confidence": r.confidence,
            }
            for r in relations
        ]
        relations_file.write_text(
            json.dumps(relations_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Export summary
        summary_file = self.config.output_dir / "law_graph_summary.json"
        summary = {
            "timestamp": self.result.timestamp,
            "laws": [
                {
                    "abbreviation": law.abbreviation,
                    "title": law.full_title,
                    "paragraphs": len(law.paragraphs()),
                    "sections": len(law.structure_nodes()),
                    "cross_references": len(law.all_cross_references()),
                }
                for law in laws
            ],
            "totals": {
                "entities": self.result.entities_created,
                "relations": self.result.relations_created,
                "embedded": self.result.documents_embedded,
                "nodes_stored": self.result.nodes_stored,
                "edges_stored": self.result.edges_stored,
            },
            "errors": self.result.errors,
            "execution_time_seconds": self.result.execution_time_seconds,
        }
        summary_file.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        logger.info(
            "results_exported",
            output_dir=str(self.config.output_dir),
            files=["law_entities.json", "law_relations.json", "law_graph_summary.json"],
        )

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _cleanup(self) -> None:
        """Close connections."""
        if self._neo4j:
            try:
                self._neo4j.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Build a Legal Knowledge Graph from German federal law XML.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "This pipeline uses the XML structure directly — no competency\n"
            "questions or iterative discovery needed. The structured XML\n"
            "format provides deterministic entity/relation extraction.\n"
        ),
    )
    parser.add_argument(
        "--law-data",
        type=Path,
        default=None,
        help="Directory containing law XML files (default: data/law_html)",
    )
    parser.add_argument(
        "--laws",
        nargs="*",
        help="Filter to specific law abbreviations (e.g. AtG StrlSchG)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory for results (default: output/law_results)",
    )
    parser.add_argument(
        "--skip-embed",
        action="store_true",
        help="Skip Qdrant embedding step",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and extract but don't write to databases",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    args = parse_args(argv)

    # Setup logging
    setup_logging(
        log_dir=Path("/tmp"),
        log_level="DEBUG" if args.verbose else "INFO",
        enable_json=True,
    )

    # Build config
    config = LawGraphConfig(
        dry_run=args.dry_run,
        skip_embed=args.skip_embed,
    )
    if args.law_data:
        config.law_data_dir = args.law_data
    if args.output:
        config.output_dir = args.output
    if args.laws:
        config.laws = args.laws

    # Run pipeline
    pipeline = LawGraphPipeline(config)
    result = pipeline.run()

    # Print summary
    print("\n" + "=" * 70)
    print("LAW GRAPH PIPELINE COMPLETE")
    print("=" * 70)
    print(f"  Laws parsed:       {result.laws_parsed}")
    print(f"  Entities created:  {result.entities_created}")
    print(f"  Relations created: {result.relations_created}")
    print(f"  Docs embedded:     {result.documents_embedded}")
    print(f"  Nodes in Neo4j:    {result.nodes_stored}")
    print(f"  Edges in Neo4j:    {result.edges_stored}")
    print(f"  Time:              {result.execution_time_seconds:.1f}s")
    if result.quality:
        q = result.quality
        print()
        print("QUALITY (pySHACL + SHACL2FOL):")
        print(f"  Combined score:   {q.get('combined_score', 'n/a')}")
        print(f"  Consistency:      {q.get('consistency', 'n/a')}")
        print(f"  Acceptance rate:  {q.get('acceptance_rate', 'n/a')}")
        print(f"  Class coverage:   {q.get('class_coverage', 'n/a')}")
        print(f"  SHACL score:      {q.get('shacl_score', 'n/a')}")
        print(f"  Violations:       {q.get('violations', 'n/a')}")
    if result.errors:
        print(f"  Errors:            {len(result.errors)}")
        for err in result.errors:
            print(f"    - {err}")
    print("=" * 70)

    return 1 if result.errors else 0


if __name__ == "__main__":
    sys.exit(main())
