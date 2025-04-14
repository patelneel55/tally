import logging
from typing import ClassVar

from infra.tools.base import BaseTool

# Set up logging
logger = logging.getLogger(__name__)

class VectorSearchTool(BaseTool):
    
    _TOOL_NAME: ClassVar[str] = "vector_search"
    _TOOL_DESCRIPTION: ClassVar[str] = """
"""