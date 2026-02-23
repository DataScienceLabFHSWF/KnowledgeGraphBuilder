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
    """A SHACL2FOL ShapeAction: adds/removes ``x predicate y`` for matching shapes.

    SHACL2FOL JSON format::

        {"type": "ShapeAction", "isAdd": true,
         "predicate": "http://...",
         "subjectShape": "@prefix sh: ... :s a sh:NodeShape ; sh:class :Foo .",
         "objectShape": "@prefix sh: ... :s a sh:NodeShape ; sh:class :Bar ."}

    ``subjectShape`` and ``objectShape`` are inline Turtle strings defining
    single named SHACL shapes.
    """

    predicate: str
    subject_shape: str
    object_shape: str
    is_add: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Serialize to SHACL2FOL JSON format."""
        return {
            "type": "ShapeAction",
            "isAdd": self.is_add,
            "predicate": self.predicate,
            "subjectShape": self.subject_shape,
            "objectShape": self.object_shape,
        }


@dataclass
class PathAction:
    """A SHACL2FOL PathAction: adds/removes ``x predicate y`` along a path.

    SHACL2FOL JSON format::

        {"type": "PathAction", "isAdd": true,
         "predicate": "http://...",
         "path": "<http://...>"}

    ``path`` is a SHACL property path expression (angle-bracket IRI or
    Turtle path syntax).
    """

    predicate: str
    path: str
    is_add: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Serialize to SHACL2FOL JSON format."""
        return {
            "type": "PathAction",
            "isAdd": self.is_add,
            "predicate": self.predicate,
            "path": self.path,
        }


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

    def to_json_list(self) -> list[dict[str, Any]]:
        """Serialize all actions to SHACL2FOL JSON array format."""
        actions: list[dict[str, Any]] = []
        for a in self.shape_actions:
            actions.append(a.to_dict())
        for a in self.path_actions:
            actions.append(a.to_dict())
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
    # Helpers
    # ------------------------------------------------------------------

    _TURTLE_PREFIXES = (
        "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\\n"
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\\n"
        "@prefix sh: <http://www.w3.org/ns/shacl#> .\\n"
    )

    def _inline_shape(self, class_uri: str) -> str:
        """Build an inline Turtle shape string for a single class.

        SHACL2FOL requires ``subjectShape`` / ``objectShape`` to be valid
        Turtle containing exactly one named shape.
        """
        return (
            f"{self._TURTLE_PREFIXES}"
            f"<{self._shapes_ns}actionShape> a sh:NodeShape ;\\n"
            f"  sh:class <{class_uri}> .\\n"
        )

    _RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    # helper extraction methods ------------------------------------------------

    @staticmethod
    def _get_entity_type(ent: Any) -> str | None:
        """Return the entity type string for an object, handling legacy attr names.

        The converter accepts many duck-typed objects coming from the
        extraction pipeline; this helper centralizes the lookup logic and makes
        it easier to test in isolation.
        """
        return getattr(ent, "entity_type", None) or getattr(ent, "type", None)

    @staticmethod
    def _get_relation_type(rel: Any) -> str | None:
        """Return the relation/predicate type string for an object.

        Looks for ``relation_type``, ``predicate`` or ``type`` attributes in
        that order, returning ``None`` if none are available.
        """
        return (
            getattr(rel, "relation_type", None)
            or getattr(rel, "predicate", None)
            or getattr(rel, "type", None)
        )

    def from_entities(self, entities: list[Any], operation: str = "add") -> ActionSet:
        """Convert extracted entities to SHACL2FOL actions.

        Each entity type maps to a ``PathAction`` adding an ``rdf:type``
        edge whose path is the identity path on ``rdf:type``.
        """
        is_add = operation != "remove"
        if operation == "update":
            remove_set = self.from_entities(entities, operation="remove")
            add_set = self.from_entities(entities, operation="add")
            return ActionSet(
                shape_actions=remove_set.shape_actions + add_set.shape_actions,
                path_actions=remove_set.path_actions + add_set.path_actions,
                metadata={"operation": "update"},
            )

        action_set = ActionSet()
        seen: set[str] = set()
        for ent in entities:
            ent_type = self._get_entity_type(ent)
            if not ent_type or ent_type in seen:
                continue
            seen.add(ent_type)
            class_uri = f"{self._ont_ns}{ent_type}"
            action_set.path_actions.append(
                PathAction(
                    predicate=self._RDF_TYPE,
                    path=f"<{self._RDF_TYPE}>",
                    is_add=is_add,
                )
            )
        action_set.metadata["generated_from"] = "entities"
        return action_set

    def from_relations(self, relations: list[Any], operation: str = "add") -> ActionSet:
        """Convert extracted relations to SHACL2FOL actions.

        Each relation maps to a ``PathAction`` for the property predicate.
        """
        is_add = operation != "remove"
        if operation == "update":
            remove_set = self.from_relations(relations, operation="remove")
            add_set = self.from_relations(relations, operation="add")
            return ActionSet(
                shape_actions=remove_set.shape_actions + add_set.shape_actions,
                path_actions=remove_set.path_actions + add_set.path_actions,
                metadata={"operation": "update"},
            )

        action_set = ActionSet()
        seen: set[str] = set()
        for rel in relations:
            rel_type = self._get_relation_type(rel)
            if not rel_type or rel_type in seen:
                continue
            seen.add(rel_type)
            pred_uri = f"{self._ont_ns}{rel_type}"
            action_set.path_actions.append(
                PathAction(
                    predicate=pred_uri,
                    path=f"<{pred_uri}>",
                    is_add=is_add,
                )
            )

            # Expand inverse actions when ontology provides inverse declarations
            try:
                if self._ontology_service:
                    special = self._ontology_service.get_special_properties() or {}
                    for inv in special.get("inverse", []) or []:
                        if isinstance(inv, tuple) and len(inv) == 2:
                            a, b = inv
                            inv_type = None
                            if rel_type == a:
                                inv_type = b
                            elif rel_type == b:
                                inv_type = a
                            if inv_type and inv_type not in seen:
                                inv_uri = f"{self._ont_ns}{inv_type}"
                                action_set.path_actions.append(
                                    PathAction(predicate=inv_uri, path=f"<{inv_uri}>", is_add=is_add)
                                )
            except Exception:
                pass

        action_set.metadata["generated_from"] = "relations"
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
