"""
Tool Base Interfaces
------------------

This module defines the base interfaces for tools that can be used by LLM agents.
Tools are the building blocks for agents to interact with the system and perform
specific tasks.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, TypedDict, Union

from langchain.tools import BaseTool
from pydantic import BaseModel

# Set up logging
logger = logging.getLogger(__name__)


class ITool(BaseTool, ABC):
    """
    Interface for tools that can be used by agents.

    Tools are the fundamental building blocks that agents use to interact with
    the system and perform specific tasks. Each tool has a name, description,
    and a run method that performs the actual work.
    """

    # def __init__(self, name: str, description: str):
    #     """
    #     Initialize the tool.
    #     """
    #     # Initialize the parent class without validation
    #     super().__init__()

    # @abstractmethod
    # def args_schema(self) -> BaseModel:
    #     """
    #     Return the schema for the tool's arguments.

    #     This defines what arguments the tool accepts and their types.

    #     Returns:
    #         A dictionary mapping their parameter definitions
    #     """
    #     pass

    @abstractmethod
    async def run(self, **kwargs) -> Any:
        """
        Execute the tool with the provided arguments.

        This is where the tool's actual functionality is implemented.

        Args:
            **kwargs: The arguments to pass to the tool

        Returns:
            The result of the tool's execution

        Raises:
            ValueError: If the arguments are invalid
            Exception: If the tool execution fails
        """
        pass

    def _run(self, **kwargs) -> Any:
        """
        Run the tool synchronously.

        This is required by LangChain's BaseTool, but we'll just call the async version.
        """
        import asyncio

        return asyncio.run(self.run(**kwargs))

    async def _arun(self, **kwargs) -> Any:
        """
        Run the tool asynchronously.

        This is the preferred method for running the tool.
        """
        return await self.run(**kwargs)
