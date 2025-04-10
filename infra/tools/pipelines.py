"""
Pipeline Tools
------------

This module provides tool implementations that wrap existing pipelines.
These tools allow agents to use pipelines as building blocks for complex workflows.
"""

import datetime
from typing import Any, ClassVar, Dict, List, Optional, Type

from pydantic import BaseModel, Field

from infra.acquisition.sec_fetcher import DataFormat, FilingType
from infra.pipelines.indexing_pipeline import IndexingPipeline
from infra.pipelines.rag_pipeline import RAGFinancialAnalysisPipeline
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


class RAGQueryToolInput(BaseModel):
    """
    Input schema for the RAGQueryTool.

    This schema defines the parameters required to query using the RAG pipeline.
    """

    task_description: str = Field(
        description="The query or analysis task to perform using the RAG system"
    )
    # retriever_search_kwargs: Optional[Dict[str, Any]] = Field(
    #     default=None,
    #     description="""
    #     Advanced search parameters for the vector store retriever, including filters.

    #     Available parameters:
    #     - k: Number of documents to retrieve (default: 4)
    #     - score_threshold: Minimum similarity score threshold (0.0 to 1.0)
    #     - fetch_k: Number of documents to initially fetch before filtering (for MMR)
    #     - lambda_mult: Controls diversity vs relevance in MMR (0.0 to 1.0)
    #     - filter: Specify filters to narrow down document retrieval

    #     Available filter fields (use with "filter" key):
    #     - accessionNo: A unique identifier assigned by the SEC to each filing. It can be used to reference or target a specific document submission precisely.
    #     - formType: The type of SEC filing this chunk comes from. Common values include 10-K (annual report), 10-Q(quarterly report), and 8-K (current event report). Use this to filter by the kind of financial document.
    #     - filing_date: The date the document was submitted to the SEC, in YYYY-MM-DD format. You can filter filings based on time ranges (e.g., “after 2022”, “from last year”, etc.).
    #     - company_name: The full legal name of the company that submitted the filing. Useful for matching companies when the ticker or CIK is unknown.
    #     - ticker: The public stock ticker symbol (e.g., AAPL for Apple). This is typically used to identify which company the filing belongs to.
    #     - cik: The Central Index Key, a unique numeric identifier issued by the SEC to each filing entity. Use this for precise filtering of companies across all their filings.
    #     - documentURL: A reference link to the original filing on the SEC website. Not used for filtering, but important for traceability.
    #     - source: Indicates the origin of the document. For SEC filings, this is typically sec.gov. Use this to distinguish between sources if multiple corpora are used.
    #     - type: The semantic type of the content chunk. Examples include Section, Paragraph, or Table. This helps in filtering for specific types of content within the filing (e.g., “only show tables” or “top-level sections only”).
    #     - level: A number indicating the hierarchical depth of the content in the document structure. A lower number (e.g., 0 or 1) represents higher-level sections, while higher numbers represent more deeply nested content.
    #     - path: A breadcrumb-like string showing the chunk’s location within the document structure (e.g., Item 1 > Business > Strategy). Use this to filter for specific thematic areas such as “Risk Factors” or “Management Discussion.”
    #     - parent: The immediate parent section heading under which this content chunk falls. Use this for context-based filtering when users mention subtopics or subsections.

    #     Filter operator examples:
    #     - Exact match: {"filter": {"company": "AAPL"}}
    #     - Range query: {"filter": {"year": {"$gte": 2020, "$lte": 2023}}}
    #     - Multiple values: {"filter": {"filing_type": {"$in": ["10-K", "10-Q"]}}}
    #     - Combined: {"filter": {"company": "MSFT", "filing_type": "10-K"}, "k": 10}

    #     Full examples:
    #     {"k": 10}
    #     {"k": 5, "score_threshold": 0.7}
    #     {"filter": {"company": "AAPL", "filing_type": "10-K"}, "k": 5}
    #     {"filter": {"filing_date": "2023-01-01"}, "k": 8}
    #     """
    # )
    retriever_search_type: Optional[str] = Field(
        default="similarity",
        description="""
        Type of search to perform in the vector store.

        Options:
        - "similarity" (default): Standard vector similarity search
        - "mmr": Maximum Marginal Relevance search for diversity
        - "similarity_score_threshold": Similarity search with score filtering
        """,
    )


class RAGQueryTool(PipelineTool):
    """
    Tool implementation that wraps the RAGFinancialAnalysisPipeline.

    This tool allows agents to query indexed SEC filings and other financial data
    using retrieval-augmented generation (RAG).
    """

    _TOOL_NAME: ClassVar[str] = "query_financial_data"
    _TOOL_DESCRIPTION: ClassVar[str] = (
        """
        Performs a retrieval-augmented generation (RAG) query against indexed financial data.
        This tool uses vector similarity search to find relevant information in the indexed
        documents and generates a response based on that information.

        Use this tool when:
        - You need to answer questions based on financial data that has been indexed
        - You want to analyze content from SEC filings that were previously indexed
        - You need to extract specific information from financial documents

        Arguments:
        - task_description (str): The query or analysis task to perform (e.g., "What were the risk factors mentioned in Tesla's latest 10-K?")
        - retriever_search_kwargs (dict, optional): Advanced search parameters and filters for the vector store
        - retriever_search_type (str, optional): Type of search to perform ("similarity", "mmr", etc.)

        Available filter fields (use with "filter" key in retriever_search_kwargs):
        - company: Company ticker symbol (e.g., 'AAPL', 'MSFT')
        - filing_type: SEC filing type ('10-K', '10-Q', '8-K')
        - year: Year of filing (e.g., 2023)
        - quarter: Quarter number for quarterly reports (1, 2, 3, 4)
        - filing_date: Date of filing in ISO format (YYYY-MM-DD)
        - section: Section of the filing (e.g., 'Risk Factors', 'MD&A')

        Advanced search parameters and examples:
        - Basic query: {"task_description": "What were Apple's revenue trends?"}
        - Filtered query: {"task_description": "Analyze risks", "retriever_search_kwargs": {"filter": {"company": "AAPL", "year": 2023}}}
        - More documents: {"task_description": "Compare financials", "retriever_search_kwargs": {"k": 10, "filter": {"filing_type": "10-K"}}}
        - Diverse results: {"task_description": "Overview competitors", "retriever_search_type": "mmr", "retriever_search_kwargs": {"k": 5, "fetch_k": 20, "lambda_mult": 0.7}}
        - Date range: {"task_description": "Trends in 2022-2023", "retriever_search_kwargs": {"filter": {"filing_date": {"$gte": "2022-01-01", "$lte": "2023-12-31"}}}}

        Notes:
        - This tool requires that documents have been previously indexed using the index_sec_filings tool
        - The quality of the response depends on the relevance of the indexed documents
        - The tool performs both retrieval and generation - it finds relevant information and then generates an analysis
        - When no filters are provided, the tool searches across all indexed documents
        """
    )

    def __init__(self, pipeline: RAGFinancialAnalysisPipeline):
        """
        Initialize the RAG query tool.

        Args:
            pipeline: An instance of RAGFinancialAnalysisPipeline
        """
        super().__init__(
            name=self._TOOL_NAME,
            description=self._TOOL_DESCRIPTION,
            args_schema=RAGQueryToolInput,
            pipeline=pipeline,
            # No arg mapping needed as the parameter names match
        )

    async def run(self, **kwargs) -> Any:
        """
        Run the RAG pipeline with the provided arguments.

        This method overrides the default PipelineTool run method to handle
        the specific parameter mapping needed for the updated RAG pipeline.

        Args:
            task_description: The query or analysis task to perform
            retriever_search_kwargs: Optional advanced search parameters including filters
            retriever_search_type: Optional type of search to perform

        Returns:
            The result of the RAG query
        """
        task_description = kwargs.get("task_description")
        retriever_search_kwargs = kwargs.get("retriever_search_kwargs", {}) or {}
        retriever_search_type = kwargs.get("retriever_search_type", "similarity")

        # Set default k if not provided
        search_kwargs = dict(retriever_search_kwargs)
        if "k" not in search_kwargs:
            search_kwargs["k"] = 4

        # Call the pipeline with the appropriate parameters
        return await self._pipeline.run(
            task_description=task_description,
            retriever_search_type=retriever_search_type,
            retriever_search_kwargs=search_kwargs,
        )
