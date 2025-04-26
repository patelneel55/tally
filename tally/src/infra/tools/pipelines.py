import json
import logging
from typing import Any
from typing import ClassVar
from typing import Dict
from typing import Type

from pydantic import BaseModel
from pydantic import Field

from infra.collections.registry import get_schema_registry
from infra.embeddings.models import IEmbeddingProvider
from infra.tools.models import BaseTool
from infra.vector_stores.models import IVectorStore


logger = logging.getLogger(__name__)


class PipelineTool(BaseTool):
    """
    Tool implementation that wraps a pipeline.

    This allows existing pipelines to be used as tools by agents.
    """

    def __init__(
        self,
        name: str,
        description: str,
        args_schema: Type[BaseModel],
        arg_mapping: Dict[str, str] = None,
    ):
        """
        Initialize the pipeline tool.

        Args:
            name: The name of the tool
            description: A description of what the tool does
            pipeline: The pipeline instance to wrap
            arg_mapping: Optional mapping from tool args to pipeline args
        """
        super().__init__(name, description, args_schema)
        self._arg_mapping = arg_mapping or {}
        self._pipeline = None  # Lazy loading

    @property
    def pipeline(self):
        return self._pipeline

    @pipeline.setter
    def pipeline(self, value):
        self._pipeline = value

    async def execute(self, **kwargs) -> Any:
        """
        Run the wrapped pipeline with the provided arguments.

        Args:
            **kwargs: Arguments to pass to the pipeline

        Returns:
            The result of the pipeline execution
        """
        logger.info(f"📌 TOOL EXECUTION: {self.name}")

        # Map tool arguments to pipeline arguments if needed
        if self._arg_mapping:
            pipeline_kwargs = {}
            for tool_arg, pipeline_arg in self._arg_mapping.items():
                if tool_arg in kwargs:
                    pipeline_kwargs[pipeline_arg] = kwargs[tool_arg]
            kwargs = pipeline_kwargs

        # Run the pipeline
        try:
            result = await self._pipeline.run(**kwargs)
            logger.info(f"✅ TOOL COMPLETED: {self.name} successfully")
            return result
        except Exception as e:
            logger.error(f"❌ TOOL ERROR: {self.name} failed with error: {str(e)}")
            raise


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
        self._schema_registry = get_schema_registry()
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
        self._vector_store.set_collection(
            collection.name, collection.metadata_model.__annotations__
        )
        self.pipeline.vector_store = self._vector_store
        return await super().execute(**tool_input.input_values)
