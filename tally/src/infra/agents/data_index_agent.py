import logging

from langchain.prompts import SystemMessagePromptTemplate

from infra.agents.langgraph import LangGraphReActAgent
from infra.embeddings.models import IEmbeddingProvider
from infra.llm.models import ILLMProvider
from infra.tools.collection_router import CollectionRouterTool
from infra.tools.pipelines import IndexingPipelineTool
from infra.tools.vector_search import VectorSearchTool
from infra.vector_stores.models import IVectorStore


# Set up logging
logger = logging.getLogger(__name__)


class DataIndexAgent(LangGraphReActAgent):
    AGENT_NAME = "DataIndexer"
    SYSTEM_MESSAGE = """
You are an AI assistant responsible for managing the status of indexed data sources.
Your job is to check if specific data sources (like company filings or transcripts) are present
and up-to-date in the knowledge base using the available tools.
If data is missing or stale, you can trigger the indexing process for that source using the appropriate tool.
Provide clear status updates based on the tool outputs.
"""

    def __init__(
        self,
        llm_provider: ILLMProvider,
        vector_store: IVectorStore,
        embedding_provider: IEmbeddingProvider,
    ):
        index_tools = [
            CollectionRouterTool(llm_provider=llm_provider),
            VectorSearchTool(vector_store=vector_store, embeddings=embedding_provider),
            # SQLAlchemySearchTool(engine=sqlalchemy_engine),
            IndexingPipelineTool(
                vector_store=vector_store,
                embeddings=embedding_provider,
            ),
        ]

        super().__init__(
            llm_provider=llm_provider,
            tools=index_tools,
            base_prompt=SystemMessagePromptTemplate.from_template(self.SYSTEM_MESSAGE),
        )
