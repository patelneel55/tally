from abc import ABC
from abc import abstractmethod
from typing import Any
from typing import Type

from langchain.tools import BaseTool
from pydantic import BaseModel


class ITool(BaseTool, ABC):
    """
    Interface for tools that can be used by agents.

    Tools are the fundamental building blocks that agents use to interact with
    the system and perform specific tasks. Each tool has a name, description,
    and a run method that performs the actual work.
    """

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
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

        return asyncio.run(self.execute(**kwargs))

    async def _arun(self, **kwargs) -> Any:
        """
        Run the tool asynchronously.

        This is the preferred method for running the tool.
        """
        return await self.execute(**kwargs)


class BaseTool(ITool):
    """
    Base implementation of the ITool interface.

    This provides a common foundation for implementing tools.
    """

    def __init__(self, name: str, description: str, args_schema: Type[BaseModel]):
        super().__init__(name=name, description=description)
        self.name = name
        self.description = description
        self.args_schema: Type[BaseModel] = args_schema
