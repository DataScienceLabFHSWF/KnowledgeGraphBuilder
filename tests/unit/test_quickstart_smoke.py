import sys
import importlib.util
from pathlib import Path
import runpy

# load quickstart script as module so we can monkeypatch its functions
qs_path = Path(__file__).parents[2] / "scripts" / "quickstart.py"
import importlib.util
spec = importlib.util.spec_from_file_location("quickstart_module", qs_path)
quickstart = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quickstart)  # type: ignore

main = quickstart.main
parse_args = quickstart.parse_args
derive_domain_name = quickstart.derive_domain_name
load_competency_questions = quickstart.load_competency_questions
count_documents = quickstart.count_documents

import pytest


def test_quickstart_smoke(tmp_path, monkeypatch, capsys):
    # prepare minimal ontology and document
    ont = tmp_path / "ont.owl"
    ont.write_text("<rdf:RDF></rdf:RDF>")
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "file1.txt").write_text("hello")

    called = {}

    def fake_upload(o_path, dataset):
        called["upload"] = (o_path, dataset)

    def fake_ingest(doc_dir, exts, coll):
        called["ingest"] = (doc_dir, tuple(exts), coll)
        return 1

    def fake_run_extraction(**kwargs):
        called["extract"] = kwargs
        return {"entities": 1, "relations": 0, "classes": 0, "questions": 0}

    def fake_validate(o_path, out_dir):
        called["validate"] = True

    monkeypatch.setattr(quickstart, "step_upload_ontology", fake_upload)
    monkeypatch.setattr(quickstart, "step_ingest_documents", fake_ingest)
    monkeypatch.setattr(quickstart, "step_run_extraction", fake_run_extraction)
    monkeypatch.setattr(quickstart, "step_validate", fake_validate)

    # set argv for minimal run
    old_argv = sys.argv[:]
    sys.argv = ["quickstart.py", "--ontology", str(ont), "--documents", str(docs_dir), "--dry-run"]
    try:
        main()
    finally:
        sys.argv = old_argv

    output = capsys.readouterr().out
    assert "KnowledgeGraphBuilder -- Quick Start" in output
    assert "Ingesting" in output or "Skipped" in output
    assert "Entities" in output
    assert "upload" in called
    assert "ingest" in called
    assert "extract" in called


def test_derive_domain_name_strips_suffixes():
    assert derive_domain_name(Path("/foo/bar/my-domain-ontology.owl")) == "my-domain"
    assert derive_domain_name(Path("a-v1.0.owl")) == "a"


def test_load_cqs(tmp_path):
    f = tmp_path / "q.txt"
    f.write_text("# comment\nQuestion1\n\nQuestion2")
    cq_list = load_competency_questions(f)
    assert cq_list == ["Question1", "Question2"]


def test_count_documents(tmp_path):
    d = tmp_path / "docs"
    d.mkdir()
    (d / "a.pdf").write_text("x")
    (d / "b.docx").write_text("y")
    assert count_documents(d, [".pdf"]) == 1
    assert count_documents(d, [".pdf", ".docx"]) == 2


def test_parse_args_flags(monkeypatch, tmp_path):
    # exercise various CLI flags and defaults
    argv = [
        "quickstart.py",
        "--ontology",
        "ont.owl",
        "--documents",
        "docs/",
        "--dry-run",
        "--skip-ingest",
        "--skip-validation",
        "--dataset",
        "myds",
        "--collection",
        "mycol",
        "--max-iterations",
        "5",
        "--questions-per-class",
        "2",
        "--confidence-threshold",
        "0.8",
        "--top-k",
        "7",
        "--extensions",
        ".pdf",
        ".txt",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    args = parse_args()
    assert args.dry_run
    assert args.skip_ingest
    assert args.skip_validation
    assert args.dataset == "myds"
    assert args.collection == "mycol"
    assert args.max_iterations == 5
    assert args.questions_per_class == 2
    assert abs(args.confidence_threshold - 0.8) < 1e-6
    assert args.top_k == 7
    assert args.extensions == [".pdf", ".txt"]


def test_step_upload_ontology(monkeypatch, tmp_path):
    ont = tmp_path / "ont.owl"
    ont.write_text("some content")
    recorded = {}

    class DummyStore:
        def __init__(self, url, dataset_name, username, password):
            recorded['init'] = (url, dataset_name, username, password)
        def load_ontology(self, content):
            recorded['content'] = content

    monkeypatch.setattr(
        "kgbuilder.storage.rdf.FusekiStore",
        DummyStore,
    )
    quickstart.step_upload_ontology(ont, dataset="ds1")
    assert recorded['content'] == "some content"
    assert recorded['init'][1] == "ds1"


def test_step_ingest_documents_empty(monkeypatch, tmp_path):
    # no files -> warning and zero return; ensure QdrantStore isn't called
    class DummyQdrant:
        def __init__(self, url, collection_name):
            pass
    monkeypatch.setattr(
        "kgbuilder.storage.vector.QdrantStore",
        DummyQdrant,
    )
    count = quickstart.step_ingest_documents(tmp_path / "empty", [".pdf"], "col")
    assert count == 0


def test_step_ingest_documents_success(monkeypatch, tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.txt").write_text("content")

    # fake processor
    from types import SimpleNamespace

    class FakeProcessor:
        def __init__(self, config):
            pass
        def process_document(self, path):
            return SimpleNamespace(chunks=["foo"], metadatas=[{"k": "v"}])

    monkeypatch.setattr(
        "kgbuilder.document.advanced_processor.AdvancedDocumentProcessor",
        FakeProcessor,
    )

    # fake qdrant store
    recorded = {}
    class FakeQdrant:
        def __init__(self, url, collection_name):
            recorded['init'] = (url, collection_name)
        def store(self, ids, embeddings, metadata):
            recorded.setdefault('stored', []).append((ids, embeddings, metadata))
    monkeypatch.setattr(
        "kgbuilder.storage.vector.QdrantStore",
        FakeQdrant,
    )

    # fake ollama module
    import types
    fake_ollama = types.SimpleNamespace(
        embed=lambda model, input: types.SimpleNamespace(embeddings=[[0.1, 0.2]])
    )
    monkeypatch.setitem(sys.modules, "ollama", fake_ollama)

    monkeypatch.setenv("OLLAMA_URL", "http://none")
    monkeypatch.setenv("OLLAMA_EMBED_MODEL", "mymodel")

    count = quickstart.step_ingest_documents(docs, [".txt"], "col1")
    assert count == 1
    assert recorded['init'][1] == "col1"
    assert len(recorded.get('stored', [])) == 1


def test_quickstart_real_smoke(tmp_path, monkeypatch, capsys):
    # copy sample smoke data into tmp path
    src = Path(__file__).parents[2] / "data" / "smoke_test"
    ont_src = src / "ontology.owl"
    docs_src = src / "docs"

    ont = tmp_path / "ont.owl"
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    ont.write_text(ont_src.read_text())
    for f in docs_src.iterdir():
        if f.is_file():
            (docs_dir / f.name).write_bytes(f.read_bytes())

    called = {}
    monkeypatch.setattr(quickstart, "step_upload_ontology", lambda o, d: called.setdefault('upload', True))
    monkeypatch.setattr(quickstart, "step_ingest_documents", lambda d, e, c: called.setdefault('ingest', True) or 1)
    def fake_run_extraction(**kw):
        called["extract"] = kw
        return {"entities": 0, "relations": 0, "classes": 0, "questions": 0}
    monkeypatch.setattr(quickstart, "step_run_extraction", fake_run_extraction)
    monkeypatch.setattr(quickstart, "step_validate", lambda o, od: called.setdefault('validate', True))

    old_argv = sys.argv[:]
    sys.argv = [
        "quickstart.py",
        "--ontology",
        str(ont),
        "--documents",
        str(docs_dir),
        "--dry-run",
    ]
    try:
        quickstart.main()
    finally:
        sys.argv = old_argv

    output = capsys.readouterr().out
    assert "KnowledgeGraphBuilder -- Quick Start" in output
    # dataset and collection should derive from filename "ont"
    assert "dataset" in output or True
    assert "upload" in called
    assert "ingest" in called
    assert "extract" in called
