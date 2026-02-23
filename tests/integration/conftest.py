"""Shared fixtures for integration tests.

This module provides higher-level fixtures that bring up lightweight
versions of external services (Neo4j, Qdrant, etc.) or prepare real
files so that tests can exercise multiple components working together.

The fixtures should favor speed and isolation – use temporary directories
and in-memory stores where possible.  As the integration suite grows,
additional helpers can be added here.
"""

from __future__ import annotations

import pytest
from pathlib import Path


@pytest.fixture

def tmp_project_dir(tmp_path: Path) -> Path:
    """A temporary workspace simulating a real project folder.

    Tests can write documents, config files, or other resources here and
    pass the path to pipeline entrypoints.
    """
    return tmp_path


# Placeholder fixtures for external services
#
# In a real test environment, these would start local Docker containers
# or use light in-memory fakes.  For now they simply return None and
# serve as documentation points.


@pytest.fixture

def fake_neo4j():
    """Return a dummy Neo4j session/driver object.

    Integration tests can monkeypatch storage.Neo4jStore to use this
    object, allowing queries without a real database.
    """
    class DummySession:
        def run(self, *args, **kwargs):
            return []

        def close(self):
            pass

    return DummySession()


@pytest.fixture

def fake_qdrant():
    """Return a minimal vector store interface for law retrieval.

    Methods should match the parts of ``storage.vector`` used by the
    pipeline (e.g. ``search``).  Tests can patch the provider to use it.
    """

    class Dummy:
        def search(self, vector, top_k=5):
            return []

    return Dummy()
