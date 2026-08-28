"""Markdown-driven skill/pipeline loader.

Lets a domain expert change *what the agent does and in what order* by
editing markdown files under `agentic_pipeline/`, without touching Python.

Each skill markdown file has YAML front matter (name, tool mapping, required
bindings, default kwargs) followed by a natural-language description body.
`pipeline.md` declares an ordered list of steps referencing those skills by
name. This module parses both into `PipelineStep` objects that
`PipelineAgent.run_plan()` can execute directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from kgbuilder.agents.pipeline_agent import PipelineStep
from kgbuilder.agents.registry import SKILL_REGISTRY

_FRONT_MATTER_DELIMITER = "---"


class MarkdownPipelineError(ValueError):
    """Raised when a skill or pipeline markdown file is invalid."""


@dataclass
class SkillDoc:
    """Parsed representation of a `skills/<name>.md` file."""

    name: str
    tool: str | None
    requires_binding: list[str]
    default_kwargs: dict[str, Any]
    description: str
    source_path: Path


def _split_front_matter(text: str, source: Path) -> tuple[dict[str, Any], str]:
    """Split a markdown file into (front_matter_dict, body_text)."""
    stripped = text.lstrip("\n")
    if not stripped.startswith(_FRONT_MATTER_DELIMITER):
        raise MarkdownPipelineError(f"{source}: missing YAML front matter (expected leading '---')")

    remainder = stripped[len(_FRONT_MATTER_DELIMITER):]
    end_index = remainder.find(f"\n{_FRONT_MATTER_DELIMITER}")
    if end_index == -1:
        raise MarkdownPipelineError(f"{source}: unterminated YAML front matter (missing closing '---')")

    raw_front_matter = remainder[:end_index]
    body = remainder[end_index + len(f"\n{_FRONT_MATTER_DELIMITER}"):].strip()

    try:
        front_matter = yaml.safe_load(raw_front_matter) or {}
    except yaml.YAMLError as exc:
        raise MarkdownPipelineError(f"{source}: invalid YAML front matter: {exc}") from exc

    if not isinstance(front_matter, dict):
        raise MarkdownPipelineError(f"{source}: front matter must be a YAML mapping")

    return front_matter, body


def load_skill_doc(path: Path) -> SkillDoc:
    """Parse a single `skills/<name>.md` file into a `SkillDoc`."""
    text = path.read_text(encoding="utf-8")
    front_matter, body = _split_front_matter(text, path)

    if "name" not in front_matter:
        raise MarkdownPipelineError(f"{path}: front matter missing required 'name' field")

    name = front_matter["name"]
    if name not in SKILL_REGISTRY:
        available = ", ".join(sorted(SKILL_REGISTRY))
        raise MarkdownPipelineError(
            f"{path}: skill '{name}' is not registered. Available skills: {available}"
        )

    return SkillDoc(
        name=name,
        tool=front_matter.get("tool"),
        requires_binding=list(front_matter.get("requires_binding") or []),
        default_kwargs=dict(front_matter.get("default_kwargs") or {}),
        description=body,
        source_path=path,
    )


def load_skill_docs(skills_dir: Path) -> dict[str, SkillDoc]:
    """Parse every `*.md` file in `skills_dir` into a name -> SkillDoc map."""
    docs: dict[str, SkillDoc] = {}
    for md_path in sorted(skills_dir.glob("*.md")):
        doc = load_skill_doc(md_path)
        docs[doc.name] = doc
    return docs


def load_pipeline(pipeline_path: Path, skills_dir: Path | None = None) -> list[PipelineStep]:
    """Parse `pipeline.md` into an ordered list of `PipelineStep` objects.

    Args:
        pipeline_path: Path to the pipeline markdown file.
        skills_dir: Directory containing skill markdown docs used to validate
            step references and fill in default kwargs. Defaults to a
            `skills/` sibling of `pipeline_path`.

    Returns:
        Ordered `PipelineStep` list ready for `PipelineAgent.run_plan()`.

    Raises:
        MarkdownPipelineError: If the file is malformed or references an
            unknown skill.
    """
    text = pipeline_path.read_text(encoding="utf-8")
    front_matter, _body = _split_front_matter(text, pipeline_path)

    raw_steps = front_matter.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise MarkdownPipelineError(f"{pipeline_path}: front matter must declare a non-empty 'steps' list")

    skills_dir = skills_dir or pipeline_path.parent / "skills"
    skill_docs = load_skill_docs(skills_dir) if skills_dir.is_dir() else {}

    steps: list[PipelineStep] = []
    for index, raw_step in enumerate(raw_steps):
        if not isinstance(raw_step, dict) or "skill" not in raw_step:
            raise MarkdownPipelineError(f"{pipeline_path}: step {index} must be a mapping with a 'skill' key")

        skill_name = raw_step["skill"]
        if skill_name not in SKILL_REGISTRY:
            available = ", ".join(sorted(SKILL_REGISTRY))
            raise MarkdownPipelineError(
                f"{pipeline_path}: step {index} references unknown skill "
                f"'{skill_name}'. Available skills: {available}"
            )

        default_kwargs = skill_docs[skill_name].default_kwargs if skill_name in skill_docs else {}
        merged_kwargs = {**default_kwargs, **dict(raw_step.get("kwargs") or {})}

        steps.append(
            PipelineStep(
                skill=skill_name,
                kwargs=merged_kwargs,
                bind=dict(raw_step.get("bind") or {}),
            )
        )

    return steps
