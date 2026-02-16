"""Rule-based extractors specialized for German legal text.

Provides high-precision, deterministic extraction of:
- Legal entity patterns (§ references, authority names, legal terms)
- Structural relations (teil_von, referenziert)
- Deontic modalities (obligations, permissions, prohibitions)

These rules exploit the highly structured nature of German law text and
complement LLM-based extraction in the ensemble pipeline.

Usage::

    extractor = LegalRuleBasedExtractor()
    entities = extractor.extract_entities(norm_text, law_abbr="AtG")
    relations = extractor.extract_relations(norm_text, entities)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from kgbuilder.core.models import Evidence, ExtractedEntity, ExtractedRelation

# ---------------------------------------------------------------------------
# Regex patterns for German legal text
# ---------------------------------------------------------------------------

# § references: § 7, §§ 7 bis 9, § 7 Abs. 2 Satz 1 Nr. 3
PARAGRAPH_REF_PATTERN = re.compile(
    r"§§?\s*\d+[a-z]?"
    r"(?:\s*(?:bis|und|,)\s*§?\s*\d+[a-z]?)*"
    r"(?:\s+(?:Abs(?:atz)?\.?\s*\d+))?"
    r"(?:\s+(?:Satz|S\.)\s*\d+)?"
    r"(?:\s+(?:Nr\.?\s*\d+))?"
)

# Authority names (Behörden): Bundesamt für ..., Bundesministerium für ...
AUTHORITY_PATTERN = re.compile(
    r"(?:Bundesamt|Bundesministerium|Landesamt|Landesministerium|Behörde|Aufsichtsbehörde"
    r"|Genehmigungsbehörde|zuständige Behörde)"
    r"(?:\s+für\s+[A-Za-zÄÖÜäöüß\s,]+?)?"
    r"(?=[\s,;.\)])"
)

# Legal definitions: "im Sinne dieses Gesetzes", "nach Maßgabe"
DEFINITION_PATTERN = re.compile(
    r"[Ii]m\s+[Ss]inne\s+(?:dieses|des)\s+(?:Gesetzes|Absatzes|Paragraphen)"
    r"|[Bb]egriff(?:sbestimmung(?:en)?)"
    r"|[Aa]ls\s+\w+\s+(?:gilt|gelten)"
    r"|[Ii]st\s+(?:eine?|der|die|das)\s+\w+,\s+(?:die|der|das)"
)

# Obligation indicators: "ist verpflichtet", "hat ... zu", "muss"
OBLIGATION_PATTERN = re.compile(
    r"\b(?:ist\s+verpflichtet|hat\s+[\w\s]+zu\s+\w+en"
    r"|muss|müssen|sind\s+verpflichtet"
    r"|hat\s+sicherzustellen|ist\s+(?:zu\s+)?\w+en\b)"
)

# Permission indicators: "darf", "kann", "ist berechtigt"
PERMISSION_PATTERN = re.compile(
    r"\b(?:darf|dürfen|kann|können|ist\s+berechtigt"
    r"|wird\s+(?:genehmigt|erlaubt|gestattet|zugelassen))"
)

# Prohibition indicators: "darf nicht", "ist untersagt", "ist verboten"
PROHIBITION_PATTERN = re.compile(
    r"\b(?:darf\s+nicht|dürfen\s+nicht|ist\s+(?:untersagt|verboten|unzulässig)"
    r"|sind\s+(?:untersagt|verboten|unzulässig)|nicht\s+(?:gestattet|zulässig))"
)

# Known German federal authority short names
KNOWN_AUTHORITIES: dict[str, str] = {
    "BfS": "Bundesamt für Strahlenschutz",
    "BASE": "Bundesamt für die Sicherheit der nuklearen Entsorgung",
    "BMU": "Bundesministerium für Umwelt, Naturschutz und nukleare Sicherheit",
    "BMUV": "Bundesministerium für Umwelt, Naturschutz, nukleare Sicherheit und Verbraucherschutz",
    "BfE": "Bundesamt für kerntechnische Entsorgungssicherheit",
    "BAM": "Bundesanstalt für Materialforschung und -prüfung",
    "UBA": "Umweltbundesamt",
    "BfR": "Bundesinstitut für Risikobewertung",
}

# Known law abbreviations for external reference detection
KNOWN_LAW_ABBREVIATIONS: set[str] = {
    "AtG", "StrlSchG", "StrlSchV", "BImSchG", "BImSchV", "KrWG",
    "WHG", "BNatSchG", "UVPG", "BBergG", "GenTG", "ChemG",
    "BGB", "VwVfG", "VwGO", "GG", "StGB", "StPO", "ZPO",
    "EnWG", "EEG", "WindSeeG", "StandAG", "EndlSiAnfV", "EndlSiUntV",
}


@dataclass
class LegalRuleBasedExtractor:
    """Rule-based entity and relation extractor for German legal text.

    Combines regex patterns, gazetteers, and structural heuristics to
    extract entities and relations with high precision. Designed to run
    alongside the LLM extractor in an ensemble.
    """

    confidence_base: float = 0.95  # Rule-based = high confidence
    _entity_counter: int = field(default=0, init=False, repr=False)

    def _next_id(self, prefix: str = "law_ent") -> str:
        self._entity_counter += 1
        return f"{prefix}_{self._entity_counter:04d}"

    def _make_evidence(
        self, text_span: str, paragraph_id: str, source_type: str = "rule"
    ) -> list[Evidence]:
        return [Evidence(source_type=source_type, source_id=paragraph_id, text_span=text_span)]

    def extract_entities(
        self,
        text: str,
        law_abbr: str = "",
        paragraph_id: str = "",
    ) -> list[ExtractedEntity]:
        """Extract all rule-based entities from a norm's text.

        Extracts:
        - Cross-references (LegalReference)
        - Authority mentions (Behörde)
        - Legal definitions (Definition)
        - Obligations, Permissions, Prohibitions

        Args:
            text: Plain text of a law paragraph.
            law_abbr: Abbreviation of the source law (e.g. "AtG").
            paragraph_id: Identifier of the source paragraph (e.g. "§ 7").

        Returns:
            List of extracted entities with evidence.
        """
        entities: list[ExtractedEntity] = []
        entities.extend(self._extract_paragraph_references(text, law_abbr, paragraph_id))
        entities.extend(self._extract_authorities(text, paragraph_id))
        entities.extend(self._extract_known_authority_abbreviations(text, paragraph_id))
        entities.extend(self._extract_definitions(text, paragraph_id))
        entities.extend(self._extract_deontic_modalities(text, paragraph_id))
        return entities

    def extract(
        self,
        text: str,
        law_abbr: str = "",
        paragraph_id: str = "",
    ) -> tuple[list[ExtractedEntity], list[ExtractedRelation]]:
        """Full extraction: entities + relations.
        
        Args:
            text: Plain text of a law paragraph.
            law_abbr: Source law abbreviation.
            paragraph_id: Source paragraph identifier.
        
        Returns:
            Tuple of (entities, relations).
        """
        entities = self.extract_entities(text, law_abbr, paragraph_id)
        relations = self.extract_relations(text, entities, law_abbr, paragraph_id)
        return entities, relations

    def extract_relations(
        self,
        text: str,
        entities: list[ExtractedEntity],
        law_abbr: str = "",
        paragraph_id: str = "",
    ) -> list[ExtractedRelation]:
        """Extract relations between previously extracted entities.

        Extracts:
        - referenziert (paragraph → paragraph via § reference)
        - zuständig (authority → obligation)
        - betrifft (obligation → actor)
        - definiert (paragraph → definition)

        Args:
            text: Plain text of a law paragraph.
            entities: Entities already extracted from this text.
            law_abbr: Source law abbreviation.
            paragraph_id: Source paragraph identifier.

        Returns:
            List of extracted relations with evidence.
        """
        relations: list[ExtractedRelation] = []
        rel_counter = 0

        # Index entities by type for quick lookup
        by_type: dict[str, list[ExtractedEntity]] = {}
        for ent in entities:
            by_type.setdefault(ent.entity_type, []).append(ent)

        # referenziert: source paragraph → each LegalReference
        for ref_ent in by_type.get("LegalReference", []):
            rel_counter += 1
            relations.append(ExtractedRelation(
                id=f"law_rel_{rel_counter:04d}",
                source_entity_id=paragraph_id or "source",
                target_entity_id=ref_ent.id,
                predicate="referenziert",
                confidence=self.confidence_base,
                evidence=self._make_evidence(ref_ent.label, paragraph_id),
            ))

        # definiert: source paragraph → each Definition
        for def_ent in by_type.get("Definition", []):
            rel_counter += 1
            relations.append(ExtractedRelation(
                id=f"law_rel_{rel_counter:04d}",
                source_entity_id=paragraph_id or "source",
                target_entity_id=def_ent.id,
                predicate="definiert",
                confidence=self.confidence_base,
                evidence=self._make_evidence(def_ent.label, paragraph_id),
            ))

        # zuständig: each authority → each obligation
        authorities = by_type.get("Behoerde", [])
        obligations = by_type.get("Obligation", [])
        for auth_ent in authorities:
            for obl_ent in obligations:
                rel_counter += 1
                relations.append(ExtractedRelation(
                    id=f"law_rel_{rel_counter:04d}",
                    source_entity_id=auth_ent.id,
                    target_entity_id=obl_ent.id,
                    predicate="zustaendig",
                    confidence=self.confidence_base * 0.9,
                    evidence=self._make_evidence(
                        f"{auth_ent.label} → {obl_ent.label}", paragraph_id
                    ),
                ))

        # betrifft: each obligation → each Betreiber/LegalActor
        betreiber = by_type.get("Betreiber", []) + by_type.get("LegalActor", [])
        for obl_ent in obligations:
            for actor_ent in betreiber:
                rel_counter += 1
                relations.append(ExtractedRelation(
                    id=f"law_rel_{rel_counter:04d}",
                    source_entity_id=obl_ent.id,
                    target_entity_id=actor_ent.id,
                    predicate="betrifft",
                    confidence=self.confidence_base * 0.85,
                    evidence=self._make_evidence(
                        f"{obl_ent.label} → {actor_ent.label}", paragraph_id
                    ),
                ))

        return relations

    # ------------------------------------------------------------------
    # Pattern-specific extractors
    # ------------------------------------------------------------------

    def _extract_paragraph_references(
        self, text: str, law_abbr: str, paragraph_id: str
    ) -> list[ExtractedEntity]:
        """Extract § cross-references as LegalReference entities."""
        entities: list[ExtractedEntity] = []
        seen: set[str] = set()
        for match in PARAGRAPH_REF_PATTERN.finditer(text):
            ref_text = match.group().strip()
            if ref_text in seen:
                continue
            seen.add(ref_text)
            # Check if it references an external law
            after_pos = match.end()
            context_after = text[after_pos:after_pos + 30]
            ext_law = ""
            for abbr in KNOWN_LAW_ABBREVIATIONS:
                if abbr in context_after.split()[:3]:
                    ext_law = abbr
                    break
            label = f"{ref_text} {ext_law}".strip() if ext_law else ref_text
            entities.append(ExtractedEntity(
                id=self._next_id(),
                label=label,
                entity_type="LegalReference",
                description=f"Reference to {label}" + (f" in {ext_law}" if ext_law else ""),
                confidence=self.confidence_base,
                evidence=self._make_evidence(ref_text, paragraph_id),
                properties={"source_law": law_abbr, "target_law": ext_law or law_abbr},
            ))
        return entities

    def _extract_authorities(
        self, text: str, paragraph_id: str
    ) -> list[ExtractedEntity]:
        """Extract Behörde entities from authority name patterns."""
        entities: list[ExtractedEntity] = []
        seen: set[str] = set()
        for match in AUTHORITY_PATTERN.finditer(text):
            name = match.group().strip()
            if name in seen or len(name) < 7:
                continue
            seen.add(name)
            entities.append(ExtractedEntity(
                id=self._next_id(),
                label=name,
                entity_type="Behoerde",
                description=f"Authority: {name}",
                confidence=self.confidence_base,
                evidence=self._make_evidence(name, paragraph_id),
            ))
        return entities

    def _extract_definitions(
        self, text: str, paragraph_id: str
    ) -> list[ExtractedEntity]:
        """Extract Definition entities from 'im Sinne dieses Gesetzes' patterns."""
        entities: list[ExtractedEntity] = []
        for match in DEFINITION_PATTERN.finditer(text):
            span = match.group().strip()
            # Try to extract the defined term from surrounding context
            start = max(0, match.start() - 80)
            context = text[start:match.end() + 80]
            entities.append(ExtractedEntity(
                id=self._next_id(),
                label=span,
                entity_type="Definition",
                description=f"Legal definition: {context[:120]}",
                confidence=self.confidence_base * 0.9,
                evidence=self._make_evidence(span, paragraph_id),
            ))
        return entities

    def _extract_deontic_modalities(
        self, text: str, paragraph_id: str
    ) -> list[ExtractedEntity]:
        """Extract Obligation, Permission, Prohibition entities."""
        entities: list[ExtractedEntity] = []

        # Prohibitions first (more specific patterns, e.g. "darf nicht" before "darf")
        for match in PROHIBITION_PATTERN.finditer(text):
            span = match.group().strip()
            sent_start = text.rfind(".", 0, match.start())
            sent_end = text.find(".", match.end())
            sentence = text[sent_start + 1:sent_end + 1 if sent_end > 0 else len(text)].strip()
            entities.append(ExtractedEntity(
                id=self._next_id(),
                label=f"Verbot: {sentence[:80]}",
                entity_type="Prohibition",
                description=sentence[:200],
                confidence=self.confidence_base,
                evidence=self._make_evidence(span, paragraph_id),
            ))

        prohibition_spans = {m.span() for m in PROHIBITION_PATTERN.finditer(text)}

        for match in OBLIGATION_PATTERN.finditer(text):
            # Skip if this span overlaps with a prohibition
            if any(
                ps[0] <= match.start() <= ps[1] or ps[0] <= match.end() <= ps[1]
                for ps in prohibition_spans
            ):
                continue
            span = match.group().strip()
            sent_start = text.rfind(".", 0, match.start())
            sent_end = text.find(".", match.end())
            sentence = text[sent_start + 1:sent_end + 1 if sent_end > 0 else len(text)].strip()
            entities.append(ExtractedEntity(
                id=self._next_id(),
                label=f"Pflicht: {sentence[:80]}",
                entity_type="Obligation",
                description=sentence[:200],
                confidence=self.confidence_base,
                evidence=self._make_evidence(span, paragraph_id),
            ))

        for match in PERMISSION_PATTERN.finditer(text):
            # Skip if overlaps with prohibition
            if any(
                ps[0] <= match.start() <= ps[1] or ps[0] <= match.end() <= ps[1]
                for ps in prohibition_spans
            ):
                continue
            span = match.group().strip()
            sent_start = text.rfind(".", 0, match.start())
            sent_end = text.find(".", match.end())
            sentence = text[sent_start + 1:sent_end + 1 if sent_end > 0 else len(text)].strip()
            entities.append(ExtractedEntity(
                id=self._next_id(),
                label=f"Erlaubnis: {sentence[:80]}",
                entity_type="Permission",
                description=sentence[:200],
                confidence=self.confidence_base * 0.9,
                evidence=self._make_evidence(span, paragraph_id),
            ))

        return entities

    def _extract_known_authority_abbreviations(
        self, text: str, paragraph_id: str
    ) -> list[ExtractedEntity]:
        """Extract known authority short names (BfS, BASE, etc.) via gazetteer."""
        entities: list[ExtractedEntity] = []
        for abbr, full_name in KNOWN_AUTHORITIES.items():
            # Word-boundary match to avoid false positives
            pattern = re.compile(rf"\b{re.escape(abbr)}\b")
            if pattern.search(text):
                entities.append(ExtractedEntity(
                    id=self._next_id(),
                    label=full_name,
                    entity_type="Behoerde",
                    description=f"{abbr} – {full_name}",
                    aliases=[abbr],
                    confidence=self.confidence_base,
                    evidence=self._make_evidence(abbr, paragraph_id),
                ))
        return entities
