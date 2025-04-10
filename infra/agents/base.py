"""
Agent Base Interfaces
------------------

This module defines the base interfaces for agents that can use tools to perform tasks.
Agents are the intelligent components that decide which tools to use and in what order.
"""

import datetime
import logging
import os
from typing import Any, List, Optional

from langchain.agents import AgentType, initialize_agent
from langchain.callbacks import FileCallbackHandler, StdOutCallbackHandler
from langchain.callbacks.manager import CallbackManager

from infra.agents.interfaces import IAgent
from infra.core.interfaces import ILLMProvider
from infra.tools.base import ITool

# Set up logging
logger = logging.getLogger(__name__)


class BaseAgent(IAgent):
    """
    Base implementation of the IAgent interface.

    This provides a common foundation for implementing agents.
    """

    def __init__(self, llm_provider: ILLMProvider):
        """
        Initialize the agent.

        Args:
            llm_provider: Provider for the LLM to use for decision making
        """
        self.llm_provider = llm_provider
        self.tools: List[ITool] = []

    def add_tool(self, tool: ITool) -> None:
        """
        Add a tool to the agent's toolset.

        Args:
            tool: The tool to add
        """
        self.tools.append(tool)

    def get_tools(self) -> List[ITool]:
        """
        Get all tools available to this agent.

        Returns:
            A list of tools available to the agent
        """
        return self.tools


class LangChainAgent(BaseAgent):
    """
    Agent implementation that uses LangChain's agent framework.

    This agent uses LangChain's built-in agent types and tools.
    """

    def __init__(
        self,
        llm_provider: ILLMProvider,
        agent_type: str = "openai-functions",
        verbose: bool = False,
        debug: bool = False,
    ):
        """
        Initialize the LangChain agent.

        Args:
            llm_provider: Provider for the LLM to use for decision making
            agent_type: Type of LangChain agent to use
            verbose: Whether to enable verbose output in the LangChain agent
            debug: Whether to enable additional detailed debug logging
        """
        super().__init__(llm_provider)
        self.agent_type = agent_type
        self.verbose = verbose
        self.debug = debug
        self.agent = None

    async def run(self, task: str, **kwargs) -> Any:
        """
        Run the agent on a specific task.

        The agent will use its tools to accomplish the task.

        Args:
            task: The task to perform
            **kwargs: Additional arguments for the agent

        Returns:
            The result of the agent's execution
        """
        logger.info(f"🧠 Running agent with task: {task}")
        # Set up callback handlers for enhanced logging
        callbacks = []

        # Always add stdout handler if verbose is True
        if self.verbose:
            callbacks.append(StdOutCallbackHandler())

        # Add file logging if debug mode is enabled
        if self.debug:
            # Create logs directory if it doesn't exist
            os.makedirs("logs", exist_ok=True)

            # Create timestamped log file
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = f"logs/agent_run_{timestamp}.log"

            callbacks.append(FileCallbackHandler(log_file))
            logger.info(f"Debug logging enabled, writing to {log_file}")

        # Create callback manager if we have callbacks
        callback_manager = CallbackManager(callbacks) if callbacks else None

        tool_names = [tool.name for tool in self.tools]
        logger.info(f"🧰 Agent equipped with tools: {', '.join(tool_names)}")
        logger.info(f"🤖 Starting agent execution for task: {task}")

        # Initialize the LangChain agent
        llm = self.llm_provider.get_model()

        # Map our agent_type to LangChain's AgentType
        agent_type_map = {
            "openai-functions": AgentType.OPENAI_FUNCTIONS,
            "react-docstore": AgentType.REACT_DOCSTORE,
            "zero-shot-react-description": AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            "conversational-react-description": AgentType.CONVERSATIONAL_REACT_DESCRIPTION,
        }
        agent_type = agent_type_map.get(self.agent_type, AgentType.OPENAI_FUNCTIONS)

        # Initialize the agent with callbacks
        agent = initialize_agent(
            tools=self.tools,
            llm=llm,
            agent=agent_type,
            verbose=self.verbose,
            callback_manager=callback_manager,
        )

        # Run the agent
        try:
            result = await agent.ainvoke(task)
            logger.info(f"✅ Agent completed task successfully")
            return result
        except Exception as e:
            logger.error(f"❌ Agent execution failed: {str(e)}")
            raise
