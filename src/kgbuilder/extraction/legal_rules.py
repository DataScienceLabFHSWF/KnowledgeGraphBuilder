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

from kgbuilder.core.models import ExtractedEntity, ExtractedRelation, Evidence


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
        raise NotImplementedError  # TODO: Step 4 implementation

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
        raise NotImplementedError  # TODO: Step 4 implementation

    # ------------------------------------------------------------------
    # Pattern-specific extractors
    # ------------------------------------------------------------------

    def _extract_paragraph_references(
        self, text: str, law_abbr: str, paragraph_id: str
    ) -> list[ExtractedEntity]:
        """Extract § cross-references as LegalReference entities."""
        raise NotImplementedError

    def _extract_authorities(
        self, text: str, paragraph_id: str
    ) -> list[ExtractedEntity]:
        """Extract Behörde entities from authority name patterns."""
        raise NotImplementedError

    def _extract_definitions(
        self, text: str, paragraph_id: str
    ) -> list[ExtractedEntity]:
        """Extract Definition entities from 'im Sinne dieses Gesetzes' patterns."""
        raise NotImplementedError

    def _extract_deontic_modalities(
        self, text: str, paragraph_id: str
    ) -> list[ExtractedEntity]:
        """Extract Obligation, Permission, Prohibition entities."""
        raise NotImplementedError

    def _extract_known_authority_abbreviations(
        self, text: str, paragraph_id: str
    ) -> list[ExtractedEntity]:
        """Extract known authority short names (BfS, BASE, etc.) via gazetteer."""
        raise NotImplementedError
