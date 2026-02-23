import logging
from types import SimpleNamespace

import pytest

from kgbuilder.assembly.core import (
    GraphStatistics,
    AssemblyResult,
    SimpleKGAssembler,
)


class DummyGraphStore:
    def __init__(self):
        self.nodes = []
        self.edges = []

    def add_node(self, node):
        self.nodes.append(node)

    def add_edge(self, edge):
        self.edges.append(edge)

    # methods expected by SimpleKGAssembler
    def add_entities(self, entities):
        self.nodes.extend(entities)

    def add_relations(self, relations):
        self.edges.extend(relations)

    def get_statistics(self):
        return SimpleNamespace(total_nodes=len(self.nodes), total_edges=len(self.edges))


class DummyLLM:
    def __init__(self, model=None, base_url=None, temperature=None, callbacks=None):
        self.model = model


class DummySplitter:
    def __init__(self, chunk_size, chunk_overlap, separator):
        pass


def test_statistics_and_result_dataclasses():
    stats = GraphStatistics()
    assert stats.num_nodes == 0
    assert stats.node_type_distribution is None

    res = AssemblyResult(document_id="doc1", entities_extracted=1, relations_extracted=0,
                         entities_stored=1, relations_stored=0, duplicates_removed=0,
                         processing_time_ms=10.0)
    assert res.document_id == "doc1"
    assert res.stats is None


def test_simple_assembler_initialization(monkeypatch, tmp_path):
    # patch dependencies to avoid imports
    monkeypatch.setattr("kgbuilder.assembly.core.ChatOllama", DummyLLM)
    monkeypatch.setattr("kgbuilder.assembly.core.CharacterTextSplitter", DummySplitter)
    monkeypatch.setattr("kgbuilder.telemetry.langsmith.get_langsmith_callbacks", lambda: None)

    store = DummyGraphStore()
    asm = SimpleKGAssembler(graph_store=store, vector_store=None, llm_model="m", llm_base_url="u")
    assert isinstance(asm._llm, DummyLLM)
    assert hasattr(asm, "_splitter")
    assert asm.dedup_threshold == 0.85


def test_build_extraction_pipeline_returns_chain(monkeypatch):
    # create assembler with patched extraction chains
    monkeypatch.setattr("kgbuilder.assembly.core.ExtractionChains", SimpleNamespace(
        create_entity_extraction_chain=lambda model: "entity",
        create_relation_extraction_chain=lambda model: "relation",
    ))
    monkeypatch.setattr("kgbuilder.assembly.core.ChatOllama", DummyLLM)
    monkeypatch.setattr("kgbuilder.assembly.core.CharacterTextSplitter", DummySplitter)
    monkeypatch.setattr("kgbuilder.telemetry.langsmith.get_langsmith_callbacks", lambda: None)

    asm = SimpleKGAssembler(graph_store=DummyGraphStore())
    result = asm.build_extraction_pipeline()
    assert result == "entity"


def test_assemble_logs(monkeypatch, caplog):
    monkeypatch.setattr("kgbuilder.assembly.core.ChatOllama", DummyLLM)
    monkeypatch.setattr("kgbuilder.assembly.core.CharacterTextSplitter", DummySplitter)
    monkeypatch.setattr("kgbuilder.telemetry.langsmith.get_langsmith_callbacks", lambda: None)

    store = DummyGraphStore()
    asm = SimpleKGAssembler(graph_store=store)
    caplog.set_level(logging.INFO)
    asm.assemble(entities=[], relations=[])
    assert "Assembling KG" in caplog.text
