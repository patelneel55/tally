"""
Pipeline Tools
------------

This module provides tool implementations that wrap existing pipelines.
These tools allow agents to use pipelines as building blocks for complex workflows.
"""

import datetime
from typing import Any, ClassVar, Dict, List, Type

from pydantic import BaseModel, Field

from infra.acquisition.sec_fetcher import DataFormat, FilingType
from infra.pipelines.indexing_pipeline import IndexingPipeline

# from infra.pipelines.rag_pipeline import RAGFinancialAnalysisPipeline
from infra.tools.base import PipelineTool


class IndexingToolInput(BaseModel):
    """
    Input schema for the IndexingPipelineTool.

    This schema defines the parameters required to index SEC filings.
    """

    ticker: str = Field(description="The ticker symbol of the company")
    filing_type: FilingType = Field(description="The type of filing to index")
    start_date: datetime.date = Field(
        description="The start date for fetching filings (YYYY-MM-DD)"
    )
    end_date: datetime.date = Field(
        description="The end date for fetching filings (YYYY-MM-DD)"
    )


class IndexingPipelineTool(PipelineTool):
    """
    Tool implementation that wraps the IndexingPipeline.

    This tool allows agents to fetch, process, and index SEC filings.
    """

    _TOOL_NAME: ClassVar[str] = "index_sec_filings"
    _TOOL_DESCRIPTION: ClassVar[str] = (
        """
        Downloads and indexes SEC filings (10-K, 10-Q, or 8-K) for a specified public company within a given date range. This tool retrieves the filings from the SEC EDGAR database, chunks the text into semantically meaningful segments, embeds them using a language model, and stores the resulting vectors in a Weaviate vector store for future semantic search and retrieval.
        Use this tool when:
        - You need to prepare a company's SEC filings for semantic or vector-based analysis.
        - You want to index filings over a historical period to enable contextual queries.
        - You are building a retrieval-augmented generation (RAG) pipeline or LLM-based analysis system using company filings.
        Arguments:
        - ticker (str): The public stock ticker symbol (e.g., "MSFT").
        - filing_type (str): Type of SEC filing to download — one of "10-K", "10-Q", or "8-K".
        - start_date (str): Start date (YYYY-MM-DD) of the filing window.
        - end_date (str): End date (YYYY-MM-DD) of the filing window.
        Notes:
        - Only filings within the specified date range will be processed.
        - This tool performs **indexing only** — it does not analyze or summarize filings.
        - Chunks are stored in Weaviate under a namespace that includes the ticker and filing type for precise querying.
        """
    )

    def __init__(self, pipeline: IndexingPipeline):
        """
        Initialize the indexing pipeline tool.

        Args:
            pipeline: An instance of IndexingPipeline
        """
        super().__init__(
            name=self._TOOL_NAME,
            description=self._TOOL_DESCRIPTION,
            args_schema=IndexingToolInput,
            pipeline=pipeline,
            arg_mapping={
                "ticker": "identifier",
                "filing_type": "filing_type",
                "start_date": "start_date",
                "end_date": "end_date",
            },
        )


# class RAGQueryTool(PipelineTool):
#     """
#     Tool implementation that wraps the RAGFinancialAnalysisPipeline.

#     This tool allows agents to query indexed SEC filings using RAG.
#     """

#     def __init__(self, pipeline: RAGFinancialAnalysisPipeline):
#         """
#         Initialize the RAG query tool.

#         Args:
#             pipeline: An instance of RAGFinancialAnalysisPipeline
#         """
#         super().__init__(
#             name="query_financial_data",
#             description="Query indexed financial data using RAG",
#             pipeline=pipeline
#         )

#     def args_schema(self) -> Dict[str, ToolParameter]:
#         """
#         Define the schema for the tool's arguments.

#         Returns:
#             A dictionary mapping argument names to their parameter definitions
#         """
#         return {
#             "task_description": {
#                 "type": "string",
#                 "description": "The query or analysis task to perform",
#                 "required": True
#             },
#             "prompt_context": {
#                 "type": "object",
#                 "description": "Additional context for the prompt",
#                 "required": False
#             }
#         }

#     async def run(self, **kwargs) -> Any:
#         """
#         Run the RAG pipeline with the provided arguments.

#         Args:
#             task_description: The query or analysis task to perform
#             prompt_context: Additional context for the prompt

#         Returns:
#             The result of the RAG query
#         """
#         return self.pipeline.run(**kwargs)
