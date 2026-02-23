"""Pytest collection safeguards for this repository.

This module enforces uniqueness of test file basenames to avoid the
`import file mismatch` collection error that occurs when two test files
share the same filename in different directories.

Behavior:
- During collection, if two or more distinct paths share the same
  basename (e.g. `test_foo.py`), pytest will be stopped with a
  clear error message listing the conflicting files.

Rationale: catching this at collection time prevents subtle test-suite
failures and CI flakiness.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import warnings


def pytest_configure(config: pytest.Config) -> None:
    """Configure global warning filters to keep test output clean.

    Many third-party dependencies emit deprecation or runtime warnings
    during our unit tests (e.g. powerlaw, torch_geometric, plotly).
    We suppress those messages here rather than updating each test
    individually.
    """
    # ignore noisy powerlaw warnings (user/runtime/optimize)
    warnings.filterwarnings(
        "ignore",
        category=UserWarning,
        module=r"powerlaw\..*",
    )
    warnings.filterwarnings(
        "ignore",
        category=RuntimeWarning,
        module=r"powerlaw\..*",
    )
    warnings.filterwarnings(
        "ignore",
        category=ImportWarning,
        module=r"powerlaw\..*",
    )
    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
        message=r".*torch\.jit\.script.*",
    )
    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
        module=r"torch_geometric\..*",
    )
    # also ignore any generic torch deprecation
    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
        module=r"torch\..*",
    )
    # plotly deprecation messages
    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
        module=r"plotly\..*",
    )
    # networkx runtime warnings
    warnings.filterwarnings(
        "ignore",
        category=RuntimeWarning,
        module=r"networkx\..*",
    )
    # catch-anyother misc deprecations from powerlaw
    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
        module=r"powerlaw\..*",
    )


def pytest_collection_modifyitems(session: pytest.Session, config: pytest.Config, items: list[pytest.Item]) -> None:  # type: ignore[override]
    """Fail fast when multiple test files share the same basename.

    Pytest's import system can import a module from the first matching
    path and later attempt to import a different file with the same
    module name, causing an ``import file mismatch`` error during
    collection.  This hook detects that situation earlier and surfaces
    a helpful error message.
    """
    basenames: dict[str, set[str]] = {}
    for item in items:
        # item.fspath is a py.path.local or str — normalize to Path
        p = Path(str(item.fspath)).name
        basenames.setdefault(p, set()).add(str(item.fspath))

    duplicates = {b: paths for b, paths in basenames.items() if len(paths) > 1}
    if duplicates:
        lines = [
            "Duplicate test file basenames detected — please rename one of the files:",
        ]
        for name, paths in sorted(duplicates.items()):
            lines.append(f"- {name}: {', '.join(sorted(paths))}")
        raise pytest.UsageError("\n".join(lines))
