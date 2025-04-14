import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from infra.core.interfaces import ILLMProvider
from infra.tools.base import ITool


class IAgent(ABC):
    """
    Interface for agents that can use tools to perform tasks.

    Agents are responsible for deciding which tools to use and in what order
    to accomplish a given task. They use an LLM to make these decisions.
    """

    @abstractmethod
    def add_tools(self, tools: List[ITool]) -> None:
        """
        Add a tool to the agent's toolset.

        Args:
            tool: The tool to add
        """
        pass

    @abstractmethod
    def get_tools(self) -> List[ITool]:
        """
        Get all tools available to this agent.

        Returns:
            A list of tools available to the agent
        """
        pass

    @abstractmethod
    def build_agent(self) -> Any:
        """
        Build the AI agent based on the provided tools
        and prompts
        """
        pass

    # @abstractmethod
    # async def run(self, task: str, **kwargs) -> Any:
    #     """
    #     Run the agent on a specific task.

    #     The agent will use its tools to accomplish the task.

    #     Args:
    #         task: The task to perform
    #         **kwargs: Additional arguments for the agent

    #     Returns:
    #         The result of the agent's execution
    #     """
    #     pass
