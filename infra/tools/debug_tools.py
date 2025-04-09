"""
Debug Tools
---------

This module provides tools specifically for debugging and observing agent behavior.
These tools are useful during development to understand what's happening.
"""

import json
import logging
import pprint
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel

from infra.tools.base import BaseTool

# Set up logging
logger = logging.getLogger(__name__)


class EchoTool(BaseTool):
    """
    Tool that simply echoes back its input with detailed logging.

    This tool is useful for debugging agent behavior, as it shows exactly what
    parameters were passed and how they were processed.
    """

    def __init__(self):
        """Initialize the echo tool."""
        super().__init__(
            name="echo_tool",
            description="Echo back the input with detailed logging. Use to debug argument handling.",
        )

    def args_schema(self) -> Type[BaseModel]:
        """
        Define the schema for the tool's arguments.

        Returns:
            A dictionary mapping argument names to their parameter definitions
        """
        return {
            "message": {
                "type": "string",
                "description": "The message to echo back",
                "required": True,
            },
            "metadata": {
                "type": "object",
                "description": "Optional metadata to include in the output",
                "required": False,
            },
        }

    async def run(
        self, message: str, metadata: Optional[Dict[str, Any]] = None, **kwargs
    ) -> str:
        """
        Echo back the input with detailed logging.

        Args:
            message: The message to echo back
            metadata: Optional metadata to include in the output
            **kwargs: Any other arguments

        Returns:
            A string containing the echoed message and metadata
        """
        # Log all inputs in detail
        logger.info(f"🔍 ECHO TOOL RECEIVED INPUT")
        logger.info(f"📝 Message: {message}")

        if metadata:
            logger.info(f"📋 Metadata:")
            formatted_metadata = pprint.pformat(metadata, indent=2)
            for line in formatted_metadata.split("\n"):
                logger.info(f"   {line}")

        if kwargs:
            logger.info(f"🔧 Additional kwargs:")
            formatted_kwargs = pprint.pformat(kwargs, indent=2)
            for line in formatted_kwargs.split("\n"):
                logger.info(f"   {line}")

        # Build response
        response = {
            "message": message,
            "metadata": metadata or {},
            "additional_args": kwargs,
        }

        # Log the response
        logger.info(f"↩️ ECHO TOOL RESPONSE: {json.dumps(response, indent=2)}")

        return json.dumps(response, indent=2)


# class TracingTool(BaseTool):
#     """
#     Tool that logs detailed execution trace information.

#     This tool helps understand the sequence of tool calls made by an agent
#     and can be used to trace execution paths.
#     """

#     def __init__(self, trace_id: str = "default"):
#         """
#         Initialize the tracing tool.

#         Args:
#             trace_id: An identifier for this trace
#         """
#         super().__init__(
#             name="trace",
#             description="Log a trace point in the agent's execution"
#         )
#         self.trace_id = trace_id
#         self.trace_points = []

#     def args_schema(self) -> BaseModel:
#         """
#         Define the schema for the tool's arguments.

#         Returns:
#             A dictionary mapping argument names to their parameter definitions
#         """
#         return {
#             "step_name": {
#                 "type": "string",
#                 "description": "Name of this trace point",
#                 "required": True
#             },
#             "data": {
#                 "type": "object",
#                 "description": "Data to log at this trace point",
#                 "required": False
#             }
#         }

#     async def run(self, step_name: str, data: Optional[Dict[str, Any]] = None) -> str:
#         """
#         Log a trace point in the agent's execution.

#         Args:
#             step_name: Name of this trace point
#             data: Data to log at this trace point

#         Returns:
#             A string confirming the trace point was logged
#         """
#         # Add trace point
#         trace_point = {
#             "step": step_name,
#             "data": data or {}
#         }
#         self.trace_points.append(trace_point)

#         # Log trace point
#         logger.info(f"🔍 TRACE [{self.trace_id}]: {step_name}")
#         if data:
#             formatted_data = pprint.pformat(data, indent=2)
#             for line in formatted_data.split('\n'):
#                 logger.info(f"   {line}")

#         return f"Trace point '{step_name}' logged (trace ID: {self.trace_id})"

#     def get_trace(self) -> List[Dict[str, Any]]:
#         """
#         Get the recorded trace.

#         Returns:
#             A list of trace points
#         """
#         return self.trace_points
