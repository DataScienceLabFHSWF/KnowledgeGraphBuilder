"""Tests for agent-swarm model/concurrency configuration."""

from __future__ import annotations

from unittest.mock import MagicMock

from kgbuilder.agents.question_generator import CQType, ResearchQuestion
from kgbuilder.agents.swarm_config import (
    SwarmModelConfig,
    build_module_bindings_with_swarm_config,
)


def test_swarm_model_config_resolves_per_module_model_with_fallback() -> None:
    config = SwarmModelConfig(
        default_model="qwen3:8b",
        module_models={"Assets and Locations": "qwen3:1.7b"},
    )

    assert config.model_for_module("Assets and Locations") == "qwen3:1.7b"
    assert config.model_for_module("Unmapped Module") == "qwen3:8b"


def test_swarm_model_config_round_trips_through_dict() -> None:
    config = SwarmModelConfig(
        backend="vllm",
        base_url="http://localhost:8000/v1",
        default_model="llama3.1:8b",
        module_models={"Waste and Materials": "llama3.1:8b-instruct-q4"},
        max_concurrent_agents=6,
    )

    restored = SwarmModelConfig.from_dict(config.to_dict())

    assert restored == config


def test_build_module_bindings_with_swarm_config_shares_resources_per_model() -> None:
    questions = [
        ResearchQuestion(
            question_id="qa", text="Which facilities exist?", entity_class="Facility",
            priority=1.0, reason="r", cq_type=CQType.SCQ,
        ),
        ResearchQuestion(
            question_id="qb", text="What documents exist?", entity_class="Document",
            priority=1.0, reason="r", cq_type=CQType.SCQ,
        ),
    ]
    module_map = {
        "Assets and Locations": ["Facility"],
        "Document Structure and Evidence": ["Document"],
    }
    swarm_config = SwarmModelConfig(
        default_model="qwen3:8b",
        module_models={"Assets and Locations": "qwen3:1.7b"},
    )

    retriever_factory = MagicMock(side_effect=lambda model: f"retriever-{model}")
    extractor_factory = MagicMock(side_effect=lambda model: f"extractor-{model}")

    bindings = build_module_bindings_with_swarm_config(
        module_map=module_map,
        questions=questions,
        retriever_factory=retriever_factory,
        extractor_factory=extractor_factory,
        swarm_config=swarm_config,
    )

    by_module = {b.module_name: b for b in bindings}
    assert by_module["Assets and Locations"].extractor == "extractor-qwen3:1.7b"
    assert by_module["Document Structure and Evidence"].extractor == "extractor-qwen3:8b"
    # One factory call per distinct model, not per module.
    assert extractor_factory.call_count == 2
