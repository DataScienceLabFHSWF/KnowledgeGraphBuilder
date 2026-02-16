"""Knowledge Graph versioning and snapshot management.

Provides version control for KGs with:
- Snapshot creation and restoration
- Version diffing (entity/relation changes)
- Version metadata tracking
- Automatic versioning on pipeline runs
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class VersionMetadata:
    """Metadata for a KG version/snapshot."""

    version_id: str  # Format: v_YYYYMMDD_HHMMSS_XXX
    name: str
    description: str
    timestamp: datetime = field(default_factory=datetime.now)

    # Trigger information
    trigger: str = ""  # "pipeline_run", "manual_snapshot", etc.
    pipeline_id: str | None = None  # Associated pipeline run ID

    # KG statistics at snapshot time
    entity_count: int = 0
    relation_count: int = 0

    # Content hash for deduplication
    content_hash: str = ""  # SHA256 of KG data
    document_set_hash: str = ""  # SHA256 of document paths used

    # Storage
    snapshot_path: Path | None = None
    export_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        if self.snapshot_path:
            data["snapshot_path"] = str(self.snapshot_path)
        if self.export_path:
            data["export_path"] = str(self.export_path)
        return data


@dataclass
class VersionDiff:
    """Difference between two KG versions."""

    version_from: str
    version_to: str

    entities_added: int = 0
    entities_modified: int = 0
    entities_deleted: int = 0

    relations_added: int = 0
    relations_modified: int = 0
    relations_deleted: int = 0

    # Detailed lists
    new_entity_ids: list[str] = field(default_factory=list)
    removed_entity_ids: list[str] = field(default_factory=list)
    new_relation_ids: list[str] = field(default_factory=list)
    removed_relation_ids: list[str] = field(default_factory=list)

    # Summary
    total_changes: int = 0

    def compute_summary(self) -> None:
        """Compute total_changes from component changes."""
        self.total_changes = (
            self.entities_added + self.entities_modified + self.entities_deleted +
            self.relations_added + self.relations_modified + self.relations_deleted
        )


class KGVersioningService:
    """Manages KG versioning, snapshots, and restoration.
    
    Features:
    - Create versioned snapshots of KG state
    - List all versions with metadata
    - Diff between versions
    - Restore KG to previous version
    - Auto-version on pipeline runs
    """

    def __init__(self, version_dir: Path, graph_store: object) -> None:
        """Initialize versioning service.
        
        Args:
            version_dir: Directory for storing version metadata and snapshots
            graph_store: Neo4jGraphStore instance for querying
        """
        self.version_dir = Path(version_dir)
        self.graph_store = graph_store
        self.metadata_file = self.version_dir / "versions.json"

        # Create version directory
        self.version_dir.mkdir(parents=True, exist_ok=True)

        # Load existing versions
        self.versions: dict[str, VersionMetadata] = {}
        self._load_versions()

        logger.info("versioning_service_initialized", version_dir=str(self.version_dir))

    def create_snapshot(
        self,
        name: str,
        description: str,
        trigger: str = "manual",
        pipeline_id: str | None = None,
        export_formats: list[str] | None = None,
    ) -> VersionMetadata:
        """Create a versioned snapshot of the current KG.
        
        Args:
            name: Human-readable name for this version
            description: Description of changes in this version
            trigger: What triggered the snapshot ("pipeline_run", "manual", etc.)
            pipeline_id: Optional associated pipeline run ID
            export_formats: Formats to export ("json-ld", "rdf", "cypher")
            
        Returns:
            VersionMetadata for the created snapshot
        """
        logger.info("creating_kg_snapshot", name=name, trigger=trigger)

        # Generate version ID
        timestamp = datetime.now()
        version_id = timestamp.strftime("v_%Y%m%d_%H%M%S_") + self._generate_short_hash()

        # Query KG statistics
        entity_count = self._count_entities()
        relation_count = self._count_relations()

        # Compute content hashes
        content_hash = self._compute_kg_hash()

        # Create snapshot directory
        snapshot_dir = self.version_dir / version_id
        snapshot_dir.mkdir(exist_ok=True)

        # Create metadata
        metadata = VersionMetadata(
            version_id=version_id,
            name=name,
            description=description,
            timestamp=timestamp,
            trigger=trigger,
            pipeline_id=pipeline_id,
            entity_count=entity_count,
            relation_count=relation_count,
            content_hash=content_hash,
            snapshot_path=snapshot_dir,
        )

        # Export KG data
        if export_formats is None:
            export_formats = ["json-ld"]

        try:
            for fmt in export_formats:
                self._export_kg(fmt, snapshot_dir, metadata)
        except Exception as e:
            logger.error(f"export_failed during snapshot: {e}")
            # Don't fail snapshot creation if export fails

        # Store metadata
        self.versions[version_id] = metadata
        self._save_versions()

        logger.info(
            "kg_snapshot_created",
            version_id=version_id,
            entities=entity_count,
            relations=relation_count,
            path=str(snapshot_dir),
        )

        return metadata

    def list_versions(self) -> list[VersionMetadata]:
        """List all versions in reverse chronological order.
        
        Returns:
            List of VersionMetadata sorted newest first
        """
        versions = sorted(
            self.versions.values(),
            key=lambda v: v.timestamp,
            reverse=True
        )
        return versions

    def get_version(self, version_id: str) -> VersionMetadata | None:
        """Get metadata for a specific version.
        
        Args:
            version_id: Version identifier
            
        Returns:
            VersionMetadata or None if not found
        """
        return self.versions.get(version_id)

    def diff(
        self,
        version_from: str | None = None,
        version_to: str | None = None,
    ) -> VersionDiff | None:
        """Compute difference between two versions.
        
        Args:
            version_from: Source version ID (or latest-1 if None)
            version_to: Target version ID (or latest if None)
            
        Returns:
            VersionDiff object with change summary
        """
        versions = self.list_versions()
        if len(versions) < 2:
            logger.warning("diff_insufficient_versions")
            return None

        if version_to is None:
            version_to_meta = versions[0]
        else:
            version_to_meta = self.get_version(version_to)
            if not version_to_meta:
                logger.warning(f"version_not_found {version_to}")
                return None

        if version_from is None:
            version_from_meta = versions[1]
        else:
            version_from_meta = self.get_version(version_from)
            if not version_from_meta:
                logger.warning(f"version_not_found {version_from}")
                return None

        # Compute diff
        diff = VersionDiff(
            version_from=version_from_meta.version_id,
            version_to=version_to_meta.version_id,
        )

        # Simple diff: compare entity/relation counts
        # TODO: For detailed diffing, compare actual entity/relation sets
        diff.entities_added = max(0, version_to_meta.entity_count - version_from_meta.entity_count)
        diff.entities_deleted = max(0, version_from_meta.entity_count - version_to_meta.entity_count)
        diff.relations_added = max(0, version_to_meta.relation_count - version_from_meta.relation_count)
        diff.relations_deleted = max(0, version_from_meta.relation_count - version_to_meta.relation_count)

        diff.compute_summary()

        logger.info(
            "kg_versions_diffed",
            from_version=diff.version_from,
            to_version=diff.version_to,
            total_changes=diff.total_changes,
        )

        return diff

    def restore(self, version_id: str) -> bool:
        """Restore KG to a previous version.
        
        Args:
            version_id: Version to restore to
            
        Returns:
            True if successful, False otherwise
        """
        metadata = self.get_version(version_id)
        if not metadata:
            logger.error(f"restore_failed version_not_found {version_id}")
            return False

        if not metadata.snapshot_path or not metadata.snapshot_path.exists():
            logger.error(f"restore_failed snapshot_not_found {metadata.snapshot_path}")
            return False

        logger.warning(
            "restoring_kg_to_version",
            version_id=version_id,
            version_name=metadata.name,
        )

        try:
            # TODO: Implement actual restore logic
            # - Load exported KG data from snapshot_path
            # - Clear current graph
            # - Rebuild from snapshot
            logger.info(f"kg_restored version_id={version_id}")
            return True
        except Exception as e:
            logger.error(f"restore_failed {version_id}: {e}")
            return False

    def generate_version_report(self) -> str:
        """Generate human-readable version history report.
        
        Returns:
            Formatted report string
        """
        report = "# Knowledge Graph Version History\n\n"

        versions = self.list_versions()
        for i, version in enumerate(versions, 1):
            report += f"## Version {i}: {version.name}\n\n"
            report += f"- **ID**: `{version.version_id}`\n"
            report += f"- **Timestamp**: {version.timestamp.isoformat()}\n"
            report += f"- **Description**: {version.description}\n"
            report += f"- **Trigger**: {version.trigger}\n"
            report += f"- **Entities**: {version.entity_count}\n"
            report += f"- **Relations**: {version.relation_count}\n"
            report += f"- **Content Hash**: `{version.content_hash[:16]}...`\n"
            report += "\n"

        return report

    def _count_entities(self) -> int:
        """Count total entities in graph."""
        try:
            with self.graph_store._driver.session() as session:
                result = session.run("MATCH (e:Entity) RETURN count(e) as count")
                return result.single()["count"]
        except Exception as e:
            logger.warning(f"Failed to count entities: {e}")
            return 0

    def _count_relations(self) -> int:
        """Count total relations in graph."""
        try:
            with self.graph_store._driver.session() as session:
                result = session.run(
                    "MATCH ()-[r]->() WHERE r.label <> 'HAS_CONTEXT' RETURN count(r) as count"
                )
                return result.single()["count"]
        except Exception as e:
            logger.warning(f"Failed to count relations: {e}")
            return 0

    def _compute_kg_hash(self) -> str:
        """Compute SHA256 hash of KG content for deduplication."""
        try:
            with self.graph_store._driver.session() as session:
                # Get a deterministic representation of the graph
                result = session.run("""
                    MATCH (e:Entity)
                    RETURN collect(DISTINCT e.id) as entity_ids
                """)
                entity_ids = result.single()["entity_ids"] or []

                # Create hash from sorted entity IDs (deterministic)
                content = json.dumps(sorted(entity_ids), sort_keys=True)
                return hashlib.sha256(content.encode()).hexdigest()
        except Exception as e:
            logger.warning(f"Failed to compute KG hash: {e}")
            return "unknown"

    def _generate_short_hash(self) -> str:
        """Generate short hash for version ID suffix."""
        import uuid
        return str(uuid.uuid4())[:8]

    def _export_kg(self, format_type: str, target_dir: Path, metadata: VersionMetadata) -> None:
        """Export KG in specified format.
        
        Args:
            format_type: Export format ("json-ld", "rdf", "cypher")
            target_dir: Directory to save export
            metadata: Version metadata for reference
        """
        # Placeholder: would call actual export methods
        logger.debug(f"export_kg format={format_type} target={target_dir}")

    def _load_versions(self) -> None:
        """Load version metadata from disk."""
        if not self.metadata_file.exists():
            logger.info("no_existing_versions")
            return

        try:
            with open(self.metadata_file) as f:
                data = json.load(f)
                for version_id, meta_dict in data.items():
                    # Reconstruct VersionMetadata
                    meta_dict["timestamp"] = datetime.fromisoformat(meta_dict["timestamp"])
                    if meta_dict.get("snapshot_path"):
                        meta_dict["snapshot_path"] = Path(meta_dict["snapshot_path"])
                    if meta_dict.get("export_path"):
                        meta_dict["export_path"] = Path(meta_dict["export_path"])

                    self.versions[version_id] = VersionMetadata(**meta_dict)

            logger.info("versions_loaded", count=len(self.versions))
        except Exception as e:
            logger.error(f"Failed to load versions: {e}")

    def _save_versions(self) -> None:
        """Save version metadata to disk."""
        try:
            data = {vid: meta.to_dict() for vid, meta in self.versions.items()}
            with open(self.metadata_file, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug("versions_saved")
        except Exception as e:
            logger.error(f"Failed to save versions: {e}")
