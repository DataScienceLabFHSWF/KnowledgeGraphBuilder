#!/usr/bin/env python
"""Convert GraphQA benchmark_v3 schema to KGBuilder QA dataset schema.

Input schema (benchmark_v3): list of question objects with fields like
`question_id`, `question`, `expected_answer`, `difficulty`, `question_type`.

Output schema (KGBuilder): object with top-level `questions` list and each
question normalized to `id`, `question`, `expected_answers`, `query_type`,
`difficulty`, `tags`, `metadata`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _normalize_query_type(raw_type: str, question_text: str) -> str:
    """Map external question types to KGBuilder query types."""
    lowered_type = (raw_type or "").strip().lower()
    if lowered_type in {"entity_lookup", "factoid", "factual", "entity"}:
        return "entity"
    if lowered_type in {"relation", "relationship"}:
        return "relation"
    if lowered_type in {"count", "counting"}:
        return "count"
    if lowered_type in {"boolean", "yes_no"}:
        return "boolean"
    if lowered_type in {"complex", "multi_hop", "open"}:
        return "complex"

    text = question_text.lower()
    if text.startswith(("how many", "wie viele")):
        return "count"
    if text.startswith(("is ", "are ", "does ", "do ", "ist ", "sind ", "kann ", "können ")):
        return "boolean"
    return "entity"


def _to_expected_answers(value: Any) -> list[str]:
    if isinstance(value, str):
        value = value.strip()
        return [value] if value else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def convert_questions(raw_questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert benchmark_v3 questions into KGBuilder QA question objects."""
    converted: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_questions, start=1):
        question_id = str(item.get("question_id") or item.get("id") or f"q{idx:03d}")
        question_text = str(item.get("question") or item.get("text") or "").strip()
        if not question_text:
            continue

        expected_answers = _to_expected_answers(item.get("expected_answer"))
        if not expected_answers:
            expected_answers = _to_expected_answers(item.get("expected_answers"))

        difficulty_raw = item.get("difficulty", 1)
        try:
            difficulty = int(difficulty_raw)
        except (TypeError, ValueError):
            difficulty = 1

        question_type = str(item.get("question_type") or item.get("type") or "")
        query_type = _normalize_query_type(question_type, question_text)

        tags: list[str] = []
        for key in ("category", "question_type", "retrieval_complexity"):
            value = item.get(key)
            if value:
                as_str = str(value)
                if as_str not in tags:
                    tags.append(as_str)

        metadata: dict[str, Any] = {}
        for key in (
            "expected_entities",
            "expected_relations",
            "notes",
            "source",
            "category",
            "question_type",
            "retrieval_complexity",
        ):
            if key in item:
                metadata[key] = item[key]

        converted.append(
            {
                "id": question_id,
                "question": question_text,
                "expected_answers": expected_answers,
                "query_type": query_type,
                "difficulty": difficulty,
                "tags": tags,
                "metadata": metadata,
            }
        )

    return converted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert benchmark_v3 JSON to KGBuilder QA format")
    parser.add_argument("--input", type=Path, required=True, help="Input benchmark_v3 JSON file")
    parser.add_argument("--output", type=Path, required=True, help="Output KGBuilder QA JSON file")
    parser.add_argument("--name", type=str, default="GraphQA benchmark_v3", help="Dataset name")
    parser.add_argument(
        "--description",
        type=str,
        default="Converted from GraphQA benchmark_v3 for KGBuilder evaluation",
        help="Dataset description",
    )
    parser.add_argument("--source", type=str, default="GraphQA benchmark_v3", help="Dataset source label")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    with args.input.open() as f:
        data = json.load(f)

    raw_questions = data.get("questions", data) if isinstance(data, dict) else data
    if not isinstance(raw_questions, list):
        raise ValueError("Input JSON must be a list of questions or an object with 'questions'.")

    questions = convert_questions(raw_questions)
    output = {
        "name": args.name,
        "description": args.description,
        "version": "1.0",
        "source": args.source,
        "questions": questions,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as f:
        json.dump(output, f, indent=2)

    scored = sum(1 for q in questions if q["expected_answers"])
    open_ended = len(questions) - scored
    print(f"Converted {len(questions)} questions -> {args.output}")
    print(f"Scored questions: {scored}")
    print(f"Open-ended questions: {open_ended}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
