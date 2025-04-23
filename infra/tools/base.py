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

    def __init__(self, name: str, description: str, args_schema: Type[BaseModel]):
        super().__init__(name=name, description=description)
        self.name = name
        self.description = description
        self.args_schema: Type[BaseModel] = args_schema


class PipelineTool(BaseTool):
    """
    Tool implementation that wraps a pipeline.

    This allows existing pipelines to be used as tools by agents.
    """

    def __init__(
        self,
        name: str,
        description: str,
        args_schema: Type[BaseModel],
        arg_mapping: Dict[str, str] = None,
    ):
        """
        Initialize the pipeline tool.

        Args:
            name: The name of the tool
            description: A description of what the tool does
            pipeline: The pipeline instance to wrap
            arg_mapping: Optional mapping from tool args to pipeline args
        """
        super().__init__(name, description, args_schema)
        self._arg_mapping = arg_mapping or {}
        self._pipeline = None  # Lazy loading

    @property
    def pipeline(self):
        return self._pipeline

    @pipeline.setter
    def pipeline(self, value):
        self._pipeline = value

    async def execute(self, **kwargs) -> Any:
        """
        Run the wrapped pipeline with the provided arguments.

        Args:
            **kwargs: Arguments to pass to the pipeline

        Returns:
            The result of the pipeline execution
        """
        logger.info(f"📌 TOOL EXECUTION: {self.name}")

        # Map tool arguments to pipeline arguments if needed
        if self._arg_mapping:
            pipeline_kwargs = {}
            for tool_arg, pipeline_arg in self._arg_mapping.items():
                if tool_arg in kwargs:
                    pipeline_kwargs[pipeline_arg] = kwargs[tool_arg]
            kwargs = pipeline_kwargs

        # Run the pipeline
        try:
            result = await self._pipeline.run(**kwargs)
            logger.info(f"✅ TOOL COMPLETED: {self.name} successfully")
            return result
        except Exception as e:
            logger.error(f"❌ TOOL ERROR: {self.name} failed with error: {str(e)}")
            raise
