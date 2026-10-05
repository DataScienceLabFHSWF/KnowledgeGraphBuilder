#!/usr/bin/env python3
"""Run the expanded development matrix sequentially and publish each completed report."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.request import urlopen


def main() -> None:
    """Run all configurations with durable status, logs, and per-run exports."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--publish-dir", type=Path, default=Path("Planning/benchmarks/expanded"))
    parser.add_argument("--corpus-dir", type=Path, default=Path("data/Decommissioning_Files"))
    parser.add_argument("--ollama-url", default="http://localhost:18134")
    parser.add_argument("--ollama-model", default="qwen3:8b")
    parser.add_argument("--vllm-url", default="http://localhost:8000/v1")
    parser.add_argument("--decision-url", default="http://localhost:11436")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--paragraphs", type=int, default=10)
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable for workers; set explicitly when detaching from a virtualenv.",
    )
    parser.add_argument("--stop-containers", nargs="*", default=[])
    args = parser.parse_args()
    if args.repeats < 1 or args.paragraphs < 1:
        parser.error("Repeats and paragraphs must be positive")
    documents = len(list(args.corpus_dir.glob("*.pdf")))
    if not documents:
        parser.error("No PDFs found in --corpus-dir")
    configurations = [
        ("rules-only", "ollama", "rules", "rules", False),
        ("gliner-rules", "ollama", "gliner", "rules", False),
        ("gliner-tev1", "ollama", "gliner", "decision", False),
        ("kolibri-llm", "vllm", "llm", "llm", False),
        ("kolibri-tev1-judge", "vllm", "llm", "llm", True),
        ("kolibri-entities-tev1", "vllm", "llm", "decision", False),
        ("gliner-kolibri", "vllm", "gliner", "llm", False),
        ("kolibri-rules-first", "vllm", "rules-first", "rules-first", False),
        ("qwen-llm", "ollama", "llm", "llm", False),
        ("gliner-qwen", "ollama", "gliner", "llm", False),
    ]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    status_path = args.output_dir / "matrix-status.json"
    status: dict[str, Any] = {
        "created_at": datetime.now(UTC).isoformat(),
        "scope": {
            "labeled_items": 22,
            "repeats": args.repeats,
            "corpus_documents": documents,
            "passages_per_document_limit": args.paragraphs,
        },
        "runs": [],
    }

    def save_status() -> None:
        temporary = status_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
        temporary.replace(status_path)

    save_status()
    environment = {
        **os.environ,
        "VLLM_BASE_URL": args.vllm_url,
        "HF_HUB_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "PYTHONUNBUFFERED": "1",
    }
    environment.pop("LLM_TEMPERATURE", None)
    environment.pop("LLM_TOP_P", None)
    failures = 0
    try:
        subprocess.run(
            [args.python, "-c", "import kgbuilder.api.dependencies"],
            env=environment,
            check=True,
        )
        with urlopen(f"{args.vllm_url.removesuffix('/v1')}/health", timeout=15) as response:
            if response.status != 200:
                raise RuntimeError("vLLM health check did not return HTTP 200")
        with urlopen(f"{args.ollama_url}/api/tags", timeout=15) as response:
            models = json.load(response)["models"]
        revision = next(model["digest"] for model in models if model["name"] == args.ollama_model)
        with urlopen(f"{args.decision_url}/api/tags", timeout=15) as response:
            decision_models = json.load(response)["models"]
        decision_revision = next(
            model["digest"] for model in decision_models if model["name"] == "tev1:0.8b"
        )
        for name, backend, entity, relation, judge in configurations:
            record: dict[str, Any] = {"name": name, "status": "running"}
            status["runs"].append(record)
            save_status()
            output = args.output_dir / f"kg-extraction-{name}.json"
            command = [
                args.python,
                "scripts/benchmark_kg_extraction.py",
                "--backend",
                backend,
                "--entity-extractor",
                entity,
                "--relation-extractor",
                relation,
                "--repeats",
                str(args.repeats),
                "--warmup",
                "1",
                "--corpus-probe",
                "--corpus-dir",
                str(args.corpus_dir),
                "--corpus-documents",
                str(documents),
                "--corpus-paragraphs",
                str(args.paragraphs),
                "--output",
                str(output),
                "--decision-base-url",
                args.decision_url,
                "--model",
                "Aleph-Alpha/Kolibri-1" if backend == "vllm" else args.ollama_model,
                "--ollama-base-url",
                args.ollama_url,
                "--decision-model-revision",
                decision_revision,
                "--model-revision",
                "e52eb4627d11516b0c01de49210ab5a4e4061444" if backend == "vllm" else revision,
            ]
            if judge:
                command.append("--decision-judge")
            print(f"Starting {name}", flush=True)
            with (args.output_dir / f"{name}.log").open("w", encoding="utf-8") as log:
                completed = subprocess.run(command, env=environment, stdout=log, stderr=log)
            record["exit_code"] = completed.returncode
            record["completed_at"] = datetime.now(UTC).isoformat()
            if completed.returncode:
                record["status"] = "failed"
                failures += 1
            else:
                report = json.loads(output.read_text(encoding="utf-8"))
                record["extraction_errors"] = report["aggregate"]["errors"]
                record["corpus_errors"] = len(report["unlabeled_corpus_probe"]["errors"])
                record["status"] = (
                    "completed_with_errors"
                    if record["extraction_errors"] or record["corpus_errors"]
                    else "completed"
                )
                subprocess.run(
                    [
                        args.python,
                        "scripts/publish_extraction_reports.py",
                        "--input-dir",
                        str(args.output_dir),
                        "--output-dir",
                        str(args.publish_dir),
                    ],
                    check=True,
                )
            save_status()
            print(f"Finished {name}: {record['status']}", flush=True)
        status["status"] = (
            "completed_with_failures"
            if failures
            else "completed_with_errors"
            if any(run["status"] == "completed_with_errors" for run in status["runs"])
            else "completed"
        )
    except Exception as exc:
        status["status"] = "failed"
        status["error"] = str(exc)
        raise
    finally:
        status["finished_at"] = datetime.now(UTC).isoformat()
        save_status()
        for container in args.stop_containers:
            subprocess.run(["docker", "stop", container], check=True)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
