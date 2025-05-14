import logging
from typing import ClassVar, Optional

from langchain_core.language_models import BaseLanguageModel
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from pydantic import BaseModel, Field

from infra.llm.models import ILLMProvider
from infra.tools.models import BaseTool


logger = logging.getLogger(__name__)


class SummarizerInput(BaseModel):
    """
    Input schema for the SummarizerTool.

    This schema defines the parameters required to summarize text.
    """

    input: str = Field(
        ...,
        description="An input string to be summarized. It can be a table, text, or any other content.",
    )
    custom_instructions: str = Field(
        default="",
        description="Custom instructions for the summarizer. This is optional and can be used to provide additional context or guidelines for the summarization process.",
    )


class SummarizerTool(BaseTool):
    """
    Summarizes a table by providing a list of column names and their types.
    """

    _TOOL_NAME: ClassVar[str] = "text_summarizer"
    _TOOL_DESCRIPTION: ClassVar[str] = "Summarizes text"

    _TABLE_SUMMARIZER_PROMPT = """
You are an expert financial analyst summarizing SEC filing segments.

Your job is to create a **structured, discriminative summary** of the content inside the <input_query> tag. This summary will be used by another AI agent to decide whether to further explore this section or not. Your task is **not abstraction**, but **indexing**: surface key facts, metrics, and disclosures that could help downstream tools answer user queries.

You MUST follow the format below. If any section is missing in the input, leave that section out.

--------------------
<output_format>
### Section Metadata
- Ticker: [e.g., JPM]
- Filing: [e.g., 10-Q for Q1 2025]
- Section: [e.g., MD&A: Liquidity and Capital Resources]

### Topics Covered
- [Short phrases like "Net interest income", "CRE risk", "Share repurchases"]

### Key Metrics & Facts
- [Example: Net interest income: $23.3B (+1% QoQ)]
- [Example: CET1 ratio: 15.4% (unchanged)]
- [Example: Provision for credit losses: $3.3B]

### Regulatory / Strategic Commentary
- [Mention any commentary, guidance, regulation, lawsuits, etc.]
- [If no such commentary is present, omit this section]

### Table References (if applicable)
- Table: [name or content type, e.g., "Allowance Rollforward", "Capital Ratios"]
- Includes: [brief summary of rows or time periods]
</output_format>
--------------------

<rules>
- Do NOT infer or speculate. Only use content provided.
- If <custom_instructions> is present, follow that and ignore other rules.
- If <table_instructions> is present, follow it precisely for tables.
</rules>


<table_instructions>
You are a detail-retentive AI summarizer designed to handle tabular financial disclosures from SEC filings.

Your input consists of one node containing:
- A table (parsed as text or semi-structured format)
- Optional footnotes, surrounding commentary, or subheaders

<task>
You must extract and preserve:
- All row/column headings and values
- Structure (e.g., categories, subtotals, multi-year columns)
- Footnotes or explanatory clauses
- Any directional language or disclaimers in text (if provided)

You are NOT allowed to interpret the meaning or importance of the table. Do not group rows, reformat tables, or paraphrase financial terms.

<rules>
- DO NOT omit any data, even if repetitive
- DO NOT summarize across time periods unless the text explicitly does
- Retain table groupings like “Total,” “Net,” or “Subtotal” if they exist
- Use bullet-point indentation to reflect row nesting or hierarchy
- Label all referenced footnotes explicitly using [Footnote X] format

<output_format>
Return a markdown-style bullet list:
- Use top-level bullets for table headers or sections
- Use indented bullets for rows with associated values
- Include units ($MM, %, basis points) as given
- Preserve time-period comparisons explicitly (e.g., FY22 vs FY23)

<final_instruction>
Do not compress or analyze. Your job is to faithfully summarize the content and structure of the table node for downstream retrieval.
</final_instruction>
</table_instructions>

<input_query>
{input}
</input_query>

<custom_instructions>
{custom_instructions}
</custom_instructions>
"""

    def __init__(self, llm_provider: ILLMProvider, prompt=None):
        """
        Initialize the TableSummarizer with the table name.

        Args:
            llm_provider: The LLM provider to use for summarization.
        """
        super().__init__(
            name=self._TOOL_NAME,
            description=self._TOOL_DESCRIPTION,
            args_schema=SummarizerInput,
        )
        self._llm_provider = llm_provider
        self._llm_instance: Optional[BaseLanguageModel] = None  # Lazy load the model

        self._prompt_template = ChatPromptTemplate.from_messages(
            [
                HumanMessagePromptTemplate.from_template(
                    prompt or self._TABLE_SUMMARIZER_PROMPT
                ),
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

    async def execute(self, **kwargs) -> str:
        logger.debug(f"📌 TOOL EXECUTION: {self.name}")
        try:
            llm = self._llm()

            # Create a new instance of TableSummarizerInput and validate the kwargs
            input_model = SummarizerInput(**kwargs)
            prompt = self._prompt_template.format_prompt(
                input=input_model.input,
                custom_instructions=input_model.custom_instructions,
            )
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

            logger.debug(f"✅ TOOL COMPLETED: {self.name} successfully")
            return summary.strip()

        except Exception as e:
            # Catch potential errors from format_prompt or invoke
            logger.error(f"Error during TableSummarizer run: {e}", exc_info=True)
            raise
