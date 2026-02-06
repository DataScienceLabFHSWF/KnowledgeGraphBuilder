from __future__ import annotations

import json
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict

import structlog

from kgbuilder.storage.protocol import GraphStore, Node, Edge

logger = structlog.get_logger(__name__)

@dataclass
class VersionMetadata:
    """Metadata for a specific Knowledge Graph version."""
    version_id: str
    timestamp: str
    description: str
    node_count: int
    edge_count: int
    document_hash: Optional[str] = None
    config_hash: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    custom_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> VersionMetadata:
        return cls(**data)


@dataclass
class VersionDiff:
    """Difference between two versions of the Knowledge Graph."""
    v1_id: str
    v2_id: str
    nodes_added: List[str] = field(default_factory=list)
    nodes_removed: List[str] = field(default_factory=list)
    nodes_modified: List[str] = field(default_factory=list)
    edges_added: List[str] = field(default_factory=list)
    edges_removed: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)


class KGVersioningService:
    """Service for managing Knowledge Graph versions and snapshots.
    
    This service allows creating snapshots of the current graph state,
    listing available versions, and computing differences between them.
    It persists snapshots to disk as JSON files.
    """

    def __init__(self, storage_dir: Path) -> None:
        """Initialize the versioning service.
        
        Args:
            storage_dir: Directory where snapshots and metadata will be stored.
        """
        self.storage_dir = Path(storage_dir)
        self.snapshots_dir = self.storage_dir / "snapshots"
        self.metadata_path = self.storage_dir / "versions_metadata.json"
        
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self._versions: Dict[str, VersionMetadata] = self._load_metadata()

    def _load_metadata(self) -> Dict[str, VersionMetadata]:
        """Load versions metadata from disk."""
        if not self.metadata_path.exists():
            return {}
        
        try:
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {vid: VersionMetadata.from_dict(v) for vid, v in data.items()}
        except Exception as e:
            logger.error("failed_to_load_version_metadata", error=str(e))
            return {}

    def _save_metadata(self) -> None:
        """Save versions metadata to disk."""
        try:
            with open(self.metadata_path, "w", encoding="utf-8") as f:
                data = {vid: v.to_dict() for vid, v in self._versions.items()}
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error("failed_to_save_version_metadata", error=str(e))

    def create_snapshot(
        self, 
        store: GraphStore, 
        description: str, 
        tags: Optional[List[str]] = None,
        custom_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a snapshot of the current GraphStore state.
        
        Args:
            store: The GraphStore to snapshot.
            description: Human-readable description of this version.
            tags: Optional list of tags for categorization.
            custom_metadata: Optional dictionary of additional metadata.
            
        Returns:
            The generated unique version ID.
        """
        version_id = str(uuid.uuid4())[:8] + "_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        timestamp = datetime.now().isoformat()
        
        logger.info("creating_kg_snapshot", version_id=version_id, description=description)
        
        # Collect graph data
        nodes = list(store.get_all_nodes())
        edges = list(store.get_all_edges())
        
        snapshot_data = {
            "version_id": version_id,
            "timestamp": timestamp,
            "nodes": [n.to_dict() for n in nodes],
            "edges": [e.to_dict() for e in edges]
        }
        
        # Save snapshot file
        snapshot_path = self.snapshots_dir / f"snapshot_{version_id}.json"
        try:
            with open(snapshot_path, "w", encoding="utf-8") as f:
                json.dump(snapshot_data, f, indent=2)
        except Exception as e:
            logger.error("failed_to_save_snapshot_file", version_id=version_id, error=str(e))
            raise RuntimeError(f"Could not save snapshot file: {e}") from e

        # Create and save metadata
        metadata = VersionMetadata(
            version_id=version_id,
            timestamp=timestamp,
            description=description,
            node_count=len(nodes),
            edge_count=len(edges),
            tags=tags or [],
            custom_metadata=custom_metadata or {}
        )
        
        self._versions[version_id] = metadata
        self._save_metadata()
        
        logger.info(
            "snapshot_created", 
            version_id=version_id, 
            nodes=metadata.node_count, 
            edges=metadata.edge_count
        )
        return version_id

    def list_versions(self) -> List[VersionMetadata]:
        """List all available versions sorted by timestamp descending."""
        return sorted(
            self._versions.values(), 
            key=lambda x: x.timestamp, 
            reverse=True
        )

    def get_snapshot(self, version_id: str) -> Dict[str, Any]:
        """Load a full snapshot's data from disk.
        
        Args:
            version_id: The ID of the version to load.
            
        Returns:
            Dictionary with 'nodes' and 'edges' lists.
            
        Raises:
            ValueError: If version ID is not found.
        """
        if version_id not in self._versions:
            raise ValueError(f"Version ID {version_id} not found.")
            
        snapshot_path = self.snapshots_dir / f"snapshot_{version_id}.json"
        if not snapshot_path.exists():
            raise FileNotFoundError(f"Snapshot file for {version_id} missing.")
            
        with open(snapshot_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def diff(self, v1_id: str, v2_id: str) -> VersionDiff:
        """Compute the difference between two versions.
        
        Args:
            v1_id: ID of the base version.
            v2_id: ID of the comparison version.
            
        Returns:
            VersionDiff object containing additions and deletions.
        """
        v1 = self.get_snapshot(v1_id)
        v2 = self.get_snapshot(v2_id)
        
        v1_nodes = {n["id"] for n in v1["nodes"]}
        v2_nodes = {n["id"] for n in v2["nodes"]}
        
        v1_edges = {e["id"] for e in v1["edges"]}
        v2_edges = {e["id"] for e in v2["edges"]}
        
        diff = VersionDiff(
            v1_id=v1_id,
            v2_id=v2_id,
            nodes_added=list(v2_nodes - v1_nodes),
            nodes_removed=list(v1_nodes - v2_nodes),
            edges_added=list(v2_edges - v1_edges),
            edges_removed=list(v1_edges - v2_edges)
        )
        
        # Check for modified nodes (same ID but different properties/label)
        common_nodes = v1_nodes & v2_nodes
        v1_node_map = {n["id"]: n for n in v1["nodes"]}
        v2_node_map = {n["id"]: n for n in v2["nodes"]}
        
        for nid in common_nodes:
            if v1_node_map[nid] != v2_node_map[nid]:
                diff.nodes_modified.append(nid)
        
        diff.stats = {
            "net_node_change": len(diff.nodes_added) - len(diff.nodes_removed),
            "net_edge_change": len(diff.edges_added) - len(diff.edges_removed),
            "modified_count": len(diff.nodes_modified)
        }
        
        return diff

    def delete_version(self, version_id: str) -> bool:
        """Delete a version and its snapshot file.
        
        Args:
            version_id: The ID of the version to delete.
            
        Returns:
            True if version was found and deleted.
        """
        if version_id not in self._versions:
            return False
            
        snapshot_path = self.snapshots_dir / f"snapshot_{version_id}.json"
        if snapshot_path.exists():
            snapshot_path.unlink()
            
        del self._versions[version_id]
        self._save_metadata()
        logger.info("version_deleted", version_id=version_id)
        return True
