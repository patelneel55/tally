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

from pydantic import BaseModel, Field

from infra.tools.interfaces import ITool

# Set up logging
logger = logging.getLogger(__name__)


class BaseTool(ITool):
    """
    Base implementation of the ITool interface.

    This provides a common foundation for implementing tools.
    """

    def __init__(self, name: str, description: str):
        super().__init__()
        self._name = name
        self._description = description

    def name(self) -> str:
        return self._name

    def description(self) -> str:
        return self._description

class PipelineTool(BaseTool):
    """
    Tool implementation that wraps a pipeline.

    This allows existing pipelines to be used as tools by agents.
    """

    def __init__(
        self, name: str, description: str, pipeline, arg_mapping: Dict[str, str] = None
    ):
        """
        Initialize the pipeline tool.

        Args:
            name: The name of the tool
            description: A description of what the tool does
            pipeline: The pipeline instance to wrap
            arg_mapping: Optional mapping from tool args to pipeline args
        """
        super().__init__(name, description)
        self.pipeline = pipeline
        self.arg_mapping = arg_mapping or {}

    def args_schema(self) -> Type[BaseModel]:
        """
        Implement in subclasses to define the specific arguments for the pipeline.
        """
        raise NotImplementedError("Subclasses must implement args_schema")

    async def run(self, **kwargs) -> Any:
        """
        Run the wrapped pipeline with the provided arguments.

        Args:
            **kwargs: Arguments to pass to the pipeline

        Returns:
            The result of the pipeline execution
        """
        logger.info(f"📌 TOOL EXECUTION: {self.name()} with args: {kwargs}")

        # Map tool arguments to pipeline arguments if needed
        if self.arg_mapping:
            pipeline_kwargs = {}
            for tool_arg, pipeline_arg in self.arg_mapping.items():
                if tool_arg in kwargs:
                    pipeline_kwargs[pipeline_arg] = kwargs[tool_arg]
            kwargs = pipeline_kwargs

        # Run the pipeline
        try:
            result = await self.pipeline.run(**kwargs)
            logger.info(f"✅ TOOL COMPLETED: {self.name()} successfully")
            return result
        except Exception as e:
            logger.error(f"❌ TOOL ERROR: {self.name()} failed with error: {str(e)}")
            raise
