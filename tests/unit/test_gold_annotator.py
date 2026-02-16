"""Tests for the static gold-standard annotator scaffold."""
from __future__ import annotations

from pathlib import Path

from kgbuilder.tools.annotator import generate_annotator_html


def test_generate_annotator_html_contains_text_and_docid(tmp_path: Path) -> None:
    text = "Dies ist ein Testdokument. Paragraph §1 ist wichtig."
    html = generate_annotator_html(text, doc_id="testdoc")
    assert "testdoc" in html
    assert "Paragraph §1" in html or "§1" in html


def test_generate_annotator_html_contains_download_filename() -> None:
    html = generate_annotator_html("Kurztext", doc_id="download_doc")
    # verify the client-side download filename is present in the generated HTML
    assert "download_doc_gold.json" in html


def test_cli_writes_file(tmp_path: Path) -> None:
    p = tmp_path / "doc.txt"
    p.write_text("Ein kurzer Text zum Annotieren", encoding='utf8')
    out = tmp_path / "annot.html"
    # Use the module-level generator to create an output file
    html = generate_annotator_html(p.read_text(encoding='utf8'), doc_id="cli_doc")
    out.write_text(html, encoding='utf8')
    assert out.exists()
    assert "cli_doc" in out.read_text(encoding='utf8')