"""Tests for BaseAgent skill/tool registry and the LangChain ReAct adapter."""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from kgbuilder.agents.base_agent import BaseAgent, LangChainReactAgent
from kgbuilder.skills.base import AgentSkill
from kgbuilder.tools.base import AgentTool


class _FakeToolCallingChatModel(BaseChatModel):
    """Minimal fake chat model that answers immediately without calling tools."""

    def bind_tools(self, tools: Any, *, tool_choice: str | None = None, **kwargs: Any) -> "_FakeToolCallingChatModel":
        return self

    def _generate(self, messages: list[BaseMessage], stop: list[str] | None = None, **kwargs: Any) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="42"))])

    @property
    def _llm_type(self) -> str:
        return "fake-tool-calling-chat-model"



class _EchoAgent(BaseAgent):
    """Minimal concrete BaseAgent for exercising the registry."""

    def run(self, prompt: str, **kwargs: object) -> str:
        return f"echo:{prompt}"


@pytest.fixture
def sample_skill() -> AgentSkill:
    return AgentSkill(name="greet", description="Return a greeting", handler=lambda name: f"hello {name}")


@pytest.fixture
def sample_tool() -> AgentTool:
    return AgentTool(
        name="double",
        description="Double a number",
        parameters={"type": "object", "properties": {"value": {"type": "integer"}}},
        handler=lambda value: value * 2,
    )


def test_base_agent_runs_registered_skill(sample_skill: AgentSkill) -> None:
    agent = _EchoAgent(name="test_agent", skills=[sample_skill])
    assert agent.run_skill("greet", name="Ada") == "hello Ada"


def test_base_agent_runs_registered_tool(sample_tool: AgentTool) -> None:
    agent = _EchoAgent(name="test_agent", tools=[sample_tool])
    assert agent.run_tool("double", value=21) == 42


def test_base_agent_unknown_skill_raises(sample_skill: AgentSkill) -> None:
    agent = _EchoAgent(name="test_agent", skills=[sample_skill])
    with pytest.raises(ValueError, match="Unknown skill"):
        agent.run_skill("missing")


def test_base_agent_unknown_tool_raises(sample_tool: AgentTool) -> None:
    agent = _EchoAgent(name="test_agent", tools=[sample_tool])
    with pytest.raises(ValueError, match="Unknown tool"):
        agent.run_tool("missing")


def test_langchain_react_agent_executes_with_tool(sample_tool: AgentTool) -> None:
    """LangChainReactAgent should wrap our tools and run a LangChain tool-calling loop end-to-end."""
    fake_llm = _FakeToolCallingChatModel()
    agent = LangChainReactAgent(name="react_agent", llm=fake_llm, tools=[sample_tool])

    result = agent.run("What is double of 21?")

    assert result is not None
    assert "messages" in result
