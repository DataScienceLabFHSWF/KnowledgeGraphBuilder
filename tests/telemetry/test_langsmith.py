"""Unit tests for optional Langsmith tracing integration."""
from __future__ import annotations

import os
import pytest

from kgbuilder.telemetry.langsmith import get_langsmith_callbacks
from kgbuilder.extraction.chains import ExtractionChains
from kgbuilder.assembly.core import SimpleKGAssembler


@pytest.mark.parametrize("enabled", [True, False])
def test_get_langsmith_callbacks_respects_env(monkeypatch, enabled: bool) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "true" if enabled else "false")
    # Ensure missing API key does not raise — helper is defensive
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

    callbacks = get_langsmith_callbacks()

    if enabled:
        # If langsmith package isn't installed in the environment, helper returns None
        # so we accept either None or a list; primarily we assert it doesn't crash
        assert callbacks is None or isinstance(callbacks, list)
    else:
        assert callbacks is None


def test_extraction_chain_initializes_with_optional_callbacks(monkeypatch) -> None:
    # Enable tracing env; chain creation should succeed whether tracer exists or not
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

    chain = ExtractionChains.create_entity_extraction_chain()
    assert chain is not None


def test_simple_kg_assembler_initializes_with_optional_tracer(monkeypatch) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

    # Use dummy stores from tests or None for vector store
    assembler = SimpleKGAssembler(graph_store=object(), vector_store=None)
    assert assembler is not None