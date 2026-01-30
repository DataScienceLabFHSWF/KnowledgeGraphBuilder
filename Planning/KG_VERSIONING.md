# Knowledge Graph Versioning – Design

## Motivation
- Ensure every KG update (from new/changed documents) is tracked and reproducible
- Enable rollback, comparison, and experiment reproducibility

## Versioning Approach

### 1. Versioned Snapshots
- Each time the KG is updated (new document, batch, or periodic), export a full KG snapshot
- Store snapshots in a versioned directory, e.g.:
  - `kg_versions/v0001/graph.jsonld`
  - `kg_versions/v0002/graph.jsonld`
  - ...
- Optionally, store diffs (delta files) for space efficiency

### 2. Metadata Tracking
- Each version has a metadata file (YAML/JSON) with:
  - Version number (monotonic)
  - Timestamp
  - Trigger (e.g., document path, batch, manual)
  - List of documents included
  - Hash/checksum of KG export
  - User/agent who triggered update (if applicable)

### 3. Automated Version Bumping
- The KG builder increments the version on every update
- Optionally, allow manual version tags (e.g., `v1.0-final`)

### 4. Rollback & Comparison
- Provide CLI/API to list, diff, and restore previous KG versions
- Enable experiment runners to reference specific KG versions

### 5. Integration Points
- Versioning is triggered after successful KG update/validation
- Snapshots are stored in a dedicated `kg_versions/` directory (configurable)
- Metadata is used for provenance and experiment reproducibility

---

## Example Metadata (kg_versions/v0003/metadata.json)
```json
{
  "version": "v0003",
  "timestamp": "2026-01-30T14:23:00Z",
  "trigger": "ingest:/data/new_paper.pdf",
  "documents": ["/data/new_paper.pdf", "/data/old_paper.pdf"],
  "kg_hash": "a1b2c3d4...",
  "user": "auto-ingest"
}
```

---

## Implementation Notes
- Add a `KGVersioningService` protocol to the codebase
- All KG update operations must call this service after changes
- Store both the KG export and metadata for each version
- Optionally, support pruning old versions (configurable)

---

See also: [ARCHITECTURE.md], [INTERFACES.md] for integration points.
