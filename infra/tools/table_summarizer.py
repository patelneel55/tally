import logging
from typing import ClassVar, Optional

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

    table: str = Field(description="The table to be summarized in Markdown format.")


class TableSummarizerTool(BaseTool):
    """
    Summarizes a table by providing a list of column names and their types.
    """

    _TOOL_NAME: ClassVar[str] = "table_summarizer"
    _TOOL_DESCRIPTION: ClassVar[str] = (
        "Summarizes a table by providing a list of column names and their types."
    )

    _TABLE_SUMMARIZER_PROMPT = """
You are an expert data analyst. Your task is to summarize the provided Markdown table for semantic search purposes. Analyze its structure (headers, rows). Generate a descriptive paragraph that includes:
1. The main subject or topic of the table.
2. The key types of data represented in the columns (e.g., identify categories from headers like 'Product Name', metrics from headers like 'Revenue', time periods from headers like 'Month').
3. The general nature of the items listed in the rows.
4. If apparent from the data and structure, mention the overall purpose or a key insight/trend.

Focus on the essence of the data, not on listing individual values or rows verbatim.

Markdown Table:
```markdown
{table}
```

Concise Summary:
        """

    def __init__(self, llm_provider: ILLMProvider):
        """
        Initialize the TableSummarizer with the table name.

        Args:
            table: The name of the table to summarize.
        """
        super().__init__(
            name=self.TOOL_NAME,
            description=self.TOOL_DESCRIPTION,
        )
        self.llm_provider = llm_provider
        self._llm_instance: Optional[BaseLanguageModel] = None  # Lazy load the model

        self.prompt_template = ChatPromptTemplate.from_messages(
            HumanMessagePromptTemplate.from_template(self._TABLE_SUMMARIZER_PROMPT),
        )

    def args_schema(self) -> BaseModel:
        """
        Return the schema for the tool's arguments.

        This defines what arguments the tool accepts and their types.
        """
        return TableSummarizerInput()

    def _llm(self) -> BaseLanguageModel:
        """
        Lazy load the language model instance.

        This method ensures that the language model is only loaded when needed.
        """
        if self._llm_instance is None:
            self._llm_instance = self.llm_provider.get_model()
        return self._llm_instance

    async def run(self, **kwargs) -> str:
        """
        Run the table summarization tool.

        Args:
            **kwargs: The arguments passed to the tool.

        Returns:
            str: The summarized text of the table.
        """
        logger.info(f"📌 TOOL EXECUTION: {self.name()} with args: {kwargs}")
        try:
            llm = self._llm()

            summarizer_model: TableSummarizerInput = super().model_from_kwargs(**kwargs)
            prompt = self.prompt_template.format_prompt(table=summarizer_model.table)
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

            logger.info(f"✅ TOOL COMPLETED: {self.name()} successfully")
            return summary.strip()

        except Exception as e:
            # Catch potential errors from format_prompt or invoke
            logger.error(f"Error during TableSummarizer run: {e}", exc_info=True)
            raise
