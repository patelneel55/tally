"""
Agent Runner
-----------

Example script showing how to use the hybrid controller with agents.
This demonstrates running both direct pipeline calls and LLM agent-based execution.
"""

import sys

import pysqlite3

sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")

import argparse
import asyncio
import logging
import sys

from infra.acquisition.sec_fetcher import DataFormat, FilingType

# from infra.agents.base import LangChainAgent
from infra.embeddings.providers import OpenAIEmbeddingProvider
from infra.llm.providers import OpenAIProvider
from infra.orchestration.controller import HybridController

# from infra.prompting.strategies import BasicPromptStrategy
from infra.tools.pipelines import IndexingPipelineTool
from infra.vector_stores.chromadb import ChromaVectorStore

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def run_examples(controller, general_agent, args):
    """Run example tasks using the hybrid controller and agent."""

    # Example 1: Direct pipeline execution via pattern matching
    if args.example == "all" or args.example == "1":
        logger.info("\n\n===== EXAMPLE 1: DIRECT PIPELINE EXECUTION =====")
        indexing_task = (
            "Index the quarterly SEC filings for GS from Jan 2024 to Jan 2025"
        )
        try:
            logger.info(f"Running task: {indexing_task}")
            result = await controller.process(indexing_task)
            logger.info(f"Successfully indexed {len(result)} documents")
        except Exception as e:
            logger.error(f"Error: {e}")

    # Example 2: RAG query via pattern matching
    if args.example == "all" or args.example == "2":
        logger.info("\n\n===== EXAMPLE 2: RAG QUERY VIA PATTERN MATCHING =====")
        rag_task = "Analyze the profitability trends for GS over the last quarter"
        try:
            logger.info(f"Running task: {rag_task}")
            result = await controller.process(rag_task)
            logger.info(f"Analysis result: {result}")
        except Exception as e:
            logger.error(f"Error: {e}")

    # Example 3: Complex task requiring agent
    if args.example == "all" or args.example == "3":
        logger.info("\n\n===== EXAMPLE 3: COMPLEX TASK REQUIRING AGENT =====")
        complex_task = "Compare the revenue growth of GS and JPM over the last year, and explain key factors driving any differences"
        try:
            logger.info(f"Running task: {complex_task}")
            result = await controller.process(complex_task)
            logger.info(f"Complex analysis result: {result}")
        except Exception as e:
            logger.error(f"Error: {e}")

    # Example 4: Direct agent execution
    if args.example == "all" or args.example == "4":
        logger.info("\n\n===== EXAMPLE 4: DIRECT AGENT EXECUTION =====")
        agent_task = "Create a summary of GS balance sheet trends, focusing on lending activity and credit risk"
        try:
            logger.info(f"Running direct agent task: {agent_task}")
            result = await general_agent.run(agent_task)
            logger.info(f"Agent result: {result}")
        except Exception as e:
            logger.error(f"Error: {e}")

    # Custom task
    if args.custom_task:
        logger.info(f"\n\n===== CUSTOM TASK: {args.custom_task} =====")
        try:
            if args.direct_agent:
                logger.info(f"Running direct agent task: {args.custom_task}")
                result = await general_agent.run(args.custom_task)
            else:
                logger.info(f"Running task via controller: {args.custom_task}")
                result = await controller.process(args.custom_task)
            logger.info(f"Result: {result}")
        except Exception as e:
            logger.error(f"Error: {e}")


async def main():
    """
    Main function to demonstrate hybrid controller and agent usage.
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Run LLM agents with tools")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose mode")
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug mode with file logging"
    )
    parser.add_argument(
        "--example",
        default="all",
        choices=["all", "1", "2", "3", "4"],
        help="Run specific example (1-4) or 'all'",
    )
    parser.add_argument(
        "--custom-task", type=str, help="Run a custom task instead of examples"
    )
    parser.add_argument(
        "--direct-agent",
        action="store_true",
        help="Use agent directly instead of controller for custom task",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set logging level",
    )

    args = parser.parse_args()

    # Configure logging based on arguments
    log_level = getattr(logging, args.log_level)
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    try:
        logger.info("Initializing components...")

        # Initialize basic components
        llm_provider = OpenAIProvider()
        embedding_provider = OpenAIEmbeddingProvider()
        vector_store = ChromaVectorStore()

        # Create the hybrid controller with verbosity settings
        controller = HybridController(
            llm_provider=llm_provider,
            embedding_provider=embedding_provider,
            vector_store=vector_store,
        )

        # Create and set the general agent with verbosity settings
        general_agent = await controller.create_agent_with_tools(
            verbose=args.verbose, debug=args.debug
        )

        # Set the general agent in the controller
        controller.general_agent = general_agent

        if args.custom_task:
            # Run only the custom task
            await run_examples(controller, general_agent, args)
        else:
            # Run specified examples
            await run_examples(controller, general_agent, args)

        logger.info("All tasks completed")

    except Exception as e:
        logger.error(f"Unhandled error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
