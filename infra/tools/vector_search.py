import logging
from typing import ClassVar, List

from langchain_core.documents import Document

from infra.tools.base import BaseTool
from infra.core.interfaces import IVectorStore, IEmbeddingProvider
from infra.acquisition.models import SECFiling

from pydantic import BaseModel, Field

# Set up logging
logger = logging.getLogger(__name__)

class VectorSearchQuery(BaseModel):
    query: str = Field(..., description="Search query that is optimized for vector search")
    justification: str = Field(..., description="A reason for why this query is relevant to the user's request")
    k: int = Field(default=5, description="The maximum number of relevant document chunks to retrieve")
    # metadata_filter: SECFiling = Field(..., description="Filter criteria for document metadata.")

class VectorSearchTool(BaseTool):

    _TOOL_NAME: ClassVar[str] = "vector_search"
    _TOOL_DESCRIPTION: ClassVar[str] = """
Searches a vector knowledge base for documents relevant to the query.
Use this to find specific information, context or data points stored previously.
Provide a clear query, justification and filters
"""

    def __init__(
            self,
            vector_store: IVectorStore,
            embeddings: IEmbeddingProvider
        ):
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
            content = doc.page_content.replace('\n', ' ').strip()
            formatted_output.append(
                f"--- Document {i + 1} ---\n"
                f"Metadata: {metadata_str}\n"
                f"Content: {content}\n"
                f"--- End Document {i + 1} ---\n"
            )
            return "\n".join(formatted_output)

    async def execute(self, **kwargs):
        try:
            search_query = VectorSearchQuery(**kwargs)
            embeddings = self._embeddings.get_embedding_model()
            search_kwargs = {'k': search_query.k}
            # if search_query.metadata_filter:
            #     search_kwargs['filter'] = search_query.metadata_filter.get_metadata()
            retriever = self._vector_store.as_retriever(
                embeddings=embeddings,
                search_type="similarity",
                search_kwargs=search_kwargs,
            )
            results = await retriever.ainvoke(search_query.query)
            formatted_results = self._format_results_to_string(results)
            return formatted_results
        except Exception as e:
            logger.error(f"Unexpected error during vector search for query {search_query.query}: {e}", exc_info=True)
