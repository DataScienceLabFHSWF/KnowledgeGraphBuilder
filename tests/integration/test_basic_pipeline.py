"""Simple integration test skeleton.

As the project matures, more realistic end-to-end tests should be added
here.  These tests import components from ``src/kgbuilder`` and exercise
multiple pieces together (e.g. loading a document, extracting entities,
building a graph, and running validation).

Currently this placeholder just verifies that the test harness is
working; subsequent tests can reuse fixtures defined in
``tests/integration/conftest.py``.
"""

from __future__ import annotations

import pytest


def test_placeholder(tmp_project_dir):
    # sanity check: fixture provides a path where files may be written
    assert tmp_project_dir.exists()
    assert tmp_project_dir.is_dir()

    # future tests could write a small PDF or XML and invoke the pipeline
    # processor, then assert on produced graph contents.
