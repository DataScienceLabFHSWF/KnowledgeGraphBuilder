"""Base agent abstractions for the KGBuilder agent stack."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from kgbuilder.skills.base import AgentSkill
from kgbuilder.tools.base import AgentTool


class BaseAgent(ABC):
    """Minimal base class for skill- and tool-driven agents."""

    def __init__(
        self,
        name: str,
        skills: list[AgentSkill] | None = None,
        tools: list[AgentTool] | None = None,
    ) -> None:
        self.name = name
        self.skills = list(skills or [])
        self.tools = list(tools or [])
        self._skill_registry = {skill.name: skill for skill in self.skills}
        self._tool_registry = {tool.name: tool for tool in self.tools}

    def run_skill(self, skill_name: str, **kwargs: Any) -> Any:
        """Execute a named skill exposed by the agent."""
        if skill_name not in self._skill_registry:
            available = ", ".join(sorted(self._skill_registry))
            raise ValueError(f"Unknown skill '{skill_name}'. Available skills: {available}")
        return self._skill_registry[skill_name].execute(**kwargs)

    def run_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Execute a named tool exposed by the agent."""
        if tool_name not in self._tool_registry:
            available = ", ".join(sorted(self._tool_registry))
            raise ValueError(f"Unknown tool '{tool_name}'. Available tools: {available}")
        return self._tool_registry[tool_name].execute(**kwargs)

    @abstractmethod
    def run(self, prompt: str, **kwargs: Any) -> Any:
        """Run the agent against a prompt or task description."""


class LangChainReactAgent(BaseAgent):
    """Thin LangChain agent adapter around a tool/skill-based agent.

    Uses LangChain 1.x's `create_agent` (LangGraph tool-calling loop), which
    replaced the legacy `AgentExecutor` / `create_react_agent` API.
    """

    def __init__(
        self,
        name: str,
        llm: Any,
        skills: list[AgentSkill] | None = None,
        tools: list[AgentTool] | None = None,
        system_prompt: str | None = None,
    ) -> None:
        super().__init__(name=name, skills=skills, tools=tools)
        self.llm = llm
        self._graph = None

        try:
            from langchain.agents import create_agent
            from langchain_core.tools import Tool
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("LangChain is required for LangChainReactAgent") from exc

        langchain_tools = [
            Tool(name=tool.name, func=tool.execute, description=tool.description)
            for tool in self.tools
        ]

        self._graph = create_agent(
            model=self.llm,
            tools=langchain_tools,
            system_prompt=system_prompt or f"You are {name}. Use the supplied tools to answer the user request.",
        )

    def run(self, prompt: str, **kwargs: Any) -> Any:
        """Execute the underlying LangChain tool-calling agent graph."""
        if self._graph is None:
            raise RuntimeError("LangChain agent graph was not initialized")
        return self._graph.invoke({"messages": [{"role": "user", "content": prompt}]}, **kwargs)
