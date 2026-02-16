"""Tests for PNG export and statistical report formatting."""
from __future__ import annotations

import os
import tempfile

import networkx as nx
import pytest

from kgbuilder.analytics.statistical import run_statistical_analysis, format_statistical_report
from kgbuilder.analytics.interactive_plots import save_all_interactive_plots


def test_save_all_interactive_plots_writes_html_and_optional_png(tmp_path):
    pytest.importorskip("kaleido")

    G = nx.barabasi_albert_graph(100, 2, seed=42)
    stat = run_statistical_analysis(G)

    # Build a fake StructuralAnalysis-like object with minimal fields used by saver
    class S:  # pragma: no cover - tiny test helper
        def __init__(self, topology, centralities=None, communities=None, statistical=None):
            self.topology = topology
            self.centralities = centralities or {}
            self.communities = communities or {}
            self.statistical = statistical

    # Run and request PNGs
    from kgbuilder.analytics.structural import compute_topology

    structural = S(compute_topology(G), statistical=stat)
    out = tmp_path / "plots"
    saved = save_all_interactive_plots(str(out), structural, store=None, save_pngs=True)

    # HTML outputs should exist
    assert any(str(p).endswith('.html') for p in saved.values())
    # PNG outputs present when kaleido is available
    assert any(str(p).endswith('.png') for p in saved.values())


def test_format_statistical_report_contains_key_sections():
    G = nx.barabasi_albert_graph(200, 2, seed=42)
    stat = run_statistical_analysis(G)
    md = format_statistical_report(stat)

    assert "Power‑law" in md
    assert "Community–ontology NMI" in md
    assert "Modularity" in md
    assert "Small‑world σ" in md
