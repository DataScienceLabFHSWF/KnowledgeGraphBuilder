"""KG versioning and snapshot management.

Provides version control for Knowledge Graphs with:
- Snapshot creation and restoration
- Version metadata tracking
- Version diffing
- Auto-versioning on pipeline runs
"""

from __future__ import annotations

from kgbuilder.versioning.service import (
    KGVersioningService,
    VersionMetadata,
    VersionDiff,
)

__all__ = [
    "KGVersioningService",
    "VersionMetadata",
    "VersionDiff",
]


__all__ = ["KGVersionMetadata"]
