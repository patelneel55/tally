"""
LangGraph Agent Demo
-------------------

This script demonstrates how to use the LangGraphAgent with RAG and indexing tools.
"""

import sys

import pysqlite3


sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
import asyncio
import logging
import os
from datetime import datetime, timedelta

from infra.output.simple import SimpleTextOutputFormatter

from infra.acquisition.sec_fetcher import FilingType
from infra.agents import LangGraphAgent
from infra.embeddings.providers import OpenAIEmbeddingProvider
from infra.llm.providers import OpenAIProvider
from infra.pipelines.indexing_pipeline import IndexingPipeline
from infra.pipelines.rag_pipeline import RAGFinancialAnalysisPipeline

# from infra.prompting.strategies import BasicPromptStrategy
from infra.tools.pipelines import IndexingPipelineTool, RAGQueryTool
from infra.vector_stores.chromadb import ChromaVectorStore


# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    # Create LLM provider with appropriate model
    llm_provider = OpenAIProvider()
    embedding_provider = OpenAIEmbeddingProvider()
    vector_store = ChromaVectorStore()

    # Create the agent
    agent = LangGraphAgent(llm_provider=llm_provider, verbose=True, max_iterations=20)

    # Create pipeline instances
    # Create the indexing pipeline
    indexing_pipeline = IndexingPipeline(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )

    # Create the RAG pipeline with a role-based prompting strategy
    # For now, we'll use a simple text output approach
    rag_pipeline = RAGFinancialAnalysisPipeline(
        llm_provider=llm_provider,
        output_formatter=SimpleTextOutputFormatter(),
        vector_store=vector_store,
        embedding_provider=embedding_provider,
    )

    # Create and add tools
    indexing_tool = IndexingPipelineTool(pipeline=indexing_pipeline)
    rag_tool = RAGQueryTool(pipeline=rag_pipeline)

    # Add tools to the agent
    agent.add_tool(indexing_tool)
    agent.add_tool(rag_tool)

    # Example query that requires breaking down into sub-tasks
    # This will demonstrate the agent's ability to:
    # 1. Parse the complex query
    # 2. First index necessary data (if not done already)
    # 3. Query the indexed data to get specific information
    # 4. Synthesize a comprehensive response

    query = """
    How does Goldman Sachs’ performance in Investment Banking compare to Asset Management?
    """

    # Run the agent
    logger.info("Starting agent execution...")
    result = await agent.run(query)

    # Print the result
    if isinstance(result, dict):
        # If in verbose mode, we get a dict with answer and steps
        print("\n\n=== FINAL ANSWER ===")
        print(result["answer"])

        print("\n\n=== REASONING STEPS ===")
        for i, step in enumerate(result["steps"], 1):
            print(f"\nStep {i}:")
            print(f"Thought: {step.get('thought', 'N/A')}")
            print(f"Action: {step.get('action', 'N/A')}")
            print(f"Action Input: {step.get('action_input', 'N/A')}")
            print(
                f"Result: {step.get('result', 'N/A')[:100]}..."
            )  # Truncate long results
    else:
        # Otherwise just the answer
        print("\n\n=== RESULT ===")
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
