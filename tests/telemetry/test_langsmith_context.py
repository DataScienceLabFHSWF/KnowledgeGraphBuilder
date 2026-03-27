"""Tests ensuring the tracing_context helper behaves correctly."""
from __future__ import annotations

import sys
import pytest

from kgbuilder.telemetry.langsmith import tracing_context, get_langsmith_callbacks


class DummyCtx:
    def __init__(self):
        self.entered = False

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_context_disabled(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    cm = tracing_context(metadata={"foo": "bar"})
    with cm:
        pass
    assert cm.__class__.__name__ == "nullcontext"


def test_context_with_langsmith(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    fake = type("F", (), {"tracing_context": lambda self, **kw: DummyCtx()})()
    monkeypatch.setitem(sys.modules, "langsmith", fake)
    cm = tracing_context(metadata={"foo": "bar"})
    with cm as ctx:
        assert isinstance(ctx, DummyCtx)
    assert ctx.entered
