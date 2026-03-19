"""Cross-domain linker between decommissioning KG entities and law graph nodes.

Creates explicit LINKED_GOVERNED_BY, LINKED_DEFINED_IN, etc. relationships
using a 3-tier strategy:
  1. Explicit citation parsing (§ 7 Abs. 3 AtG)
  2. Keyword-to-law matching on entity labels
  3. Entity-type default fallback
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict

import structlog
from neo4j import GraphDatabase

logger = structlog.get_logger(__name__)


class KGLawLinker:
    """Creates cross-domain links between decommissioning KG and law graph.

    Uses a 3-tier linking strategy with deterministic edge IDs
    and paragraph-level resolution where possible.

    Args:
        neo4j_uri: Neo4j bolt URI.
        neo4j_user: Neo4j username.
        neo4j_password: Neo4j password.
        database: Neo4j database name.
        link_prefix: Prefix for cross-domain relationship types.
    """

    def __init__(
        self,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "changeme",
        database: str = "neo4j",
        link_prefix: str = "LINKED_",
    ) -> None:
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.database = database
        self.link_prefix = link_prefix

        # Configurable law patterns
        self.law_patterns: dict[str, dict[str, str | list[str]]] = {
            # --- Core nuclear / radiation laws ---
            "AtG": {
                "patterns": [r"\bAtG\b", r"\bAtomgesetz\b"],
                "full_name": "Atomgesetz",
            },
            "StrlSchG": {
                "patterns": [r"\bStrlSchG\b", r"\bStrahlenschutzgesetz\b"],
                "full_name": "Strahlenschutzgesetz",
            },
            "StrlSchV": {
                "patterns": [r"\bStrlSchV\b", r"\bStrahlenschutzverordnung\b"],
                "full_name": "Strahlenschutzverordnung",
            },
            "StandAG": {
                "patterns": [r"\bStandAG\b", r"\bStandortauswahlgesetz\b"],
                "full_name": "Standortauswahlgesetz",
            },
            # --- Environmental / planning laws ---
            "BImSchG": {
                "patterns": [r"\bBImSchG\b", r"\bImmissionsschutzgesetz\b"],
                "full_name": "Bundes-Immissionsschutzgesetz",
            },
            "UVPG": {
                "patterns": [r"\bUVPG\b", r"\bUmweltverträglichkeitsprüfungsgesetz\b"],
                "full_name": "Gesetz über die Umweltverträglichkeitsprüfung",
            },
            "BauGB": {
                "patterns": [r"\bBauGB\b", r"\bBBauG\b", r"\bBaugesetzbuch\b"],
                "full_name": "Baugesetzbuch",
            },
            "KrWG": {
                "patterns": [r"\bKrWG\b", r"\bKreislaufwirtschaftsgesetz\b"],
                "full_name": "Kreislaufwirtschaftsgesetz",
            },
            # --- Administrative / procedural laws ---
            "VwVfG": {
                "patterns": [r"\bVwVfG\b", r"\bVerwaltungsverfahrensgesetz\b"],
                "full_name": "Verwaltungsverfahrensgesetz",
            },
            "VwGO": {
                "patterns": [r"\bVwGO\b", r"\bVerwaltungsgerichtsordnung\b"],
                "full_name": "Verwaltungsgerichtsordnung",
            },
            # --- Mining ---
            "BBergG": {
                "patterns": [r"\bBBergG\b", r"\bBundesberggesetz\b"],
                "full_name": "Bundesberggesetz",
            },
            # --- Liability / financial security ---
            "VVG": {
                "patterns": [r"\bVVG\b", r"\bVersicherungsvertragsgesetz\b"],
                "full_name": "Versicherungsvertragsgesetz",
            },
            "BGB": {
                "patterns": [r"\bBGB\b", r"\bBürgerliches Gesetzbuch\b"],
                "full_name": "Bürgerliches Gesetzbuch",
            },
            # --- Safety / enforcement ---
            "SprengG": {
                "patterns": [r"\bSprengG\b", r"\bSprengstoffgesetz\b"],
                "full_name": "Gesetz über explosionsgefährliche Stoffe",
            },
            "OWiG": {
                "patterns": [r"\bOWiG\b", r"\bOrdnungswidrigkeitengesetz\b"],
                "full_name": "Gesetz über Ordnungswidrigkeiten",
            },
            # --- Tax / fiscal ---
            "AO": {
                "patterns": [r"\bAO\b(?!\s*\d)", r"\bAbgabenordnung\b"],
                "full_name": "Abgabenordnung",
            },
            # --- Criminal / procedural ---
            "StPO": {
                "patterns": [r"\bStPO\b", r"\bStrafprozessordnung\b"],
                "full_name": "Strafprozessordnung",
            },
        }

        # Entity type → relationship type mapping
        self.governance_mappings: dict[str, str] = {
            "Facility": "GOVERNED_BY",
            "Organization": "GOVERNED_BY",
            "Process": "GOVERNED_BY",
            "Activity": "GOVERNED_BY",
            "NuclearMaterial": "DEFINED_IN",
            "WasteCategory": "DEFINED_IN",
            "Permit": "GOVERNED_BY",
            "SafetySystem": "GOVERNED_BY",
            "Regulation": "GOVERNED_BY",
            "Operation": "GOVERNED_BY",
            "Action": "GOVERNED_BY",
            "DomainRequirement": "GOVERNED_BY",
            "DomainConstant": "DEFINED_IN",
            "DomainPredicate": "GOVERNED_BY",
            "PlanningDomain": "GOVERNED_BY",
            "State": "GOVERNED_BY",
        }

        # Keyword-to-law mappings
        # (regex_pattern, law_code, section_or_None, rel_type, confidence)
        self.keyword_law_mappings: list[
            tuple[re.Pattern[str], str, str | None, str, float]
        ] = [
            # AtG — facility & decommissioning licensing
            (re.compile(r"Kernbrennstoff", re.I), "AtG", "§ 2", "DEFINED_IN", 0.85),
            (
                re.compile(r"Genehmigung|genehmigt", re.I),
                "AtG",
                "§ 7",
                "GOVERNED_BY",
                0.80,
            ),
            (
                re.compile(r"Stilllegung|Abbau|Rückbau|Demontage", re.I),
                "AtG",
                "§ 7 Abs. 3",
                "GOVERNED_BY",
                0.85,
            ),
            (
                re.compile(r"kerntechnisch|Kernanlage|Kernkraftwerk|KKW", re.I),
                "AtG",
                "§ 7",
                "GOVERNED_BY",
                0.80,
            ),
            (
                re.compile(r"Sicherung|Objektschutz|Zutrittskontrolle", re.I),
                "AtG",
                "§ 7 Abs. 2",
                "GOVERNED_BY",
                0.75,
            ),
            (
                re.compile(r"Betreiber|Betriebsgenehmigung", re.I),
                "AtG",
                "§ 7",
                "GOVERNED_BY",
                0.75,
            ),
            (
                re.compile(r"Entsorgung|Endlager|Zwischen\s?lager", re.I),
                "AtG",
                "§ 9a",
                "GOVERNED_BY",
                0.80,
            ),
            (
                re.compile(r"Sicherheitsanalyse|Sicherheitsbericht", re.I),
                "AtG",
                "§ 7a",
                "GOVERNED_BY",
                0.75,
            ),
            (
                re.compile(
                    r"Aufbewahrung.*Kernbrennstoff|Kernbrennstoff.*Aufbewahrung", re.I
                ),
                "AtG",
                "§ 6",
                "GOVERNED_BY",
                0.80,
            ),
            # StrlSchG — radiation protection
            (
                re.compile(r"radioaktiv|Aktivität", re.I),
                "StrlSchG",
                None,
                "GOVERNED_BY",
                0.70,
            ),
            (
                re.compile(r"Freigabe|Freigabewert", re.I),
                "StrlSchG",
                "§ 31",
                "GOVERNED_BY",
                0.85,
            ),
            (
                re.compile(r"Dosisleistung|Strahlenexposition|Strahlung", re.I),
                "StrlSchG",
                "§ 5",
                "GOVERNED_BY",
                0.80,
            ),
            (
                re.compile(
                    r"Überwachungsbereich|Kontrollbereich|Strahlenschutzbereich", re.I
                ),
                "StrlSchG",
                "§ 52",
                "GOVERNED_BY",
                0.80,
            ),
            (
                re.compile(r"Kontamination|dekontaminier", re.I),
                "StrlSchG",
                "§ 64",
                "GOVERNED_BY",
                0.75,
            ),
            (
                re.compile(r"Abfall.*radioaktiv|radioaktiv.*Abfall", re.I),
                "StrlSchG",
                "§ 9a",
                "GOVERNED_BY",
                0.80,
            ),
            (
                re.compile(
                    r"Transport.*radioaktiv|radioaktiv.*Transport|Beförderung", re.I
                ),
                "StrlSchG",
                "§ 27",
                "GOVERNED_BY",
                0.75,
            ),
            (
                re.compile(r"Strahlenschutzbeauftragte", re.I),
                "StrlSchG",
                "§ 70",
                "GOVERNED_BY",
                0.80,
            ),
            (
                re.compile(r"Dosimetrie|Personendosis", re.I),
                "StrlSchG",
                "§ 66",
                "GOVERNED_BY",
                0.75,
            ),
            # BImSchG
            (
                re.compile(r"Emission|Immission", re.I),
                "BImSchG",
                None,
                "GOVERNED_BY",
                0.75,
            ),
            # BBergG
            (
                re.compile(r"Bergbau|untertägig|Schacht", re.I),
                "BBergG",
                None,
                "GOVERNED_BY",
                0.70,
            ),
            # KrWG
            (
                re.compile(
                    r"Abfall.*konventionell|konventionell.*Abfall|Kreislaufwirtschaft",
                    re.I,
                ),
                "KrWG",
                None,
                "GOVERNED_BY",
                0.70,
            ),
            # StandAG — nuclear waste site selection
            (
                re.compile(r"Endlager|Standortauswahl|Endlagersuche|Tiefenlagerung", re.I),
                "StandAG",
                None,
                "GOVERNED_BY",
                0.85,
            ),
            (
                re.compile(r"Planfeststellungsverfahren.*Endlager|Endlager.*Standort", re.I),
                "StandAG",
                "§ 35",
                "GOVERNED_BY",
                0.80,
            ),
            # UVPG — environmental impact assessment
            (
                re.compile(r"Umweltverträglichkeitsprüfung|UVP(?!G)|UVP-Bericht|UVP-Pflicht", re.I),
                "UVPG",
                None,
                "GOVERNED_BY",
                0.85,
            ),
            (
                re.compile(r"Umweltverträglichkeitsstudie|Scoping|UVP-Verfahren", re.I),
                "UVPG",
                None,
                "GOVERNED_BY",
                0.80,
            ),
            # VwVfG — administrative procedure
            (
                re.compile(r"Planfeststellung|Planfeststellungsbeschluss", re.I),
                "VwVfG",
                "§ 72",
                "GOVERNED_BY",
                0.85,
            ),
            (
                re.compile(r"öffentliche Auslegung|Einwendungsverfahren|Erörterungstermin", re.I),
                "VwVfG",
                "§ 73",
                "GOVERNED_BY",
                0.80,
            ),
            (
                re.compile(r"Verwaltungsakt|Widerspruchsverfahren|Anhörung", re.I),
                "VwVfG",
                None,
                "GOVERNED_BY",
                0.70,
            ),
            # VwGO — administrative court
            (
                re.compile(r"Verwaltungsgericht|Verwaltungsklage|Anfechtungsklage", re.I),
                "VwGO",
                None,
                "GOVERNED_BY",
                0.80,
            ),
            (
                re.compile(r"einstweilige Verfügung|aufschiebende Wirkung", re.I),
                "VwGO",
                "§ 80",
                "GOVERNED_BY",
                0.75,
            ),
            # VVG — insurance / financial security
            (
                re.compile(r"Deckungsvorsorge|Haftpflichtversicherung", re.I),
                "VVG",
                None,
                "GOVERNED_BY",
                0.80,
            ),
            # BauGB — building / land use planning
            (
                re.compile(r"Bebauungsplan|Bauleitplan|Flächennutzungsplan", re.I),
                "BauGB",
                None,
                "GOVERNED_BY",
                0.80,
            ),
            # BGB — civil liability
            (
                re.compile(r"Schadensersatz|Haftung.*Betreiber|Eigentümer.*Haftung", re.I),
                "BGB",
                None,
                "GOVERNED_BY",
                0.70,
            ),
            # SprengG — explosives (demolition work)
            (
                re.compile(r"Sprengstoff|Sprengung|Sprengarbeiten|Pyrotechnik", re.I),
                "SprengG",
                None,
                "GOVERNED_BY",
                0.80,
            ),
        ]

        # Entity-type-to-law defaults (fallback)
        self.type_law_defaults: dict[
            str, list[tuple[str, str | None, str, float]]
        ] = {
            "Facility": [("AtG", "§ 7", "GOVERNED_BY", 0.60)],
            "Operation": [("AtG", "§ 7 Abs. 3", "GOVERNED_BY", 0.60)],
            "DomainRequirement": [("StrlSchG", None, "GOVERNED_BY", 0.50)],
            "SafetySystem": [("AtG", "§ 7 Abs. 2", "GOVERNED_BY", 0.55)],
            "NuclearMaterial": [("AtG", "§ 2", "DEFINED_IN", 0.55)],
            "WasteCategory": [("StrlSchG", None, "DEFINED_IN", 0.50)],
            "Permit": [("AtG", "§ 7", "GOVERNED_BY", 0.55)],
            "Process": [("VwVfG", None, "GOVERNED_BY", 0.45)],
            "Activity": [("AtG", "§ 7 Abs. 3", "GOVERNED_BY", 0.45)],
        }

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #

    def create_links(self, dry_run: bool = True) -> dict:
        """Create cross-domain links between KG entities and law nodes.

        Args:
            dry_run: If True, compute links but don't write to Neo4j.

        Returns:
            Summary dict with total_entities_processed, total_links_created,
            stats breakdown, and sample links.
        """
        entities = self._get_decommissioning_entities()
        links_created: list[dict] = []
        stats: dict[str, int] = defaultdict(int)

        driver = GraphDatabase.driver(
            self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
        )

        try:
            with driver.session(database=self.database) as session:
                for entity in entities:
                    entity_id = entity["id"]
                    entity_label = entity["label"]
                    entity_type = entity["entity_type"]

                    # Collect text sources for explicit citation detection
                    text_sources = [entity_label]
                    if entity.get("properties"):
                        try:
                            props = (
                                json.loads(entity["properties"])
                                if isinstance(entity["properties"], str)
                                else entity["properties"]
                            )
                            if isinstance(props, dict):
                                for key in (
                                    "evidence",
                                    "source_text",
                                    "context",
                                    "description",
                                    "text",
                                    "content",
                                ):
                                    if key in props and props[key]:
                                        if isinstance(props[key], list):
                                            text_sources.extend(
                                                [str(x) for x in props[key]]
                                            )
                                        else:
                                            text_sources.append(str(props[key]))
                        except (json.JSONDecodeError, TypeError):
                            pass

                    # --- Tier 1: Explicit citations ---
                    explicit_refs: list[dict] = []
                    for text in text_sources:
                        if text:
                            explicit_refs.extend(
                                self.find_law_references_in_text(text)
                            )

                    explicit_keys: set[tuple[str, str | None]] = set()
                    for ref in explicit_refs:
                        rel_type = self.determine_relationship_type(
                            entity_type, ref.get("context", "")
                        )
                        link = {
                            "source_entity": entity_id,
                            "target_law": ref["law_code"],
                            "relationship": rel_type,
                            "confidence": ref["confidence"],
                            "reason": "explicit_citation",
                            "section": ref.get("section"),
                            "context": ref.get("context"),
                        }
                        links_created.append(link)
                        stats["explicit_citations"] += 1
                        explicit_keys.add((ref["law_code"], ref.get("section")))

                        if not dry_run:
                            self._create_relationship(session, link)

                    # --- Tier 2: Keyword matching ---
                    keyword_refs = self.find_keyword_law_references(entity_label)
                    for ref in keyword_refs:
                        key = (ref["law_code"], ref.get("section"))
                        if key in explicit_keys:
                            continue
                        link = {
                            "source_entity": entity_id,
                            "target_law": ref["law_code"],
                            "relationship": ref.get(
                                "relationship_override", "GOVERNED_BY"
                            ),
                            "confidence": ref["confidence"],
                            "reason": "keyword_match",
                            "section": ref.get("section"),
                            "context": ref.get("context"),
                        }
                        links_created.append(link)
                        explicit_keys.add(key)
                        stats["keyword_matches"] += 1

                        if not dry_run:
                            self._create_relationship(session, link)

                    # --- Tier 3: Entity-type default ---
                    if not explicit_refs and not keyword_refs:
                        type_defaults = self.find_type_law_defaults(entity_type)
                        for ref in type_defaults:
                            link = {
                                "source_entity": entity_id,
                                "target_law": ref["law_code"],
                                "relationship": ref.get(
                                    "relationship_override", "GOVERNED_BY"
                                ),
                                "confidence": ref["confidence"],
                                "reason": "type_default",
                                "section": ref.get("section"),
                                "context": ref.get("context"),
                            }
                            links_created.append(link)
                            stats["type_defaults"] += 1

                            if not dry_run:
                                self._create_relationship(session, link)

                    if len(links_created) % 50 == 0 and links_created:
                        logger.info(
                            "law_linking_progress", links_so_far=len(links_created)
                        )
        finally:
            driver.close()

        result = {
            "total_entities_processed": len(entities),
            "total_links_created": len(links_created),
            "stats": dict(stats),
            "links": links_created[:100],
        }

        logger.info(
            "law_linking_complete",
            entities=len(entities),
            links=len(links_created),
            stats=dict(stats),
        )
        return result

    def get_link_statistics(self) -> dict[str, int]:
        """Return counts of existing cross-domain links by relationship type."""
        driver = GraphDatabase.driver(
            self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
        )
        try:
            with driver.session(database=self.database) as session:
                prefixed = [
                    f"{self.link_prefix}{t}"
                    for t in ("REFERENCES", "GOVERNED_BY", "DEFINED_IN", "REQUIRES")
                ]
                rel_types_str = "|".join(prefixed)

                query = f"""
                MATCH (n)-[r:{rel_types_str}]->(law)
                WHERE NOT any(l IN labels(n)
                              WHERE l IN ['Paragraf', 'Abschnitt', 'Gesetzbuch'])
                RETURN type(r) as rel_type, count(*) as count
                ORDER BY count DESC
                """
                result = session.run(query)
                stats: dict[str, int] = {
                    record["rel_type"]: record["count"] for record in result
                }

                total_q = f"""
                MATCH (n)-[r:{rel_types_str}]->(law)
                WHERE NOT any(l IN labels(n)
                              WHERE l IN ['Paragraf', 'Abschnitt', 'Gesetzbuch'])
                RETURN count(r) as total
                """
                total_rec = session.run(total_q).single()
                stats["total"] = total_rec["total"] if total_rec else 0
                return stats
        finally:
            driver.close()

    # --------------------------------------------------------------------- #
    # Matching helpers
    # --------------------------------------------------------------------- #

    def find_law_references_in_text(self, text: str) -> list[dict]:
        """Find explicit law references (§ citations) in text."""
        references: list[dict] = []

        citation_patterns = [
            # § 7 Abs. 3 AtG
            (
                re.compile(
                    r"§\s*(\d+[\w]*)\s+Abs\.?\s*(\d+[\w]*)\s+([A-Z][A-Za-z]+)",
                    re.IGNORECASE,
                ),
                lambda m: (
                    f"{m.group(1)} Abs. {m.group(2)}",
                    self._normalize_law_code(m.group(3)),
                ),
            ),
            # § 4 Absatz 1
            (
                re.compile(
                    r"§\s*(\d+[\w]*)\s+Absatz\s+(\d+[\w]*)", re.IGNORECASE
                ),
                lambda m: (f"{m.group(1)} Abs. {m.group(2)}", None),
            ),
            # § 7 AtG
            (
                re.compile(
                    r"§\s*(\d+[\w]*)\s+([A-Z][A-Za-z]+)", re.IGNORECASE
                ),
                lambda m: (m.group(1), self._normalize_law_code(m.group(2))),
            ),
            # Art. 12 BBergG
            (
                re.compile(
                    r"Art\.?\s*(\d+[\w]*)\s+([A-Z][A-Za-z]+)", re.IGNORECASE
                ),
                lambda m: (
                    f"Art. {m.group(1)}",
                    self._normalize_law_code(m.group(2)),
                ),
            ),
            # Full names
            (
                re.compile(
                    r"\b(Strahlenschutzgesetz|Atomgesetz|Berggesetz"
                    r"|Immissionsschutzgesetz|Kreislaufwirtschaftsgesetz)\b",
                    re.IGNORECASE,
                ),
                lambda m: (None, self._normalize_law_code(m.group(1))),
            ),
            # Abbreviations
            (
                re.compile(
                    r"\b(AtG|BBergG|BImSchG|KrWG|StrlSchG|StrSchG"
                    r"|StrVG|AtVfV|UVPG|StrlSchV)\b",
                    re.IGNORECASE,
                ),
                lambda m: (None, self._normalize_law_code(m.group(1))),
            ),
        ]

        for pattern, extractor in citation_patterns:
            for match in pattern.finditer(text):
                section, law_code = extractor(match)
                if law_code and (
                    law_code in self.law_patterns or law_code == "StrlSchV"
                ):
                    references.append(
                        {
                            "law_code": law_code,
                            "section": section,
                            "context": text[
                                max(0, match.start() - 50) : match.end() + 50
                            ].strip(),
                            "confidence": 0.95,
                            "type": "explicit_citation",
                        }
                    )
                elif section and not law_code:
                    references.append(
                        {
                            "law_code": "AtG",
                            "section": section,
                            "context": text[
                                max(0, match.start() - 50) : match.end() + 50
                            ].strip(),
                            "confidence": 0.7,
                            "type": "explicit_citation",
                        }
                    )
        return references

    def find_keyword_law_references(self, label: str) -> list[dict]:
        """Match entity label against keyword-to-law mappings."""
        references: list[dict] = []
        seen: set[tuple[str, str | None]] = set()
        for pattern, law_code, section, rel_type, confidence in self.keyword_law_mappings:
            if pattern.search(label):
                key = (law_code, section)
                if key not in seen:
                    seen.add(key)
                    references.append(
                        {
                            "law_code": law_code,
                            "section": section,
                            "context": label,
                            "confidence": confidence,
                            "type": "keyword_match",
                            "relationship_override": rel_type,
                        }
                    )
        return references

    def find_type_law_defaults(self, entity_type: str) -> list[dict]:
        """Return default law links for an entity type (lowest-confidence fallback)."""
        defaults = self.type_law_defaults.get(entity_type, [])
        return [
            {
                "law_code": law_code,
                "section": section,
                "context": f"type-default for {entity_type}",
                "confidence": confidence,
                "type": "type_default",
                "relationship_override": rel_type,
            }
            for law_code, section, rel_type, confidence in defaults
        ]

    def determine_relationship_type(
        self, entity_type: str, law_context: str
    ) -> str:
        """Determine the appropriate relationship type for a link."""
        if entity_type in self.governance_mappings:
            return self.governance_mappings[entity_type]
        if "definition" in law_context.lower() or "defined" in law_context.lower():
            return "DEFINED_IN"
        if "permit" in law_context.lower() or "approval" in law_context.lower():
            return "REQUIRES"
        return "GOVERNED_BY"

    def generate_visualization_query(self) -> str:
        """Generate a Neo4j Browser query for visualizing cross-domain links."""
        return (
            "// Cross-Domain KG-Law Links Visualization\n"
            "MATCH (n)-[r:LINKED_REFERENCES|LINKED_GOVERNED_BY"
            "|LINKED_DEFINED_IN|LINKED_REQUIRES]->(law)\n"
            "WHERE NOT any(l IN labels(n) "
            "WHERE l IN ['Paragraf', 'Abschnitt', 'Gesetzbuch'])\n"
            "RETURN n, r, law\n"
            "LIMIT 100"
        )

    # --------------------------------------------------------------------- #
    # Private helpers
    # --------------------------------------------------------------------- #

    def _get_decommissioning_entities(self) -> list[dict]:
        """Retrieve all non-law entities from Neo4j."""
        driver = GraphDatabase.driver(
            self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
        )
        try:
            with driver.session(database=self.database) as session:
                query = """
                MATCH (n)
                WHERE NOT any(l IN labels(n)
                              WHERE l IN ['Paragraf', 'Abschnitt', 'Gesetzbuch'])
                AND n.label IS NOT NULL
                AND n.node_type IS NOT NULL
                RETURN n.id as id, n.label as label,
                       n.node_type as entity_type,
                       n.confidence as confidence,
                       n.properties as properties
                """
                result = session.run(query)
                entities = [dict(record) for record in result]
                logger.info("decommissioning_entities_retrieved", count=len(entities))
                return entities
        finally:
            driver.close()

    @staticmethod
    def _resolve_paragraph_id(law_code: str, section: str | None) -> str | None:
        """Resolve law code + section to a Paragraf node ID.

        Returns None when no paragraph-level node can be determined.

        Examples:
            ("AtG", "§ 7")       → "AtG_S_7"
            ("StrlSchG", "§ 31") → "StrlSchG_S_31"
            ("AtG", "§ 7 Abs. 3")  → "AtG_S_7"
            ("AtG", None)        → None
        """
        if section is None:
            return None
        m = re.match(r"§?\s*(\d+\w*)", section)
        if m:
            return f"{law_code}_S_{m.group(1)}"
        return None

    def _normalize_law_code(self, code: str) -> str:
        """Normalize law code abbreviations."""
        mappings = {
            "STRSCHG": "StrlSchG",
            "STRVG": "StrVG",
            "ATVFV": "AtVfV",
            "UVPG": "UVPG",
        }
        return mappings.get(code.upper(), code)

    def _create_relationship(self, session, link: dict) -> None:  # type: ignore[type-arg]
        """Create a single cross-domain relationship in Neo4j.

        Tries paragraph-level link first, falls back to Gesetzbuch node.
        Uses MERGE with deterministic edge IDs for idempotency.
        """
        relationship_type = f"{self.link_prefix}{link['relationship']}"

        if link["relationship"] not in (
            "REFERENCES",
            "GOVERNED_BY",
            "DEFINED_IN",
            "REQUIRES",
        ):
            raise ValueError(
                f"Unsupported relationship type: {link['relationship']}"
            )

        # Try paragraph-level first
        paragraph_id = self._resolve_paragraph_id(
            link["target_law"], link.get("section")
        )

        # Deterministic edge ID
        target_id = paragraph_id or link["target_law"]
        edge_key = (
            f"{link['source_entity']}::{target_id}"
            f"::{relationship_type}::{link.get('section', '')}"
        )
        edge_id = (
            f"{relationship_type}"
            f"_{hashlib.sha256(edge_key.encode()).hexdigest()[:12]}"
        )

        # Dynamic SET clause
        set_parts = ["r.confidence = $confidence", "r.reason = $reason"]
        params: dict = {
            "entity_id": link["source_entity"],
            "edge_id": edge_id,
            "confidence": link["confidence"],
            "reason": link["reason"],
        }
        if link.get("section"):
            set_parts.append("r.section = $section")
            params["section"] = link["section"]
        if link.get("context"):
            set_parts.append("r.context = $context")
            params["context"] = link["context"]
        set_clause = ", ".join(set_parts)

        if paragraph_id:
            params["paragraph_id"] = paragraph_id
            query = f"""
            MATCH (para:Paragraf {{id: $paragraph_id}})
            MATCH (entity) WHERE entity.id = $entity_id
            MERGE (entity)-[r:{relationship_type} {{id: $edge_id}}]->(para)
            SET {set_clause}
            RETURN count(r) AS cnt
            """
            result = session.run(query, **params)
            record = result.single()
            if record and record["cnt"] > 0:
                return  # paragraph-level link created

        # Fallback: link to Gesetzbuch
        params["law_code"] = link["target_law"]
        query = f"""
        MATCH (law:Gesetzbuch {{id: $law_code}})
        MATCH (entity) WHERE entity.id = $entity_id
        MERGE (entity)-[r:{relationship_type} {{id: $edge_id}}]->(law)
        SET {set_clause}
        """
        session.run(query, **params)
