"""Law Graph Retrieval Service.

Provides retrieval of relevant legal context from the law graph
to augment entity extraction in the decommissioning KG pipeline.

Uses both vector similarity (Qdrant) and structural graph queries (Neo4j)
to find relevant paragraphs, obligations, and cross-references.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class LawContext:
    """A piece of legal context retrieved from the law graph."""

    paragraph_id: str
    law_abbreviation: str
    paragraph_number: str
    title: str
    text: str
    score: float = 0.0
    cross_references: list[str] = field(default_factory=list)


@dataclass
class LawGraphRetriever:
    """Retrieves relevant legal context from the law graph.

    Combines vector similarity search (Qdrant lawgraph collection)
    with structural Neo4j queries to provide rich legal context
    for entity extraction.

    Args:
        neo4j_store: Neo4j graph store instance
        qdrant_store: Qdrant vector store for lawgraph collection
        embedding_provider: Embedding provider for query vectorization
        max_results: Maximum number of law paragraphs to return
    """

    neo4j_store: Any  # Neo4jGraphStore
    qdrant_store: Any  # QdrantStore (lawgraph collection)
    embedding_provider: Any  # OllamaProvider
    max_results: int = 5

    def retrieve_for_text(self, text: str) -> list[LawContext]:
        """Retrieve relevant law paragraphs for a given text.

        Uses vector similarity search over the lawgraph Qdrant collection
        to find paragraphs semantically related to the input text.

        Args:
            text: Source text (e.g., a decommissioning document chunk)

        Returns:
            List of relevant LawContext objects, ranked by relevance
        """
        if not text or not text.strip():
            return []

        try:
            query_vec = self.embedding_provider.embed_text(text[:2000])
            results = self.qdrant_store.search(query_vec, top_k=self.max_results)

            contexts = []
            for rid, score, meta in results:
                ctx = LawContext(
                    paragraph_id=str(rid),
                    law_abbreviation=meta.get("law", ""),
                    paragraph_number=meta.get("paragraph", ""),
                    title=meta.get("title", ""),
                    text=meta.get("text", ""),
                    score=score,
                )
                contexts.append(ctx)

            if contexts:
                logger.debug(
                    "law_context_retrieved",
                    count=len(contexts),
                    top_score=contexts[0].score if contexts else 0,
                    top_law=contexts[0].law_abbreviation if contexts else "",
                )

            return contexts

        except Exception as e:
            logger.warning("law_retrieval_failed", error=str(e))
            return []

    def retrieve_for_entity(self, entity_label: str) -> list[LawContext]:
        """Retrieve law paragraphs mentioning a specific entity.

        Uses Neo4j full-text search on law graph nodes to find
        paragraphs that reference a given entity label.

        Args:
            entity_label: Entity label to search for (e.g., "Kernbrennstoff")

        Returns:
            List of relevant LawContext objects
        """
        if not entity_label:
            return []

        try:
            query = """
            MATCH (p:Paragraf)
            WHERE p.properties CONTAINS $label
            RETURN p.id AS id, p.label AS label, p.properties AS properties
            LIMIT $limit
            """
            result = self.neo4j_store.query(
                query, {"label": entity_label, "limit": self.max_results}
            )

            import json as _json

            contexts = []
            for record in result.records:
                props = _json.loads(record.get("properties") or "{}")
                label_val = record.get("label") or ""
                law_abbr = props.get("law_abbreviation", "")
                if not law_abbr:
                    law_abbr = label_val.split(" ", 1)[0] if label_val else ""

                ctx = LawContext(
                    paragraph_id=record.get("id", ""),
                    law_abbreviation=law_abbr,
                    paragraph_number=props.get("enbez", ""),
                    title=props.get("title", ""),
                    text=props.get("description", "")[:500],
                    score=1.0,
                )
                contexts.append(ctx)

            return contexts

        except Exception as e:
            logger.warning("law_entity_retrieval_failed", error=str(e))
            return []

    def retrieve_cross_references(self, paragraph_id: str) -> list[LawContext]:
        """Retrieve paragraphs cross-referenced from a given paragraph.

        Follows REFERENZIERT edges in Neo4j to find related paragraphs.

        Args:
            paragraph_id: Source paragraph node ID

        Returns:
            List of cross-referenced LawContext objects
        """
        try:
            query = """
            MATCH (source)-[:REFERENZIERT]->(target:Paragraf)
            WHERE source.id = $pid
            RETURN target.id AS id, target.label AS label,
                   target.properties AS properties
            LIMIT $limit
            """
            result = self.neo4j_store.query(
                query, {"pid": paragraph_id, "limit": self.max_results}
            )

            import json as _json

            contexts = []
            for record in result.records:
                props = _json.loads(record.get("properties") or "{}")
                label_val = record.get("label") or ""
                law_abbr = props.get("law_abbreviation", "")
                if not law_abbr:
                    law_abbr = label_val.split(" ", 1)[0] if label_val else ""

                ctx = LawContext(
                    paragraph_id=record.get("id", ""),
                    law_abbreviation=law_abbr,
                    paragraph_number=props.get("enbez", ""),
                    title=props.get("title", ""),
                    text=props.get("description", "")[:500],
                    score=0.8,
                )
                contexts.append(ctx)

            return contexts

        except Exception as e:
            logger.warning("xref_retrieval_failed", error=str(e))
            return []

    def format_as_prompt_context(self, contexts: list[LawContext]) -> str:
        """Format law contexts into a string suitable for LLM prompt injection.

        Args:
            contexts: List of LawContext objects

        Returns:
            Formatted string for prompt inclusion
        """
        if not contexts:
            return ""

        lines = ["RELEVANT LEGAL CONTEXT (from German federal law):"]
        for ctx in contexts:
            header = f"[{ctx.law_abbreviation} {ctx.paragraph_number}]"
            if ctx.title:
                header += f" {ctx.title}"
            lines.append(f"\n{header}")
            if ctx.text:
                lines.append(ctx.text[:400])

        return "\n".join(lines)
