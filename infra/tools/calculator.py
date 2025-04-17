import logging
import numexpr
import math
from typing import ClassVar

from pydantic import BaseModel, Field

from infra.tools.base import BaseTool

logger = logging.getLogger(__name__)

class CalculatorNumExprInput(BaseModel):
    expr: str = Field(description="Python numexpr compatbile expression to be solved")

class CalculatorTool(BaseTool):
    """
    Performs mathematical calculations
    """

    _TOOL_NAME: ClassVar[str] = "math_tool"
    _TOOL_DESCRIPTION: ClassVar[str] = """
Calculate expression using Python's numexpr library.
Expression should be a single line mathematical expression
that solves the problem which should be a supported input for the
numexpr library.

Examples:
  "37593 * 67" for "37593 times 67"
  "37593**(1/5)" for "37593^(1/5)""
"""

    def __init__(self):
        super().__init__(
            name=self._TOOL_NAME,
            description=self._TOOL_DESCRIPTION,
            args_schema=CalculatorNumExprInput,
        )

    async def execute(self, **kwargs) -> str:
        """
        Run the calculator tool.

        Args:
            **kwargs: The arguments passed to the tool.

        Returns:
            str: The resulting expression.
        """
        logger.info(f"📌 TOOL EXECUTION: {self.name}")
        local_dict = {"pi": math.pi, "e": math.e}
        try:
            calculator_input = CalculatorNumExprInput(**kwargs)
            return str(
                numexpr.evaluate(
                    calculator_input.expr.strip(),
                    local_dict=local_dict,
                )
            )
        except Exception as e:
            logger.error(f"Error during Calculator: {e}", exc_info=True)
            raise
