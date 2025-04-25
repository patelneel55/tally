import logging
from typing import Any, ClassVar, Dict, List, Type

from langchain_core.documents import Document
from pydantic import BaseModel, Field

from infra.acquisition.registry import BaseMetadata
from infra.core.interfaces import IEmbeddingProvider, IVectorStore
from infra.tools.base import BaseTool

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
        description="The maximum number of relevant document chunks to retrieve",
    )
    collection: str = Field(..., description="Collection name of the vector database")
    filters: Dict[str, Any] = Field(
        ...,
        description="Filter criteria for document metadata retrieval. Only provide values if absolutely sure and necessary",
    )


class VectorSearchTool(BaseTool):

    _TOOL_NAME: ClassVar[str] = "vector_search"
    _TOOL_DESCRIPTION: ClassVar[
        str
    ] = """
You are a vector search tool used by an agent to retrieve documents from a knowledge base.
Your job is to:
    Interpret the user's query to understand the specific information, context, or data point requested.
    Formulate a semantic query that captures the user's intent.
    Identify and include only the necessary metadata filters—these are filters without which the search would be too vague or
    incorrect (e.g., a company ticker for SEC filings).

Example Use Case:
User says: "What did Amazon say about advertising revenue last quarter?"
You should produce:
{
  "query": "Advertising revenue commentary from management",
  "k": 10,
  "filters": {
    "ticker": "AMZN"
  }
}
"""

    def __init__(self, vector_store: IVectorStore, embeddings: IEmbeddingProvider):
        super().__init__(
            name=self._TOOL_NAME,
            description=self._TOOL_DESCRIPTION,
            args_schema=VectorSearchQuery,
        )
        self._vector_store = vector_store
        self._embeddings = embeddings

    def _format_results_to_string(self, res: List[Document]) -> str:
        formatted_output = ["Retrieved Documents:"]
        for i, doc in enumerate(res):
            metadata_str = ", ".join(f"{k}={v}" for k, v in doc.metadata.items())
            content = doc.page_content.replace("\n", " ").strip()
            formatted_output.append(
                f"--- Document {i + 1} ---\n"
                f"Metadata: {metadata_str}\n"
                f"Content: {content}\n"
                f"--- End Document {i + 1} ---\n"
            )
        return "\n".join(formatted_output) if len(res) > 0 else None

    async def execute(self, **kwargs):
        try:
            search_query = VectorSearchQuery(**kwargs)
            embeddings = self._embeddings.get_embedding_model()
            search_kwargs = {"k": search_query.k}
            if search_query.filters:
                search_kwargs["filter"] = search_query.filters
            self._vector_store.set_collection(search_query.collection, search_query.filters)
            retriever = self._vector_store.as_retriever(
                embeddings=embeddings,
                search_type="similarity",
                search_kwargs=search_kwargs,
            )
            results = await retriever.ainvoke(search_query.query)
            formatted_results = self._format_results_to_string(results)
            return formatted_results
        except Exception as e:
            logger.error(
                f"Unexpected error during vector search for query {search_query.query}: {e}",
                exc_info=True,
            )
