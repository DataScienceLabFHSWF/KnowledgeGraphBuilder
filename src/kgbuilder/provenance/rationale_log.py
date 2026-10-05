"""Append-only provenance/rationale log for KG construction decisions.

Records *why* an agent made a decision about an entity or relation — kept,
merged, rejected, repaired, validated — as opposed to `Evidence`, which
grounds a *fact* in source text. This closes the "why is this axiom here?"
gap identified after SEMANTiCS 2026 (see
`Planning/SEMANTICS2026_IMPROVEMENT_PLAN.md`, Phase A / gap G1).

Sources / attribution
----------------------
- **MASEO** (Multi-Agent System for Explainable Ontology Generation),
  OEG-UPM — the direct design inspiration for per-axiom, agent-attributed,
  append-only provenance (`vaem:rationale` + `dc:source`, linking each
  change back to the CQ/pitfall/error that motivated it).
  Repo: https://github.com/oeg-upm/maseo (Apache-2.0)
  Docs: https://maseo.readthedocs.io
  DOI: 10.5281/zenodo.19052003
  Funded by SOEL — "Supporting Ontology Engineering with Large Language
  Models" (https://w3id.org/soel), grant PID2023-152703NA-I00.
  Presented at SEMANTiCS 2026 (Ghent, 15-17 Sep 2026), IOS Press
  *Studies on the Semantic Web* vol. 63, doi:10.3233/SSW63 (CC BY 4.0).
- **Sabou, M.** "Beyond Data: Why the Future of AI is Neurosymbolic"
  (NeSy workshop keynote, SEMANTiCS 2026, WU Wien) — named provenance and
  continuous system auditing as prerequisites for trustworthy AI, and
  argued explanations are only useful when grounded in domain knowledge.
- **W3C PROV-O** (PROV Ontology), https://www.w3.org/TR/prov-o/ — vocabulary
  used for the `prov:wasGeneratedBy` / `prov:generatedAtTime` JSON-LD export
  shape below, for interoperability beyond this repo's own log format.
- **Dublin Core Metadata Terms** (`dc:`), used for `dc:source`:
  https://www.dublincore.org/specifications/dublin-core/dcmi-terms/
- **VAEM** (Vocabulary for Attaching Essential Metadata), used for
  `vaem:rationale`: http://www.linkedmodel.org/schema/vaem
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import structlog

from kgbuilder.core.models import RationaleEntry

logger = structlog.get_logger(__name__)

JSONLD_CONTEXT = {
    "prov": "http://www.w3.org/ns/prov#",
    "dc": "http://purl.org/dc/terms/",
    "vaem": "http://www.linkedmodel.org/schema/vaem#",
}


@runtime_checkable
class _RationaleCarrier(Protocol):
    """Structural type for anything with an `id` and a `rationale` list."""

    id: str
    rationale: list[RationaleEntry]


class RationaleLog:
    """Append-only log of `RationaleEntry` records, keyed by entity/relation id.

    Usage:
        >>> log = RationaleLog()
        >>> log.record(entity, agent="module_extraction_agent:Assets", \
                        action="extracted", reason="matched Facility class", \
                        triggered_by="q_facility")
        >>> log.entries_for(entity.id)
        [RationaleEntry(agent='module_extraction_agent:Assets', ...)]
    """

    def __init__(self) -> None:
        self._entries_by_id: dict[str, list[RationaleEntry]] = {}

    def record(
        self,
        subject: _RationaleCarrier,
        agent: str,
        action: str,
        reason: str,
        triggered_by: str | None = None,
    ) -> RationaleEntry:
        """Record one decision about `subject` (an entity or relation).

        Appends the new `RationaleEntry` both to the log's own index (keyed
        by `subject.id`, so it survives independent of the object) and to
        `subject.rationale` (so it travels with the entity/relation through
        serialization).

        Args:
            subject: The `ExtractedEntity`/`ExtractedRelation` this decision
                is about (must have `.id` and a mutable `.rationale` list).
            agent: Name of the agent making the decision.
            action: Short verb phrase (e.g. "extracted", "validated", "repaired").
            reason: Human-readable justification.
            triggered_by: Optional id of what motivated this (CQ id, SHACL
                violation id, OOPS! pitfall id, ...).

        Returns:
            The recorded `RationaleEntry`.
        """
        entry = self.record_for_id(
            subject.id, agent=agent, action=action, reason=reason, triggered_by=triggered_by,
        )
        subject.rationale.append(entry)
        return entry

    def record_for_id(
        self,
        subject_id: str,
        agent: str,
        action: str,
        reason: str,
        triggered_by: str | None = None,
    ) -> RationaleEntry:
        """Record a decision keyed by a plain id, for subjects with no `.rationale` list.

        Use this for decisions that aren't about a specific `ExtractedEntity`/
        `ExtractedRelation` object — e.g. a VCQ question's validation outcome,
        keyed by `question.question_id`.
        """
        entry = RationaleEntry(agent=agent, action=action, reason=reason, triggered_by=triggered_by)
        self._entries_by_id.setdefault(subject_id, []).append(entry)
        logger.debug(
            "rationale_recorded",
            subject_id=subject_id,
            agent=agent,
            action=action,
            triggered_by=triggered_by,
        )
        return entry

    def entries_for(self, subject_id: str) -> list[RationaleEntry]:
        """Return all recorded entries for a given entity/relation id."""
        return list(self._entries_by_id.get(subject_id, []))

    def __len__(self) -> int:
        return sum(len(entries) for entries in self._entries_by_id.values())

    def export_jsonld(self, base_uri: str = "http://kgbuilder.io/kg/") -> dict[str, Any]:
        """Export the full log as PROV-O/VAEM/Dublin-Core-shaped JSON-LD.

        Args:
            base_uri: Base URI used to mint subject node ids.

        Returns:
            A JSON-LD document with one node per subject id, each carrying a
            `vaem:rationale` array of provenance records.
        """
        graph = []
        for subject_id, entries in self._entries_by_id.items():
            graph.append(
                {
                    "@id": f"{base_uri.rstrip('/')}/{subject_id}",
                    "vaem:rationale": [
                        {
                            "vaem:rationale": entry.reason,
                            "prov:wasGeneratedBy": entry.agent,
                            "prov:generatedAtTime": entry.timestamp,
                            "dc:source": entry.triggered_by,
                            "action": entry.action,
                        }
                        for entry in entries
                    ],
                }
            )
        return {"@context": JSONLD_CONTEXT, "@graph": graph}
