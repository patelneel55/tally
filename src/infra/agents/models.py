from abc import ABC, abstractmethod
from typing import Any, List

from infra.tools.models import ITool


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
