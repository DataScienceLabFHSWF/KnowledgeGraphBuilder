"""Tests for DocumentLoaderFactory logic."""

from __future__ import annotations

from pathlib import Path

import pytest

from kgbuilder.document.loaders.base import DocumentLoaderFactory
from kgbuilder.document.loaders.pdf import PDFLoader
from kgbuilder.document.loaders.office import DOCXLoader, PPTXLoader
from kgbuilder.core.exceptions import UnsupportedFormatError, DocumentLoadError
from kgbuilder.core.models import Document
import sys
import types


class FakeLoader:
    def __init__(self):
        self.supported_extensions = [".foo", ".bar"]

    def load(self, path: Path) -> Document:  # type: ignore[override]
        # return a simple Document object for testing
        from kgbuilder.core.models import FileType

        return Document(
            id=str(path),
            content=f"loaded {path.name}",
            source_path=path,
            file_type=FileType.PDF,
        )


def test_register_and_get_loader(monkeypatch):
    # clear existing registrations to avoid interference
    DocumentLoaderFactory._loaders.clear()
    DocumentLoaderFactory.register(FakeLoader)

    loader = DocumentLoaderFactory.get_loader(Path("/tmp/test.foo"))
    assert isinstance(loader, FakeLoader)
    # Document has 'content' field
    assert loader.load(Path("a.foo")).content == "loaded a.foo"

    # unsupported suffix should raise
    with pytest.raises(UnsupportedFormatError):
        DocumentLoaderFactory.get_loader(Path("/tmp/not_supported.xyz"))


def test_load_and_load_batch(monkeypatch, tmp_path):
    # ensure factory has fake loader registered
    DocumentLoaderFactory._loaders.clear()
    DocumentLoaderFactory.register(FakeLoader)

    p1 = tmp_path / "one.foo"
    p1.write_text("dummy")
    p2 = tmp_path / "two.bar"
    p2.write_text("dummy")
    p3 = tmp_path / "bad.baz"
    p3.write_text("bad")

    # load single
    doc = DocumentLoaderFactory.load(p1)
    assert "one.foo" in doc.id

    # load_batch should include only supported docs and skip bad one
    docs = DocumentLoaderFactory.load_batch([p1, p2, p3])
    assert len(docs) == 2
    ids = {d.id for d in docs}
    assert any("one.foo" in i for i in ids)
    assert any("two.bar" in i for i in ids)


def _make_fake_pdf_module(pages_text):
    class DummyPDFPage:
        def __init__(self, text):
            self._text = text

        def extract_text(self):
            return self._text

    class DummyPDF:
        def __init__(self, pages):
            self.pages = [DummyPDFPage(t) for t in pages]

    class DummyPDFContext:
        def __init__(self, path):
            self._pdf = DummyPDF(pages_text)

        def __enter__(self):
            return self._pdf

        def __exit__(self, exc_type, exc, tb):
            return False

    fake = types.SimpleNamespace(open=lambda p: DummyPDFContext(p))
    return fake


# --- PDFLoader tests ------------------------------------------------------

class DummyLoaderException(Exception):
    pass


def test_pdf_loader_import_and_simple(monkeypatch, tmp_path: Path):
    loader = PDFLoader()
    monkeypatch.setitem(sys.modules, "pdfplumber", None)
    with pytest.raises(DocumentLoadError):
        loader.load(tmp_path / "ignore.pdf")

    fake = _make_fake_pdf_module(["foo", "bar"])
    monkeypatch.setitem(sys.modules, "pdfplumber", fake)
    doc = loader.load(tmp_path / "f.pdf")
    assert "foo" in doc.content and "bar" in doc.content
    assert doc.metadata.page_count == 2


def test_pdf_loader_batch_and_error(monkeypatch, tmp_path: Path):
    loader = PDFLoader()
    fake = _make_fake_pdf_module(["x"])
    monkeypatch.setitem(sys.modules, "pdfplumber", fake)

    paths = [tmp_path / "a.pdf", tmp_path / "b.pdf"]
    docs = loader.load_batch(paths)
    assert len(docs) == 2

    class BadContext:
        def __init__(self, p):
            pass
        def __enter__(self):
            raise RuntimeError("boom")
        def __exit__(self, *args):
            return False
    monkeypatch.setitem(sys.modules, "pdfplumber", types.SimpleNamespace(open=lambda p: BadContext(p)))
    assert loader.load_batch(paths) == []


# --- Office loaders ------------------------------------------------------
# helpers for office loader tests

def _make_docx(paragraphs: list[str]):
    return types.SimpleNamespace(paragraphs=[types.SimpleNamespace(text=t) for t in paragraphs])


def _make_pptx(slides: list[str]):
    slide_objs = []
    for txt in slides:
        slide_objs.append(types.SimpleNamespace(shapes=[types.SimpleNamespace(text=txt)]))
    return types.SimpleNamespace(slides=slide_objs)


def test_docx_and_pptx_loading(monkeypatch, tmp_path: Path):
    # DOCX import failure
    loaderx = DOCXLoader()
    monkeypatch.setitem(sys.modules, "docx", None)
    with pytest.raises(DocumentLoadError):
        loaderx.load(tmp_path / "f.docx")

    fake_docx = types.SimpleNamespace(Document=lambda p: _make_docx(["a", "b"]))
    monkeypatch.setitem(sys.modules, "docx", fake_docx)
    doc = loaderx.load(tmp_path / "f.docx")
    assert "a" in doc.content and "b" in doc.content

    # PPTX import failure
    loaderp = PPTXLoader()
    monkeypatch.setitem(sys.modules, "pptx", None)
    with pytest.raises(DocumentLoadError):
        loaderp.load(tmp_path / "f.pptx")

    fake_pptx = types.SimpleNamespace(Presentation=lambda p: _make_pptx(["s1"]))
    monkeypatch.setitem(sys.modules, "pptx", fake_pptx)
    doc2 = loaderp.load(tmp_path / "f.pptx")
    assert "s1" in doc2.content


def test_office_loader_batches(monkeypatch, tmp_path: Path):
    loaderx = DOCXLoader()
    loaderp = PPTXLoader()
    fake_docx = types.SimpleNamespace(Document=lambda p: _make_docx(["z"]))
    fake_pptx = types.SimpleNamespace(Presentation=lambda p: _make_pptx(["q"]))
    monkeypatch.setitem(sys.modules, "docx", fake_docx)
    monkeypatch.setitem(sys.modules, "pptx", fake_pptx)
    docsx = loaderx.load_batch([tmp_path / "a.docx"])
    docsp = loaderp.load_batch([tmp_path / "a.pptx"])
    assert len(docsx) == 1
    assert len(docsp) == 1
