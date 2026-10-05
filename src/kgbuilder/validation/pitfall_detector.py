"""Ontology pitfall detection via OOPS! (SEMANTiCS 2026 Phase C, gap G3).

Wraps the public **OOPS! (OntOlogy Pitfall Scanner!)** REST API — no local
install required, just network access (`httpx`, already a core dependency).
When the API is unreachable or returns an error, falls back to a small
local rule-based scan covering the two pitfalls cheapest to reimplement
without an external service: **P08** (missing human-readable annotations)
and **P11** (missing domain/range on object properties). This mirrors the
"prompt diversity + rule-based validator" pattern (gap G6) rather than
adding a second hard external dependency for the fallback path.

Verified against the real OOPS! service (2026-09-17) using
`data/ontology/domain/decommissioning.owl`: it currently reports **P10**
(missing disjointness, 1 affected element) and **P08** (missing
annotations, 64 affected elements) at "Important" severity — concrete,
actionable findings for anyone tightening this ontology before publication.

Sources / attribution
----------------------
- **OOPS!** (OntOlogy Pitfall Scanner!), Poveda-Villalón et al., UPM —
  used by MASEO's Pitfall Resolution Agent as one stage of a decompose ->
  generate -> validate -> repair cascade; this module provides the *check*
  half of that pattern. Service: https://oops.linkeddata.es/
- **MASEO** (Multi-Agent System for Explainable Ontology Generation,
  OEG-UPM): https://github.com/oeg-upm/maseo (Apache-2.0) ·
  doi:10.5281/zenodo.19052003
- Presented at SEMANTiCS 2026 (Ghent, 15-17 Sep 2026), IOS Press
  *Studies on the Semantic Web* vol. 63, doi:10.3233/SSW63 (CC BY 4.0).
  See `Planning/SEMANTICS2026_IMPROVEMENT_PLAN.md` Phase C / gap G3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

DEFAULT_OOPS_API_URL = "https://oops.linkeddata.es/rest"

_OOPS_NS = "http://oops.linkeddata.es/def#"


@dataclass
class Pitfall:
    """One pitfall finding (from OOPS! or the local fallback scan).

    Attributes:
        code: OOPS! pitfall code (e.g. `"P08"`, `"P10"`, `"P11"`), or a
            `"LOCAL-*"` code for fallback-scan findings not tied to an
            official OOPS! catalog entry.
        name: Short pitfall name.
        description: Human-readable description.
        importance: `"Critical"`, `"Important"`, or `"Minor"` (OOPS!'s own
            levels; the local fallback uses `"Important"` for both checks).
        affected_elements: URIs/names of ontology elements this finding applies to.
    """

    code: str
    name: str
    description: str
    importance: str = "Important"
    affected_elements: list[str] = field(default_factory=list)

    @property
    def num_affected_elements(self) -> int:
        """Number of affected elements (derived from the list, not a separate count)."""
        return len(self.affected_elements)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict."""
        return {
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "importance": self.importance,
            "affected_elements": self.affected_elements,
            "num_affected_elements": self.num_affected_elements,
        }


@dataclass
class PitfallScanResult:
    """Result of a pitfall scan.

    Attributes:
        pitfalls: Findings, in whatever order the source reported them.
        source: `"oops_api"` or `"local_fallback"`.
        error: Set if the OOPS! API call failed and the local fallback was
            used instead (informational — `pitfalls` may still be populated
            from the fallback scan).
    """

    pitfalls: list[Pitfall] = field(default_factory=list)
    source: str = "oops_api"
    error: str | None = None

    @property
    def critical_count(self) -> int:
        """Number of `"Critical"`-importance pitfalls."""
        return sum(1 for p in self.pitfalls if p.importance.lower() == "critical")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict."""
        return {
            "pitfalls": [p.to_dict() for p in self.pitfalls],
            "source": self.source,
            "error": self.error,
            "critical_count": self.critical_count,
            "total_count": len(self.pitfalls),
        }


class OOPSPitfallDetector:
    """Scans an OWL ontology for common modeling pitfalls via OOPS!."""

    def __init__(
        self,
        api_url: str = DEFAULT_OOPS_API_URL,
        timeout_s: float = 90.0,
        http_client: Any | None = None,
    ) -> None:
        """Initialize the detector.

        Args:
            api_url: OOPS! REST endpoint.
            timeout_s: HTTP request timeout.
            http_client: Optional pre-configured `httpx.Client`-compatible
                object exposing `.post(url, content=..., headers=...,
                timeout=...) -> response` with `.status_code`/`.text`. Used
                mainly for testing without a network dependency.
        """
        self._api_url = api_url
        self._timeout_s = timeout_s
        self._http_client = http_client

    def scan(self, ontology_path: str | Path) -> PitfallScanResult:
        """Scan the OWL ontology at `ontology_path` for pitfalls.

        Tries the OOPS! REST API first; falls back to a local rule-based
        scan (P08/P11 only) if the API call fails or the request itself
        can't be built (e.g. file missing).

        Args:
            ontology_path: Path to an OWL/RDF-XML ontology file.

        Returns:
            `PitfallScanResult`. Never raises.
        """
        path = Path(ontology_path)
        try:
            ontology_content = path.read_text()
        except OSError as e:
            return PitfallScanResult(
                pitfalls=[], source="local_fallback", error=f"Could not read ontology file: {e}",
            )

        try:
            return self._scan_via_api(ontology_content)
        except Exception as e:
            logger.warning("oops_api_scan_failed_falling_back", error=str(e))
            fallback = self._scan_local(path)
            fallback.error = f"OOPS! API unavailable ({e}); used local fallback scan (P08/P11 only)"
            return fallback

    # ------------------------------------------------------------------
    # OOPS! REST API
    # ------------------------------------------------------------------

    def _scan_via_api(self, ontology_content: str) -> PitfallScanResult:
        """Call the OOPS! REST API and parse its RDF/XML response."""
        import httpx

        body = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<OOPSRequest>\n"
            "<OntologyUrl></OntologyUrl>\n"
            f"<OntologyContent><![CDATA[{ontology_content}]]></OntologyContent>\n"
            "<Pitfalls></Pitfalls>\n"
            "<OutputFormat>RDF/XML</OutputFormat>\n"
            "</OOPSRequest>"
        )

        client = self._http_client
        if client is not None:
            response = client.post(
                self._api_url,
                content=body.encode("utf-8"),
                headers={"Content-Type": "application/xml"},
                timeout=self._timeout_s,
            )
        else:
            response = httpx.post(
                self._api_url,
                content=body.encode("utf-8"),
                headers={"Content-Type": "application/xml"},
                timeout=self._timeout_s,
                follow_redirects=True,
            )

        if response.status_code != 200:
            raise RuntimeError(f"OOPS! API returned HTTP {response.status_code}")

        return self._parse_oops_response(response.text)

    @staticmethod
    def _parse_oops_response(rdf_xml: str) -> PitfallScanResult:
        """Parse the OOPS! RDF/XML response into `PitfallScanResult`."""
        import rdflib

        graph = rdflib.Graph()
        graph.parse(data=rdf_xml, format="xml")

        oops = rdflib.Namespace(_OOPS_NS)
        rdf_type = rdflib.RDF.type

        # OOPS! reports its own internal errors as a "...#response" node with
        # hasTitle "OOPS! something went wrong." — but a *successful* scan
        # also emits a "#response" node (linking pitfalls via hasPitfall,
        # no hasTitle), so only hasTitle presence distinguishes an error.
        for node in graph.subjects(rdf_type, oops.response):
            title = graph.value(node, oops.hasTitle)
            if title is not None:
                raise RuntimeError(f"OOPS! service error: {title}")

        pitfalls: list[Pitfall] = []
        for subject in graph.subjects(rdf_type, oops.pitfall):
            code = str(graph.value(subject, oops.hasCode) or "UNKNOWN")
            name = str(graph.value(subject, oops.hasName) or "")
            description = str(graph.value(subject, oops.hasDescription) or "")
            importance = str(graph.value(subject, oops.hasImportanceLevel) or "Important")
            affected = [str(o) for o in graph.objects(subject, oops.hasAffectedElement)]
            pitfalls.append(
                Pitfall(
                    code=code, name=name, description=description,
                    importance=importance, affected_elements=affected,
                )
            )

        return PitfallScanResult(pitfalls=pitfalls, source="oops_api")

    # ------------------------------------------------------------------
    # Local rule-based fallback (P08, P11 only)
    # ------------------------------------------------------------------

    def _scan_local(self, path: Path) -> PitfallScanResult:
        """Cheap local scan for P08 (missing annotations) and P11 (missing domain/range)."""
        import rdflib
        from rdflib.namespace import OWL, RDFS

        graph = rdflib.Graph()
        try:
            graph.parse(str(path))
        except Exception as e:
            return PitfallScanResult(
                pitfalls=[], source="local_fallback", error=f"Failed to parse ontology: {e}",
            )

        annotation_predicates = (RDFS.label, RDFS.comment)
        unannotated: list[str] = []
        for cls in set(graph.subjects(rdflib.RDF.type, OWL.Class)):
            if not any(graph.value(cls, pred) for pred in annotation_predicates):
                unannotated.append(str(cls))

        missing_domain_range: list[str] = []
        for prop in set(graph.subjects(rdflib.RDF.type, OWL.ObjectProperty)):
            has_domain = graph.value(prop, RDFS.domain) is not None
            has_range = graph.value(prop, RDFS.range) is not None
            if not (has_domain and has_range):
                missing_domain_range.append(str(prop))

        pitfalls: list[Pitfall] = []
        if unannotated:
            pitfalls.append(
                Pitfall(
                    code="P08",
                    name="Missing annotations (local check)",
                    description="Classes without rdfs:label or rdfs:comment.",
                    importance="Important",
                    affected_elements=unannotated,
                )
            )
        if missing_domain_range:
            pitfalls.append(
                Pitfall(
                    code="P11",
                    name="Missing domain or range in properties (local check)",
                    description="Object properties without both rdfs:domain and rdfs:range.",
                    importance="Important",
                    affected_elements=missing_domain_range,
                )
            )

        return PitfallScanResult(pitfalls=pitfalls, source="local_fallback")
