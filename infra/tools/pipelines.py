"""
Pipeline Tools
------------

This module provides tool implementations that wrap existing pipelines.
These tools allow agents to use pipelines as building blocks for complex workflows.
"""

import datetime
import json
from typing import Any, ClassVar, Dict, List, Optional, Type

from pydantic import BaseModel, Field

from infra.acquisition.registry import schema_registry
from infra.acquisition.sec_fetcher import DataFormat, FilingType
from infra.core.interfaces import IEmbeddingProvider, IVectorStore
from infra.pipelines.indexing_pipeline import IndexingPipeline
from infra.pipelines.rag_pipeline import RAGFinancialAnalysisPipeline
from infra.tools.base import PipelineTool


class IndexingToolInput(BaseModel):
    collection: str = Field(..., description="Collection name to index into")
    is_query_mode: bool = Field(
        default=False,
        description="Query mode returns the accepted metadata schema for the metadata field",
    )
    input_values: Dict[str, Any] = Field(default_factory=dict, description="")


class IndexingPipelineTool(PipelineTool):
    """
    Tool implementation that wraps the IndexingPipeline.

    This tool allows agents to fetch, process, and index SEC filings.
    """

    _TOOL_NAME: ClassVar[str] = "index_collection_data"
    _TOOL_DESCRIPTION: ClassVar[
        str
    ] = """
Triggers the appropriate indexing pipeline for a given collection based on validated metadata.
Use this tool when data is missing from search results and must be ingested into the knowledge base.
Once this tool is complete, indexing will be complete as well. Confirm that indexing is complete by
querying the vector search one more time after this.

The tool operates in two modes:
    Query Mode (is_query_mode=True): Returns the required metadata schema for the specified collection. Use this first to determine what metadata is needed.
    Index Mode (is_query_mode=False): Accepts a list of metadata objects (under input_values) and performs the actual ingestion. Metadata must match the schema returned in query mode.

Instructions:
    Use this tool only after all missing metadata has been identified.
    Batch multiple input values in a single call to optimize indexing efficiency.
    Always start with query mode to fetch the metadata schema before submitting input values.

Arguments:
    collection (str): Name of the collection to index (e.g. "SECFilings", "EarningsCall").
    is_query_mode (bool): Set to True to return the expected metadata schema; False to trigger indexing.
    input_values (dictionary): Dictionary of metadata entries to ingest. Only required when is_query_mode=False.
"""

    def __init__(self, vector_store: IVectorStore, embeddings: IEmbeddingProvider):
        """
        Initialize the indexing pipeline tool.

        Args:
            pipeline: An instance of IndexingPipeline
        """
        super().__init__(
            name=self._TOOL_NAME,
            description=self._TOOL_DESCRIPTION,
            args_schema=IndexingToolInput,
        )
        self._schema_registry = schema_registry
        self._vector_store = vector_store
        self._embedding_provider = embeddings

    async def execute(self, **kwargs):
        tool_input = IndexingToolInput(**kwargs)
        collection = self._schema_registry.get_collection(tool_input.collection)
        if tool_input.is_query_mode:
            schema = collection.indexer_schema.model_json_schema()
            return json.dumps(schema)
        self.pipeline = collection.indexer
        self.pipeline.embedding_provider = self._embedding_provider
        self.pipeline.vector_store = self._vector_store
        return await super().execute(**tool_input.input_values)
