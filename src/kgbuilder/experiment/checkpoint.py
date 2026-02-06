"""Experiment checkpointing for extraction results.

Enables saving/loading discovered entities and relations to avoid
re-running expensive extraction phases.

Key Features:
- Serialize entities and relations to JSON after discovery
- Load checkpoints to skip extraction and proceed to enhancement/storage
- Preserve all metadata (confidence, evidence, question source)
- Support both eager checkpointing and lazy loading
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import structlog

from kgbuilder.core.models import ExtractedEntity, ExtractedRelation, Evidence

logger = structlog.get_logger(__name__)


@dataclass
class CheckpointMetadata:
    """Metadata for a checkpoint."""

    run_id: str
    variant_name: str
    checkpoint_time: str  # ISO format datetime
    entities_count: int
    relations_count: int
    extraction_seconds: float
    questions_processed: int


class CheckpointManager:
    """Manages saving/loading extraction checkpoints."""

    def __init__(self, checkpoint_dir: Path) -> None:
        """Initialize checkpoint manager.

        Args:
            checkpoint_dir: Directory to store checkpoints
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save_extraction(
        self,
        run_id: str,
        variant_name: str,
        entities: list[ExtractedEntity],
        relations: list[ExtractedRelation] | None = None,
        extraction_seconds: float = 0.0,
        questions_processed: int = 0,
    ) -> Path:
        """Save extraction results to checkpoint.

        Args:
            run_id: Unique run identifier
            variant_name: Configuration variant name
            entities: Extracted entities
            relations: Extracted relations (optional)
            extraction_seconds: Time spent on extraction
            questions_processed: Number of discovery questions processed

        Returns:
            Path to saved checkpoint
        """
        from datetime import datetime

        # Prepare checkpoint data
        checkpoint_data = {
            "metadata": {
                "run_id": run_id,
                "variant_name": variant_name,
                "checkpoint_time": datetime.now().isoformat(),
                "entities_count": len(entities),
                "relations_count": len(relations) if relations else 0,
                "extraction_seconds": round(extraction_seconds, 2),
                "questions_processed": questions_processed,
            },
            "entities": [self._entity_to_dict(e) for e in entities],
            "relations": [self._relation_to_dict(r) for r in (relations or [])],
        }

        # Save to JSON
        checkpoint_path = (
            self.checkpoint_dir / f"checkpoint_{run_id}_extraction.json"
        )
        with open(checkpoint_path, "w") as f:
            json.dump(checkpoint_data, f, indent=2)

        logger.info(
            "checkpoint_saved",
            path=str(checkpoint_path),
            run_id=run_id,
            entities=len(entities),
            relations=len(relations) if relations else 0,
        )

        return checkpoint_path

    def load_extraction(self, checkpoint_path: Path) -> tuple[
        list[ExtractedEntity],
        list[ExtractedRelation],
        CheckpointMetadata,
    ]:
        """Load extraction results from checkpoint.

        Args:
            checkpoint_path: Path to checkpoint file

        Returns:
            Tuple of (entities, relations, metadata)

        Raises:
            FileNotFoundError: If checkpoint doesn't exist
            json.JSONDecodeError: If checkpoint is invalid
        """
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

        with open(checkpoint_path) as f:
            data = json.load(f)

        # Parse metadata
        metadata_dict = data["metadata"]
        metadata = CheckpointMetadata(
            run_id=metadata_dict["run_id"],
            variant_name=metadata_dict["variant_name"],
            checkpoint_time=metadata_dict["checkpoint_time"],
            entities_count=metadata_dict["entities_count"],
            relations_count=metadata_dict["relations_count"],
            extraction_seconds=metadata_dict["extraction_seconds"],
            questions_processed=metadata_dict["questions_processed"],
        )

        # Parse entities
        entities = [self._dict_to_entity(e) for e in data.get("entities", [])]

        # Parse relations
        relations = [self._dict_to_relation(r) for r in data.get("relations", [])]

        logger.info(
            "checkpoint_loaded",
            checkpoint_path=str(checkpoint_path),
            entities=len(entities),
            relations=len(relations),
        )

        return entities, relations, metadata

    def list_checkpoints(self, run_id: str | None = None) -> list[Path]:
        """List available checkpoints.

        Args:
            run_id: Filter by run ID (optional)

        Returns:
            List of checkpoint paths
        """
        pattern = (
            f"checkpoint_{run_id}_extraction.json"
            if run_id
            else "checkpoint_*_extraction.json"
        )
        return sorted(self.checkpoint_dir.glob(pattern))

    def exists(self, run_id: str) -> bool:
        """Check if checkpoint exists for run.

        Args:
            run_id: Run identifier

        Returns:
            True if checkpoint exists
        """
        checkpoint_path = (
            self.checkpoint_dir / f"checkpoint_{run_id}_extraction.json"
        )
        return checkpoint_path.exists()

    @staticmethod
    def _entity_to_dict(entity: ExtractedEntity) -> dict[str, Any]:
        """Convert entity to serializable dict."""
        entity_dict = asdict(entity)
        # Convert Evidence objects to dicts
        if "evidence" in entity_dict:
            entity_dict["evidence"] = [
                asdict(e) if isinstance(e, Evidence) else e
                for e in entity_dict["evidence"]
            ]
        return entity_dict

    @staticmethod
    def _dict_to_entity(data: dict[str, Any]) -> ExtractedEntity:
        """Convert dict back to ExtractedEntity."""
        # Convert evidence dicts back to Evidence objects
        evidence_list = []
        if data.get("evidence"):
            for ev in data["evidence"]:
                if isinstance(ev, dict):
                    evidence_list.append(Evidence(**ev))
                else:
                    evidence_list.append(ev)
        data["evidence"] = evidence_list

        return ExtractedEntity(**data)

    @staticmethod
    def _relation_to_dict(relation: ExtractedRelation) -> dict[str, Any]:
        """Convert relation to serializable dict."""
        relation_dict = asdict(relation)
        # Convert Evidence objects to dicts
        if "evidence" in relation_dict:
            relation_dict["evidence"] = [
                asdict(e) if isinstance(e, Evidence) else e
                for e in relation_dict["evidence"]
            ]
        return relation_dict

    @staticmethod
    def _dict_to_relation(data: dict[str, Any]) -> ExtractedRelation:
        """Convert dict back to ExtractedRelation."""
        # Convert evidence dicts back to Evidence objects
        evidence_list = []
        if data.get("evidence"):
            for ev in data["evidence"]:
                if isinstance(ev, dict):
                    evidence_list.append(Evidence(**ev))
                else:
                    evidence_list.append(ev)
        data["evidence"] = evidence_list

        return ExtractedRelation(**data)
