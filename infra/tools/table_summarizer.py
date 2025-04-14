import logging
from typing import ClassVar, Optional, Type

from langchain_core.language_models import BaseLanguageModel
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from pydantic import BaseModel, Field

from infra.core.interfaces import ILLMProvider
from infra.tools.base import BaseTool

logger = logging.getLogger(__name__)


class TableSummarizerInput(BaseModel):
    """
    Input schema for the TableSummarizerTool.

    This schema defines the parameters required to summarize a table.
    """

    table: str = Field(description="The table to be summarized provided in Markdown format.")


class TableSummarizerTool(BaseTool):
    """
    Summarizes a table by providing a list of column names and their types.
    """

    _TOOL_NAME: ClassVar[str] = "table_summarizer"
    _TOOL_DESCRIPTION: ClassVar[str] = (
        "Summarizes a table by providing a list of column names and their types."
    )

    _TABLE_SUMMARIZER_PROMPT = """
Summarize the content of the provided table in one to two concise sentences.
First, describe what the table shows by identifying its subject, key columns, and general row categories,
and include any available timeframes (e.g., Q3 2024, year-end 2023) or company names.
If the table contains financial data, emphasize relevant metrics such as total assets, total liabilities, cash and cash equivalents,
and additional paid-in capital, and note if the table is consolidated, unaudited, or segment-specific.
For non-financial tables, provide a clear description of the categories and data without overloading the summary with excessive details.
Ensure the summary remains succinct, using key financial and general terminology that supports semantic retrieval without exceeding token limits.
The summary should be robust enough that if a query were to try and retrieve any specific line item of the table,
the summary will contain the necessary references to identify the table as the data source.

```
{table}
```
"""

    def __init__(self, llm_provider: ILLMProvider):
        """
        Initialize the TableSummarizer with the table name.

        Args:
            llm_provider: The LLM provider to use for summarization.
        """
        super().__init__(
            name=self._TOOL_NAME,
            description=self._TOOL_DESCRIPTION,
            args_schema=TableSummarizerInput,
        )
        self._llm_provider = llm_provider
        self._llm_instance: Optional[BaseLanguageModel] = None  # Lazy load the model

        self._prompt_template = ChatPromptTemplate.from_messages(
            [
                HumanMessagePromptTemplate.from_template(self._TABLE_SUMMARIZER_PROMPT),
            ]
        )

    def _llm(self) -> BaseLanguageModel:
        """
        Lazy load the language model instance.

        This method ensures that the language model is only loaded when needed.
        """
        if self._llm_instance is None:
            self._llm_instance = self._llm_provider.get_model()
        return self._llm_instance

    async def run(self, **kwargs) -> str:
        """
        Run the table summarization tool.

        Args:
            **kwargs: The arguments passed to the tool.

        Returns:
            str: The summarized text of the table.
        """
        logger.info(f"📌 TOOL EXECUTION: {self.name}")
        try:
            llm = self._llm()

            # Create a new instance of TableSummarizerInput and validate the kwargs
            summarizer_model = TableSummarizerInput(**kwargs)
            prompt = self._prompt_template.format_prompt(table=summarizer_model.table)
            response = await llm.ainvoke(prompt)

            # Chat models (like ChatOpenAI) return a message object (e.g., AIMessage)
            # Older LLM models might return just a string
            if hasattr(response, "content"):
                summary = response.content
            elif isinstance(response, str):
                summary = response
            else:
                logger.warning(
                    f"LLM response was of unexpected type: {type(response)}. Attempting to cast to string."
                )
                summary = str(response)

            if not isinstance(summary, str):  # Final check
                summary = ""

            logger.info(f"✅ TOOL COMPLETED: {self.name} successfully")
            return summary.strip()

        except Exception as e:
            # Catch potential errors from format_prompt or invoke
            logger.error(f"Error during TableSummarizer run: {e}", exc_info=True)
            raise
