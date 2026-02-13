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


def pytest_collection_modifyitems(session: "pytest.Session", config: "pytest.Config", items: list["pytest.Item"]) -> None:  # type: ignore[override]
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
