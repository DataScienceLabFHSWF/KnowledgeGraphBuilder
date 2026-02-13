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
        operation: 'add'|'remove'|'update' describing the intended update.
    """

    subject_shape: str
    object_shape: str
    operation: str = "add"

    def to_dict(self) -> dict[str, str]:
        """Serialize to SHACL2FOL JSON format."""
        d = {
            "type": "ShapeAction",
            "subjectShape": self.subject_shape,
            "objectShape": self.object_shape,
        }
        if self.operation and self.operation != "add":
            d["operation"] = self.operation
        return d


@dataclass
class PathAction:
    """A SHACL2FOL PathAction: instantiates a property path.

    Attributes:
        path: URI of the property path being added.
        operation: 'add'|'remove'|'update' describing the intended update.
    """

    path: str
    operation: str = "add"

    def to_dict(self) -> dict[str, str]:
        """Serialize to SHACL2FOL JSON format."""
        d = {"type": "PathAction", "path": self.path}
        if self.operation and self.operation != "add":
            d["operation"] = self.operation
        return d


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
        """Serialize all actions to SHACL2FOL JSON array format.

        When this ActionSet represents an "update" (merged remove+add) we
        explicitly include the `operation` field for *all* actions so the
        serialized form unambiguously conveys both the `remove` and `add`
        semantics (the individual action serializers omit `operation` for
        the common `add` case).
        """
        actions: list[dict[str, str]] = []

        # Build paired (obj, dict) so we can inject operation when this
        # ActionSet encodes an `update` (remove+add) and callers expect both
        # semantics to appear in the JSON representation.
        for a in self.shape_actions:
            d = a.to_dict()
            if self.metadata.get("operation") == "update" and "operation" not in d:
                d["operation"] = a.operation
            actions.append(d)

        for a in self.path_actions:
            d = a.to_dict()
            if self.metadata.get("operation") == "update" and "operation" not in d:
                d["operation"] = a.operation
            actions.append(d)

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
        ontology_service: Any | None = None,
    ) -> None:
        """Initialize the action converter.

        Args:
            shapes_namespace: Namespace for generated shape URIs.
            ontology_namespace: Namespace for ontology property URIs.
            ontology_service: Optional ontology backend used to expand inverse/property metadata.
        """
        self._shapes_ns = shapes_namespace
        self._ont_ns = ontology_namespace
        self._ontology_service = ontology_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def from_entities(self, entities: list[Any], operation: str = "add") -> ActionSet:
        """Convert extracted entities to SHACL2FOL actions.

        Each entity type maps to a ``ShapeAction`` asserting the node
        conforms to the corresponding NodeShape.

        Args:
            entities: List of entity-like objects with `entity_type`.
            operation: One of 'add', 'remove', or 'update' describing the
                intended update operation (defaults to 'add').
        """
        if operation == "update":
            # update -> emit remove + add
            remove_set = self.from_entities(entities, operation="remove")
            add_set = self.from_entities(entities, operation="add")
            merged = ActionSet(
                shape_actions=remove_set.shape_actions + add_set.shape_actions,
                path_actions=remove_set.path_actions + add_set.path_actions,
                metadata={"merged_from": [remove_set.metadata.get("generated_from"), add_set.metadata.get("generated_from")], "operation": "update"},
            )
            return merged

        action_set = ActionSet()
        for ent in entities:
            # Expect attribute `entity_type` on entity model
            ent_type = getattr(ent, "entity_type", None) or getattr(ent, "type", None)
            if not ent_type:
                continue
            shape_uri = f"{self._shapes_ns}{ent_type}Shape"
            action_set.shape_actions.append(ShapeAction(subject_shape=shape_uri, object_shape=shape_uri, operation=operation))
        action_set.metadata["generated_from"] = "entities"
        action_set.metadata["operation"] = operation
        return action_set

    def from_relations(self, relations: list[Any], operation: str = "add") -> ActionSet:
        """Convert extracted relations to SHACL2FOL actions.

        Each relation maps to a ``PathAction`` for the predicate path and a
        ``ShapeAction`` linking the source/target shapes when type info is
        available.

        Args:
            relations: List of relation-like objects.
            operation: One of 'add', 'remove', or 'update' describing the
                intended update operation (defaults to 'add').
        """
        if operation == "update":
            # Emit remove + add for relations
            remove_set = self.from_relations(relations, operation="remove")
            add_set = self.from_relations(relations, operation="add")
            merged = ActionSet(
                shape_actions=remove_set.shape_actions + add_set.shape_actions,
                path_actions=remove_set.path_actions + add_set.path_actions,
                metadata={"merged_from": [remove_set.metadata.get("generated_from"), add_set.metadata.get("generated_from")], "operation": "update"},
            )
            return merged

        action_set = ActionSet()
        for rel in relations:
            rel_type = getattr(rel, "relation_type", None) or getattr(rel, "predicate", None) or getattr(rel, "type", None)
            if rel_type:
                path_uri = f"{self._ont_ns}{rel_type}"
                action_set.path_actions.append(PathAction(path=path_uri, operation=operation))

                # Expand inverse actions when ontology provides inverse declarations
                try:
                    if self._ontology_service:
                        special = self._ontology_service.get_special_properties() or {}
                        for inv in special.get("inverse", []) or []:
                            if isinstance(inv, tuple) and len(inv) == 2:
                                a, b = inv
                                if rel_type == a:
                                    inv_path = f"{self._ont_ns}{b}"
                                    action_set.path_actions.append(PathAction(path=inv_path, operation=operation))
                                elif rel_type == b:
                                    inv_path = f"{self._ont_ns}{a}"
                                    action_set.path_actions.append(PathAction(path=inv_path, operation=operation))
                except Exception:
                    pass

            # Try to link shapes if source/target types are present
            src_type = getattr(rel, "source_type", None) or getattr(rel, "source_class", None)
            tgt_type = getattr(rel, "target_type", None) or getattr(rel, "target_class", None)
            if src_type and tgt_type:
                subj_shape = f"{self._shapes_ns}{src_type}Shape"
                obj_shape = f"{self._shapes_ns}{tgt_type}Shape"
                action_set.shape_actions.append(ShapeAction(subject_shape=subj_shape, object_shape=obj_shape, operation=operation))
        action_set.metadata["generated_from"] = "relations"
        action_set.metadata["operation"] = operation
        return action_set

    def from_entities_and_relations(
        self,
        entities: list[Any],
        relations: list[Any],
        operation: str = "add",
    ) -> ActionSet:
        """Convert both entities and relations into a combined ActionSet.

        Args:
            entities: List of entity-like objects.
            relations: List of relation-like objects.
            operation: Operation applied to both entities and relations. If
                'update', the converter will emit both remove *and* add
                actions so downstream static validation can reason about
                updates.
        """
        if operation == "update":
            # Emit both remove and add actions (update = remove + add)
            remove_set = ActionSet()
            add_set = ActionSet()
            if entities:
                remove_set = self.from_entities(entities, operation="remove")
                add_set = self.from_entities(entities, operation="add")
            if relations:
                r_remove = self.from_relations(relations, operation="remove")
                r_add = self.from_relations(relations, operation="add")
                remove_set.shape_actions.extend(r_remove.shape_actions)
                remove_set.path_actions.extend(r_remove.path_actions)
                add_set.shape_actions.extend(r_add.shape_actions)
                add_set.path_actions.extend(r_add.path_actions)

            merged = ActionSet(
                shape_actions=remove_set.shape_actions + add_set.shape_actions,
                path_actions=remove_set.path_actions + add_set.path_actions,
                metadata={
                    "merged_from": [
                        remove_set.metadata.get("generated_from"),
                        add_set.metadata.get("generated_from"),
                    ],
                    "operation": "update",
                },
            )
            return merged

        entities_set = self.from_entities(entities, operation=operation)
        relations_set = self.from_relations(relations, operation=operation)
        merged = ActionSet(
            shape_actions=entities_set.shape_actions + relations_set.shape_actions,
            path_actions=entities_set.path_actions + relations_set.path_actions,
            metadata={
                "merged_from": [
                    entities_set.metadata.get("generated_from"),
                    relations_set.metadata.get("generated_from"),
                ],
                "operation": operation,
            },
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
