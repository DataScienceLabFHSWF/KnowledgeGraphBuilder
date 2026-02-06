# Knowledge Graph Versioning Guide

This guide explains how to use the Knowledge Graph Versioning Service to track evolution, compare ablation runs, and manage snapshots.

## Overview

The `KGVersioningService` automatically creates a point-in-time snapshot of the Knowledge Graph (nodes and edges) after each successful pipeline run. Snapshots are stored in `output/versions/` as JSON files.

## Automated Versioning

The `scripts/full_kg_pipeline.py` script automatically triggers a snapshot at the end of its run. 

### CLI Options
- `--version-dir`: Override the default storage directory (`output/versions`).

## Manual Management

Use the `scripts/manage_versions.py` utility to interact with the versioning system.

### 1. List All Versions
```bash
python3 scripts/manage_versions.py list
```
Displays a table of IDs, timestamps, node/edge counts, and descriptions.

### 2. Compare Versions (Diff)
To see what changed between two runs (e.g., after increasing discovery iterations):
```bash
python3 scripts/manage_versions.py diff <v1_id> <v2_id>
```
Shows number of nodes/edges added, removed, or modified.

### 3. Delete Old Versions
```bash
python3 scripts/manage_versions.py delete <version_id>
```

## Internal Storage Structure

```
output/versions/
├── versions_metadata.json         # Master index of snapshots
└── snapshots/
    ├── snapshot_abc123_2026.json # Full graph data (nodes/edges)
    └── ...
```

## Integration with Ablation Studies

When running ablations:
1. Run baseline (Iteration 1). Note the version ID.
2. Run experimental (Iteration 2). Note the version ID.
3. Use `diff` to quantify the information gain from the additional discovery step.
