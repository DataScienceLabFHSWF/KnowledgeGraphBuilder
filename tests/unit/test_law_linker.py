"""Unit tests for law linker helper methods."""

from __future__ import annotations

import re

import pytest

from kgbuilder.linking.law_linker import KGLawLinker


@pytest.fixture

def linker() -> KGLawLinker:
    return KGLawLinker()


def test_normalize_and_resolve():
    lk = KGLawLinker()
    assert lk._normalize_law_code("strschg") == "StrlSchG"
    assert lk._normalize_law_code("unknown") == "unknown"
    assert lk._resolve_paragraph_id("AtG", "§ 7") == "AtG_S_7"
    assert lk._resolve_paragraph_id("X", None) is None
    assert lk._resolve_paragraph_id("Y", "no match") is None


def test_determine_relationship_type():
    lk = KGLawLinker()
    # entity type present -> mapping
    assert lk.determine_relationship_type("Facility", "whatever") == "GOVERNED_BY"
    # context leads to defined in
    assert lk.determine_relationship_type("Foo", "this definition") == "DEFINED_IN"
    # context leads to requires
    assert lk.determine_relationship_type("Foo", "requires approval") == "REQUIRES"
    # fallback
    assert lk.determine_relationship_type("Bar", "other text") == "GOVERNED_BY"


def test_find_law_references_in_text():
    lk = KGLawLinker()
    # explicit citation with law code
    text = "Some text § 7 Abs. 3 AtG more"
    results = lk.find_law_references_in_text(text)
    # at least one entry with correct section should be present
    assert any("7 Abs. 3" in r.get("section", "") for r in results)
    # law_code should appear in one of them
    assert any(r.get("law_code") == "AtG" for r in results)

    # citation without code should default to AtG
    text2 = "See § 4 Absatz 1 for rules"
    res2 = lk.find_law_references_in_text(text2)
    assert res2[0]["law_code"] == "AtG"
    assert "4 Abs. 1" in res2[0]["section"]

    # abbreviation match
    text3 = "Refer to StrlSchG for radiation"
    res3 = lk.find_law_references_in_text(text3)
    assert res3[0]["law_code"] == "StrlSchG"


def test_keyword_and_type_defaults(linker):
    # keyword mapping should return at least one entry for a known keyword
    kw = "Kernbrennstoff facility"
    kw_res = linker.find_keyword_law_references(kw)
    assert any(r["law_code"] == "AtG" for r in kw_res)

    # type defaults include mapping entries for Facility
    defaults = linker.find_type_law_defaults("Facility")
    assert any(d["relationship_override"] == "GOVERNED_BY" for d in defaults)


def test_generate_visualization_query(linker):
    q = linker.generate_visualization_query()
    assert "MATCH" in q and "LINKED_GOVERNED_BY" in q

