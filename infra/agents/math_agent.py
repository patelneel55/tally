import logging
from typing import Any, Dict, List, Optional, TypedDict, Union, cast

from langchain.prompts import BasePromptTemplate, ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate

from infra.agents.interfaces import IAgent
from infra.tools.base import ITool
from infra.core.interfaces import ILLMProvider
from infra.agents.langgraph import LangGraphReActAgent
from infra.tools.calculator import CalculatorTool


# Set up logging
logger = logging.getLogger(__name__)

class MathAgent(LangGraphReActAgent):

    AGENT_NAME = "FinancialMathExpert"
    SYSTEM_MESSAGE = """
You are a specialized AI assistant highly skilled in financial mathematics, modeling, and quantitative analysis.
You must use the provided tools to perform calculations accurately based on the user's request or intermediate data.
Do not perform calculations yourself, always use a tool.
Explain your reasoning for choosing a calculation or interpreting a result if asked.
ALL calculations, simple or complex, MUST be performed using the available tools.
Respond concisely with the calculation result or status. Use the provided tools ONLY.
"""

    def __init__(
        self,
        llm_provider: ILLMProvider,
        verbose: bool = False,
        max_iterations: int = 15,
    ):
        math_tools = [CalculatorTool()]

        # Define the base prompt
        prompt = SystemMessagePromptTemplate.from_template(self.SYSTEM_MESSAGE)

        super().__init__(
            llm_provider=llm_provider,
            verbose=verbose,
            max_iterations=max_iterations,
            tools=math_tools,
            base_prompt=prompt,
        )

