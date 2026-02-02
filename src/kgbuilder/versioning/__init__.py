"""KG versioning and snapshot management.

Implementation of Planning/KG_VERSIONING.md and INTERFACES.md Section 12

TODO (KGVersioningService):
- [ ] Define KGVersioningService protocol
  - create_version() -> KGVersionMetadata
  - list_versions() -> list[KGVersionMetadata]
  - restore_version(version_id) -> None
  - diff_versions(v1, v2) -> str
  - get_version_metadata(version_id) -> KGVersionMetadata

- [ ] Implement local file-based versioning
  - Store snapshots in kg_versions/ directory
  - Use version metadata JSON files
  - Generate KG hashes (SHA256) for integrity
  - Support rollback to previous versions
  - Generate diffs between versions (optional)

- [ ] Integration with KG updates
  - Automatically create version after successful update
  - Trigger: ingest, manual, batch, etc.
  - Track which documents are in each version
  - Preserve full provenance

- [ ] Cleanup and maintenance
  - Optional pruning of old versions
  - Configurable retention policy
  - Archive old versions (optional)

- [ ] Unit tests with mock versions
- [ ] Integration tests with actual KG updates

See Planning/KG_VERSIONING.md and Planning/INTERFACES.md Section 12 for specs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class KGVersionMetadata:
    """Metadata for a KG version snapshot."""

    version: str
    timestamp: datetime
    trigger: str  # e.g., 'ingest:/data/file.pdf', 'manual'
    documents: list[str] = field(default_factory=list)
    kg_hash: str = ""
    user: str = "auto-ingest"


__all__ = ["KGVersionMetadata"]
