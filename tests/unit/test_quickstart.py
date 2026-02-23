import sys
import runpy
from pathlib import Path

# ensure src on path
sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

# load quickstart script as module namespace
_quickstart_ns = runpy.run_path(str(Path(__file__).parents[2] / "scripts" / "quickstart.py"))
parse_args = _quickstart_ns["parse_args"]


def test_parse_args_minimal(tmp_path):
    # create dummy files to satisfy required args
    ont = tmp_path / "ontology.owl"
    ont.write_text("<rdf/>")
    docs = tmp_path / "docs"
    docs.mkdir()

    # simulate command line arguments
    old_argv = sys.argv
    sys.argv = [old_argv[0], "--ontology", str(ont), "--documents", str(docs)]
    try:
        args = parse_args()
    finally:
        sys.argv = old_argv
    assert args.ontology == str(ont)
    assert args.documents == str(docs)
    assert args.max_iterations == 2
    assert not args.dry_run


def test_parse_args_additional_flags(tmp_path):
    ont = tmp_path / "on.owl"
    ont.write_text("")
    docs = tmp_path / "d"
    docs.mkdir()
    cqs = tmp_path / "q.txt"
    cqs.write_text("q1\n")

    old_argv = sys.argv
    sys.argv = [
        old_argv[0],
        "--ontology",
        str(ont),
        "--documents",
        str(docs),
        "--cqs",
        str(cqs),
        "--dry-run",
        "--verbose",
    ]
    try:
        args = parse_args()
    finally:
        sys.argv = old_argv
    assert args.cqs == str(cqs)
    assert args.dry_run
    assert args.verbose
