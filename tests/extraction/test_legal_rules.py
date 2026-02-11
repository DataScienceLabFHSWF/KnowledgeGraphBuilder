"""Tests for the LegalRuleBasedExtractor."""

from __future__ import annotations

import pytest

from kgbuilder.extraction.legal_rules import LegalRuleBasedExtractor


@pytest.fixture
def extractor() -> LegalRuleBasedExtractor:
    return LegalRuleBasedExtractor()


class TestParagraphReferences:
    def test_extracts_simple_paragraph_ref(self, extractor: LegalRuleBasedExtractor) -> None:
        text = "Gemäß § 7 ist eine Genehmigung erforderlich."
        entities = extractor.extract_entities(text, law_abbr="AtG", paragraph_id="§ 1")
        refs = [e for e in entities if e.entity_type == "LegalReference"]
        assert len(refs) >= 1
        assert any("§ 7" in e.label for e in refs)

    def test_extracts_paragraph_with_absatz(self, extractor: LegalRuleBasedExtractor) -> None:
        text = "Nach § 19 Abs. 3 kann die Behörde Maßnahmen anordnen."
        entities = extractor.extract_entities(text, law_abbr="AtG")
        refs = [e for e in entities if e.entity_type == "LegalReference"]
        assert len(refs) >= 1
        assert any("§ 19 Abs. 3" in e.label for e in refs)

    def test_detects_external_law_reference(self, extractor: LegalRuleBasedExtractor) -> None:
        text = "Im Einklang mit § 3 BImSchG sind Immissionen zu vermeiden."
        entities = extractor.extract_entities(text, law_abbr="AtG")
        refs = [e for e in entities if e.entity_type == "LegalReference"]
        assert len(refs) >= 1
        assert any("BImSchG" in e.label for e in refs)

    def test_deduplicates_same_reference(self, extractor: LegalRuleBasedExtractor) -> None:
        text = "§ 7 regelt die Genehmigung. Beachte § 7 auch hier."
        entities = extractor.extract_entities(text, law_abbr="AtG")
        refs = [e for e in entities if e.entity_type == "LegalReference"]
        assert len(refs) == 1


class TestAuthorities:
    def test_extracts_zustaendige_behoerde(self, extractor: LegalRuleBasedExtractor) -> None:
        text = "Die zuständige Behörde erteilt die Genehmigung."
        entities = extractor.extract_entities(text)
        auths = [e for e in entities if e.entity_type == "Behoerde"]
        assert len(auths) >= 1
        assert any("zuständige Behörde" in e.label for e in auths)

    def test_extracts_genehmigungsbehoerde(self, extractor: LegalRuleBasedExtractor) -> None:
        text = "Die Genehmigungsbehörde kann den Betrieb untersagen."
        entities = extractor.extract_entities(text)
        auths = [e for e in entities if e.entity_type == "Behoerde"]
        assert len(auths) >= 1

    def test_extracts_known_abbreviations(self, extractor: LegalRuleBasedExtractor) -> None:
        text = "Das BfS überwacht die Strahlenschutzmaßnahmen."
        entities = extractor.extract_entities(text)
        auths = [e for e in entities if e.entity_type == "Behoerde"]
        assert len(auths) >= 1
        assert any("Bundesamt für Strahlenschutz" in e.label for e in auths)

    def test_base_abbreviation(self, extractor: LegalRuleBasedExtractor) -> None:
        text = "Das BASE ist nach § 23d zuständig."
        entities = extractor.extract_entities(text)
        auths = [e for e in entities if e.entity_type == "Behoerde"]
        assert any("nuklearen Entsorgung" in e.label for e in auths)


class TestDeonticModalities:
    def test_extracts_obligation(self, extractor: LegalRuleBasedExtractor) -> None:
        text = "Der Betreiber ist verpflichtet, die Behörde zu unterrichten."
        entities = extractor.extract_entities(text)
        obligs = [e for e in entities if e.entity_type == "Obligation"]
        assert len(obligs) >= 1

    def test_extracts_prohibition(self, extractor: LegalRuleBasedExtractor) -> None:
        text = "Ein solches Vorhaben darf nicht ohne Genehmigung durchgeführt werden."
        entities = extractor.extract_entities(text)
        prohibs = [e for e in entities if e.entity_type == "Prohibition"]
        assert len(prohibs) >= 1

    def test_extracts_permission(self, extractor: LegalRuleBasedExtractor) -> None:
        text = "Die Behörde kann im Einzelfall Ausnahmen zulassen."
        entities = extractor.extract_entities(text)
        perms = [e for e in entities if e.entity_type == "Permission"]
        assert len(perms) >= 1

    def test_prohibition_not_double_counted_as_permission(
        self, extractor: LegalRuleBasedExtractor
    ) -> None:
        text = "Der Betreiber darf nicht entsorgen."
        entities = extractor.extract_entities(text)
        prohibs = [e for e in entities if e.entity_type == "Prohibition"]
        perms = [e for e in entities if e.entity_type == "Permission"]
        assert len(prohibs) >= 1
        assert len(perms) == 0


class TestDefinitions:
    def test_extracts_definition_pattern(self, extractor: LegalRuleBasedExtractor) -> None:
        text = "Im Sinne dieses Gesetzes ist eine kerntechnische Anlage jede Anlage."
        entities = extractor.extract_entities(text)
        defs = [e for e in entities if e.entity_type == "Definition"]
        assert len(defs) >= 1


class TestRelations:
    def test_extracts_referenziert(self, extractor: LegalRuleBasedExtractor) -> None:
        text = "Gemäß § 7 ist eine Genehmigung erforderlich."
        entities = extractor.extract_entities(text, law_abbr="AtG", paragraph_id="§ 1")
        relations = extractor.extract_relations(text, entities, paragraph_id="§ 1")
        referenziert = [r for r in relations if r.predicate == "referenziert"]
        assert len(referenziert) >= 1
        assert referenziert[0].source_entity_id == "§ 1"

    def test_extracts_zustaendig(self, extractor: LegalRuleBasedExtractor) -> None:
        text = "Die zuständige Behörde ist verpflichtet, den Schutz sicherzustellen."
        entities = extractor.extract_entities(text, paragraph_id="§ 12")
        relations = extractor.extract_relations(text, entities, paragraph_id="§ 12")
        zustaendig = [r for r in relations if r.predicate == "zustaendig"]
        assert len(zustaendig) >= 1

    def test_extracts_definiert(self, extractor: LegalRuleBasedExtractor) -> None:
        text = "Im Sinne dieses Gesetzes gelten folgende Begriffe."
        entities = extractor.extract_entities(text, paragraph_id="§ 2")
        relations = extractor.extract_relations(text, entities, paragraph_id="§ 2")
        definiert = [r for r in relations if r.predicate == "definiert"]
        assert len(definiert) >= 1

    def test_confidence_within_range(self, extractor: LegalRuleBasedExtractor) -> None:
        text = "Die zuständige Behörde ist verpflichtet zu prüfen."
        entities = extractor.extract_entities(text, paragraph_id="§ 5")
        relations = extractor.extract_relations(text, entities, paragraph_id="§ 5")
        for rel in relations:
            assert 0.0 < rel.confidence <= 1.0


class TestIntegration:
    def test_full_extraction_on_realistic_text(
        self, extractor: LegalRuleBasedExtractor
    ) -> None:
        text = (
            "Der Betreiber einer Anlage nach § 7 Abs. 1 ist verpflichtet, die "
            "zuständige Behörde unverzüglich zu unterrichten, wenn ein Vorkommnis "
            "eintritt. Die Genehmigungsbehörde kann nach § 19 Abs. 3 AtG die "
            "Genehmigung widerrufen. Das BfS darf nicht ohne Zustimmung des "
            "Bundesministerium für Umwelt Maßnahmen ergreifen. "
            "Im Sinne dieses Gesetzes ist eine kerntechnische Anlage jede Anlage."
        )
        entities = extractor.extract_entities(text, law_abbr="AtG", paragraph_id="§ 21")
        relations = extractor.extract_relations(
            text, entities, law_abbr="AtG", paragraph_id="§ 21"
        )

        types = {e.entity_type for e in entities}
        assert "LegalReference" in types
        assert "Behoerde" in types
        assert "Obligation" in types
        assert "Prohibition" in types
        assert "Definition" in types

        predicates = {r.predicate for r in relations}
        assert "referenziert" in predicates
        assert "zustaendig" in predicates
        assert "definiert" in predicates
