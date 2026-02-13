"""Convert KG construction operations to SHACL2FOL update actions.

SHACL2FOL expects graph updates as a JSON array of *actions* that describe
which shapes are instantiated.  Two action types exist:

- **ShapeAction**: ``{ "type": "ShapeAction", "subjectShape": "...",
  "objectShape": "..." }`` — asserts that a node matching ``subjectShape``
  is connected to a node matching ``objectShape``.
- **PathAction**: ``{ "type": "PathAction", "path": "..." }`` — asserts
  that a specific property path is instantiated.

This module translates extracted entities and relations from the KG
construction pipeline into these action objects so that
``StaticValidator.validate_static()`` can check them *before* they are
written to the graph store.

Usage:
    >>> from kgbuilder.validation.action_converter import ActionConverter
    >>> converter = ActionConverter(shapes_namespace="https://purl.org/ai4s/shapes/")
    >>> actions = converter.from_entities_and_relations(entities, relations)
    >>> converter.write_json(actions, Path("actions.json"))

References:
    - https://github.com/paolo7/SHACL2FOL (``runnable/health_actions.json``)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Action data models
# ---------------------------------------------------------------------------

@dataclass
class ShapeAction:
    """A SHACL2FOL ShapeAction: connects two shape-typed nodes.

    Attributes:
        subject_shape: URI of the SHACL shape for the subject node.
        object_shape: URI of the SHACL shape for the object node.
    """

    subject_shape: str
    object_shape: str

    def to_dict(self) -> dict[str, str]:
        """Serialize to SHACL2FOL JSON format."""
        return {
            "type": "ShapeAction",
            "subjectShape": self.subject_shape,
            "objectShape": self.object_shape,
        }


@dataclass
class PathAction:
    """A SHACL2FOL PathAction: instantiates a property path.

    Attributes:
        path: URI of the property path being added.
    """

    path: str

    def to_dict(self) -> dict[str, str]:
        """Serialize to SHACL2FOL JSON format."""
        return {"type": "PathAction", "path": self.path}


@dataclass
class ActionSet:
    """Collection of SHACL2FOL actions for a batch of updates.

    Attributes:
        shape_actions: List of ShapeAction objects.
        path_actions: List of PathAction objects.
        metadata: Optional metadata about the conversion.
    """

    shape_actions: list[ShapeAction] = field(default_factory=list)
    path_actions: list[PathAction] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json_list(self) -> list[dict[str, str]]:
        """Serialize all actions to SHACL2FOL JSON array format."""
        actions: list[dict[str, str]] = []
        actions.extend(a.to_dict() for a in self.shape_actions)
        actions.extend(a.to_dict() for a in self.path_actions)
        return actions

    @property
    def total_actions(self) -> int:
        """Total number of actions in this set."""
        return len(self.shape_actions) + len(self.path_actions)


# ---------------------------------------------------------------------------
# Converter
# ---------------------------------------------------------------------------

class ActionConverter:
    """Convert pipeline entities/relations to SHACL2FOL actions.

    Maps:
    - Entity with ``entity_type`` → ``ShapeAction`` referencing the
      corresponding SHACL NodeShape.
    - Relation with ``relation_type`` → ``PathAction`` referencing the
      property path, plus a ``ShapeAction`` linking source/target shapes.

    Attributes:
        shapes_namespace: URI prefix for SHACL shape references.
        ontology_namespace: URI prefix for ontology property references.
    """

    def __init__(
        self,
        shapes_namespace: str = "https://purl.org/ai4s/shapes/",
        ontology_namespace: str = "https://purl.org/ai4s/ontology/planning#",
    ) -> None:
        """Initialize the action converter.

        Args:
            shapes_namespace: Namespace for generated shape URIs.
            ontology_namespace: Namespace for ontology property URIs.
        """
        self._shapes_ns = shapes_namespace
        self._ont_ns = ontology_namespace

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def from_entities(self, entities: list[Any]) -> ActionSet:
        """Convert extracted entities to SHACL2FOL actions.

        Each entity type maps to a ``ShapeAction`` asserting the node
        conforms to the corresponding NodeShape.
        """
        action_set = ActionSet()
        for ent in entities:
            # Expect attribute `entity_type` on entity model
            ent_type = getattr(ent, "entity_type", None) or getattr(ent, "type", None)
            if not ent_type:
                continue
            shape_uri = f"{self._shapes_ns}{ent_type}Shape"
            action_set.shape_actions.append(ShapeAction(subject_shape=shape_uri, object_shape=shape_uri))
        action_set.metadata["generated_from"] = "entities"
        return action_set

    def from_relations(self, relations: list[Any]) -> ActionSet:
        """Convert extracted relations to SHACL2FOL actions.

        Each relation maps to a ``PathAction`` for the predicate path and a
        ``ShapeAction`` linking the source/target node shapes when type info
        is available.
        """
        action_set = ActionSet()
        for rel in relations:
            rel_type = getattr(rel, "relation_type", None) or getattr(rel, "predicate", None) or getattr(rel, "type", None)
            if rel_type:
                path_uri = f"{self._ont_ns}{rel_type}"
                action_set.path_actions.append(PathAction(path=path_uri))
            # Try to link shapes if source/target types are present
            src_type = getattr(rel, "source_type", None) or getattr(rel, "source_class", None)
            tgt_type = getattr(rel, "target_type", None) or getattr(rel, "target_class", None)
            if src_type and tgt_type:
                subj_shape = f"{self._shapes_ns}{src_type}Shape"
                obj_shape = f"{self._shapes_ns}{tgt_type}Shape"
                action_set.shape_actions.append(ShapeAction(subject_shape=subj_shape, object_shape=obj_shape))
        action_set.metadata["generated_from"] = "relations"
        return action_set

    def from_entities_and_relations(
        self,
        entities: list[Any],
        relations: list[Any],
    ) -> ActionSet:
        """Convert both entities and relations into a combined ActionSet."""
        entities_set = self.from_entities(entities)
        relations_set = self.from_relations(relations)
        merged = ActionSet(
            shape_actions=entities_set.shape_actions + relations_set.shape_actions,
            path_actions=entities_set.path_actions + relations_set.path_actions,
            metadata={"merged_from": [entities_set.metadata.get("generated_from"), relations_set.metadata.get("generated_from")]},
        )
        return merged

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    def write_json(self, action_set: ActionSet, path: Path) -> Path:
        """Write an ActionSet to a SHACL2FOL-compatible JSON file.

        Args:
            action_set: Actions to serialize.
            path: Output file path.

        Returns:
            Path to the written file.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(action_set.to_json_list(), f, indent=2)

        logger.info(
            "actions_written",
            path=str(path),
            total_actions=action_set.total_actions,
        )
        return path

    @staticmethod
    def read_json(path: Path) -> list[dict[str, str]]:
        """Read a SHACL2FOL actions JSON file.

        Args:
            path: Path to JSON file.

        Returns:
            List of action dicts.
        """
        with open(path) as f:
            return json.load(f)
