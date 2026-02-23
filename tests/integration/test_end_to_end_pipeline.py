"""A minimal end-to-end integration test exercising core pipeline pieces.

This test constructs a small document, chunks it, runs a fake extractor to
produce entities, and then passes the results through the KGBuilder using a
simple in-memory store implementation.  Its purpose is to verify that the
connectors between document, extraction and assembly layers work together.
"""

from __future__ import annotations

from pathlib import Path

from kgbuilder.assembly.kg_builder import KGBuilder, KGBuilderConfig
from kgbuilder.core.models import Document, DocumentMetadata, ExtractedEntity
from kgbuilder.document.chunking.strategies import FixedSizeChunker
from kgbuilder.storage.protocol import GraphStore, Node, QueryResult


def test_simple_document_to_kg(tmp_project_dir: Path) -> None:
    # 1. create a "document" and write it to the temp directory
    doc_path = tmp_project_dir / "doc.txt"
    doc_path.write_text("alpha beta gamma delta")

    doc = Document(
        id="doc1",
        content=doc_path.read_text(),
        source_path=doc_path,
        file_type=DocumentMetadata(file_type=None).file_type if False else None,  # not used
        metadata=DocumentMetadata(title="testdoc"),
    )

    # 2. chunk the document
    chunker = FixedSizeChunker()
    chunks = chunker.chunk(doc, chunk_size=10, chunk_overlap=2)
    assert len(chunks) > 0

    # 3. fake extractor: one entity per chunk
    entities: list[ExtractedEntity] = []
    for idx, chunk in enumerate(chunks):
        entities.append(
            ExtractedEntity(
                id=f"e{idx+1}",
                label=chunk.content.strip(),
                entity_type="TestClass",
                description="fake",
            )
        )

    # 4. convert to storage nodes
    nodes = [Node(id=e.id, node_type=e.entity_type, label=e.label) for e in entities]

    # 5. dummy GraphStore implementation
    class DummyStore(GraphStore):
        def __init__(self) -> None:
            self.nodes: list[Node] = []
            self.edges: list = []

        def add_node(self, node: Node) -> str:
            self.nodes.append(node)
            return node.id

        def add_edge(self, edge: Node) -> str:  # type: ignore[override]
            self.edges.append(edge)
            return edge.id  # type: ignore[attr-defined]

        def query(self, query: str) -> QueryResult:  # type: ignore[override]
            return QueryResult(records=[])

        def health_check(self) -> bool:  # type: ignore[override]
            return True

    store = DummyStore()
    builder = KGBuilder(store, config=KGBuilderConfig(sync_stores=False))

    result = builder.build(nodes)

    assert result.nodes_created == len(nodes)
    assert len(store.nodes) == len(nodes)
    # confirm builder recorded the correct primary store name
    assert result.primary_store == "DummyStore"
