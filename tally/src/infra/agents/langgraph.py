"""
LangGraph Agent
--------------

This module provides an agent implementation using LangGraph for structured workflow
and ReAct prompting for reasoning through complex tasks.
"""

import logging
from typing import Any
from typing import Dict
from typing import List

from langchain.prompts import SystemMessagePromptTemplate
from langgraph.prebuilt import create_react_agent

from infra.agents.models import IAgent
from infra.llm.models import ILLMProvider
from infra.tools.models import ITool


# Set up logging
logger = logging.getLogger(__name__)


class LangGraphReActAgent(IAgent):
    """
    Agent implementation using LangGraph for structured reasoning workflows.

    This agent uses the ReAct (Reasoning and Acting) approach to break down complex
    queries into smaller sub-tasks, interact with tools, and maintain focus on the
    original objective throughout the process.
    """

    def __init__(
        self,
        llm_provider: ILLMProvider,
        base_prompt: SystemMessagePromptTemplate = "",
        verbose: bool = False,
        max_iterations: int = 15,
        tools: List[ITool] = [],
    ):
        """
        Initialize the LangGraph agent.

        Args:
            llm_provider: Provider for the LLM to use for decision making
            verbose: Whether to enable verbose logging
            max_iterations: Maximum number of iterations for the agent
        """
        self.llm_provider = llm_provider
        self.verbose = verbose
        self.max_iterations = max_iterations
        self._tools: Dict[str, ITool] = {tool.name: tool for tool in tools}
        self._graph = None  # Lazy initialization
        self._system_prompt = base_prompt

    def add_tools(self, tools: List[ITool]) -> None:
        """
        Add a tool to the agent's toolset.

        Args:
            tool: The tool to add
        """
        for tool in tools:
            if tool.name not in self._tools:
                self._tools[tool.name] = tool

    def get_tools(self) -> List[ITool]:
        """
        Get all tools available to this agent.

        Returns:
            A list of tools available to the agent
        """
        return self.tools

    def build_agent(self) -> Any:
        """
        Create the LangGraph workflow for ReAct agent execution.

        Returns:
            An initialized StateGraph for execution
        """
        llm = self.llm_provider.get_model()

        # Use LangGraph's prebuilt function to create the agent logic
        # This typically binds the tools to the LLM for function calling
        # and includes logic to parse the LLM response into actions or finish states.
        try:
            agent = create_react_agent(
                model=llm,
                tools=list(self._tools.values()),
                prompt=self._system_prompt.format(),
            )
            logger.debug(
                f"Runnable agent created successfully for {self.__class__.__name__}."
            )
            return agent
        except Exception as e:
            logger.error(
                f"Failed to build agent runnable for {self.__class__.__name__}: {e}",
                exc_info=True,
            )
            # Depending on desired behavior, re-raise or return None/handle error
            raise RuntimeError(
                f"Could not build runnable for {self.__class__.__name__}"
            ) from e
