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

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Return the name of the tool.

        The name should be unique and descriptive of the tool's function.
        It will be used by agents to identify and invoke the tool.

        Returns:
            A string containing the tool's name
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Return a description of what the tool does.

        This description will be used by agents to understand the tool's
        purpose and decide when to use it.

        Returns:
            A string describing the tool's functionality
        """
        pass

    @property
    @abstractmethod
    def args_schema(self) -> Type[BaseModel]:
        """
        Return the schema for the tool's arguments.

        This defines what arguments the tool accepts and their types.

        Returns:
            A dictionary mapping their parameter definitions
        """
        pass

    @property
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

    async def _arun(self, **kwargs) -> Any:
        # Optional: unify LangChain's interface with your own
        return await self.run(**kwargs)

    def _run(self, **kwargs) -> Any:
        # LangChain requires this; optionally wrap sync call
        import asyncio

        return asyncio.run(self.run(**kwargs))
