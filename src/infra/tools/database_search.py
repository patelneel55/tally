import asyncio
import json
import logging
from datetime import date, datetime
from typing import Any, ClassVar, Dict, List

from langchain_core.documents import Document
from pydantic import BaseModel, Field
from sqlalchemy import func

from infra.collections.registry import TraversalType, get_schema_registry
from infra.databases.cache import Cache
from infra.embeddings.models import IEmbeddingProvider
from infra.llm.models import ILLMProvider
from infra.pipelines.mem_walker import MemoryTreeNode, MemWalker
from infra.tools.models import BaseTool
from infra.vector_stores.models import IVectorStore, SearchKwargs
from infra.collections.models import HierarchyMetadata


# Set up logging
logger = logging.getLogger(__name__)


class VectorSearchQuery(BaseModel):
    query: str = Field(
        ..., description="Search query that is optimized for vector search"
    )
    justification: str = Field(
        ..., description="A reason for why this query is relevant to the user's request"
    )
    k: int = Field(
        default=5,
        description="The maximum number o relevant document chunks to retrieve",
    )
    collection: str = Field(..., description="Collection name of the vector database")
    filters: Dict[str, Any] = Field(
        ...,
        description="Filter criteria for document metadata retrieval. Only provide values if absolutely sure and necessary",
    )

class TargetQueryInfo(BaseModel):
    collection_searched: str
    filters_applied: Dict[str, Any]

class SearchOutput(BaseModel):
    status: str = Field("")
    message: str = Field("")
    query_executed: TargetQueryInfo = Field(...)
    results: List[BaseModel] = Field(default_factory=list)

class DatabaseSearchTool(BaseTool):
    _TOOL_NAME: ClassVar[str] = "database_search"
    _TOOL_DESCRIPTION: ClassVar[str] = ""

    def __init__(
        self,
        llm_provider: ILLMProvider,
        vector_store: IVectorStore = None,
        embeddings: IEmbeddingProvider = None,
    ):
        super().__init__(
            name=self._TOOL_NAME,
            description=self._TOOL_DESCRIPTION,
            args_schema=VectorSearchQuery,
        )
        self._schema_registry = get_schema_registry()
        self._vector_store = vector_store
        self._embeddings = embeddings
        self._llm_provider = llm_provider

    async def execute(self, **kwargs) -> str:
        logger.info(f"📌 TOOL EXECUTION: {self.name}")
        try:
            search_query = VectorSearchQuery(**kwargs)
            collection = self._schema_registry.get_collection(search_query.collection)
            search_output = SearchOutput(
                query_executed=TargetQueryInfo(
                    collection_searched=collection.name,
                    filters_applied=search_query.filters
                )
            )

            exists, status, reason = collection.searcher.data_exists(search_query.filters)
            search_output.status = status
            search_output.message = reason
            if not exists:
                return search_output.model_dump()

            search_kwargs = SearchKwargs(k=search_query.k, filters=search_query.filters)
            if collection.traversal == TraversalType.MEM_WALK:
                root_nodes: List[MemoryTreeNode] = (
                    collection.searcher.nodes_for_mem_walk(search_query.filters)
                )
                mem_walker = MemWalker(llm_provider=self._llm_provider)
                tasks = [
                    mem_walker.navigate_tree(search_query.query, node)
                    for node in root_nodes
                ]
                results = await asyncio.gather(*tasks)
                results = [
                    summary_ctx
                    for output_obj in results
                    for summary_ctx in output_obj.collected_context
                ]
                node_ids = [r.node_id for r in results]
                search_kwargs.k = 100
                search_kwargs.filters = {
                    "node_ids": node_ids
                }
            
            embeddings = self._embeddings.get_embedding_model()
            self._vector_store.set_collection(
                search_query.collection, search_query.filters
            )
            retriever = self._vector_store.as_retriever(
                embeddings=embeddings,
                search_kwargs=search_kwargs
            )
            documents = await retriever.ainvoke(search_query.query) 

            logger.info(f"✅ TOOL COMPLETED: {self.name} successfully")
            return json.dumps([out.model_dump() for out in documents])
        except Exception as e:
            # Catch potential errors from format_prompt or invoke
            logger.error(f"Error during TableSummarizer run: {e}", exc_info=True)
            raise
