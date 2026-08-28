"""Join skill: merge entities produced by independent per-module subagents."""

from __future__ import annotations

from typing import Any

from kgbuilder.skills.base import AgentSkill


def _join_module_results_handler(results_by_module: dict[str, list[Any]]) -> list[Any]:
    """Merge entities from multiple module subagents, deduping by (label, type).

    Uses the same dedup key strategy as `IterativeDiscoveryLoop` so entities
    for the same real-world concept found by different module subagents
    collapse into a single higher-confidence entity with merged evidence.
    """
    merged: dict[tuple[str, str], Any] = {}

    for entities in results_by_module.values():
        for entity in entities:
            dedup_key = (entity.label.lower().strip(), entity.entity_type.lower().strip())
            if dedup_key not in merged:
                merged[dedup_key] = entity
                continue

            existing = merged[dedup_key]
            if entity.confidence > existing.confidence:
                merged_evidence = list(
                    {e.source_id: e for e in existing.evidence + entity.evidence}.values()
                )
                entity.evidence = merged_evidence
                merged[dedup_key] = entity
            elif entity.evidence:
                existing_ids = {e.source_id for e in existing.evidence}
                for ev in entity.evidence:
                    if ev.source_id not in existing_ids:
                        existing.evidence.append(ev)

    return list(merged.values())


JoinModuleResultsSkill = AgentSkill(
    name="join_module_results",
    description=(
        "Merge entity lists produced by independent ontology-module subagents into one "
        "deduplicated result, keeping the highest-confidence version and merged evidence."
    ),
    handler=_join_module_results_handler,
)
