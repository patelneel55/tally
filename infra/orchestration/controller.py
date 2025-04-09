"""
Hybrid Controller
---------------

This module provides the controller for hybrid pipeline/agent execution.
The controller decides whether to run pipelines directly or delegate to agents.
"""

import logging
import re
from typing import Any, Callable, Dict, List, Optional, Pattern, Tuple, Union

from infra.agents.base import IAgent
from infra.core.interfaces import IEmbeddingProvider, ILLMProvider, IVectorStore
from infra.pipelines.indexing_pipeline import IndexingPipeline

# from infra.pipelines.rag_pipeline import RAGFinancialAnalysisPipeline
# from infra.tools.debug_tools import EchoTool
from infra.tools.pipelines import IndexingPipelineTool

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PipelinePattern:
    """
    Class to represent a pattern that matches tasks that should be handled by a pipeline.
    """

    def __init__(
        self,
        pattern: Union[str, Pattern],
        pipeline_name: str,
        param_extractor: Callable[[str], Dict[str, Any]],
    ):
        """
        Initialize the pipeline pattern.

        Args:
            pattern: Regex pattern to match tasks
            pipeline_name: Name of the pipeline to use
            param_extractor: Function to extract parameters from the matched task
        """
        self.pattern = re.compile(pattern) if isinstance(pattern, str) else pattern
        self.pipeline_name = pipeline_name
        self.param_extractor = param_extractor

    def match(self, task: str) -> bool:
        """
        Check if the task matches this pattern.

        Args:
            task: The task to check

        Returns:
            True if the task matches, False otherwise
        """
        return bool(self.pattern.search(task))

    def extract_params(self, task: str) -> Dict[str, Any]:
        """
        Extract parameters from the task.

        Args:
            task: The task to extract parameters from

        Returns:
            A dictionary of parameters
        """
        return self.param_extractor(task)


class HybridController:
    """
    Controller that decides whether to run pipelines directly or delegate to agents.
    """

    def __init__(
        self,
        llm_provider: ILLMProvider,
        embedding_provider: IEmbeddingProvider,
        vector_store: IVectorStore,
        general_agent: Optional[IAgent] = None,
        verbose: bool = False,
        debug: bool = False,
    ):
        """
        Initialize the hybrid controller.

        Args:
            llm_provider: Provider for the LLM
            embedding_provider: Provider for embeddings
            vector_store: Vector store for document storage
            general_agent: Optional general-purpose agent to delegate to
            verbose: Whether to enable verbose output
            debug: Whether to enable debug logging
        """
        self.llm_provider = llm_provider
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.general_agent = general_agent
        self.verbose = verbose
        self.debug = debug

        # Initialize pipelines
        self.pipelines = self._initialize_pipelines()

        # Initialize pipeline patterns
        # self.pipeline_patterns = self._initialize_pipeline_patterns()

        # Initialize debug tools
        # self.trace_tool = TracingTool(trace_id="hybrid_controller")

    def _initialize_pipelines(self) -> Dict[str, Any]:
        """
        Initialize all pipelines.

        Returns:
            A dictionary mapping pipeline names to pipeline instances
        """
        # Create the indexing pipeline
        indexing_pipeline = IndexingPipeline(
            embedding_provider=self.embedding_provider,
            vector_store=self.vector_store,
            should_save_intermediates=self.debug,
        )

        # # Create the RAG pipeline
        # rag_pipeline = RAGFinancialAnalysisPipeline(
        #     prompt_strategy=None,  # Will be set based on task
        #     llm_provider=self.llm_provider,
        #     output_formatter=None,  # Will be set based on task
        #     vector_store=self.vector_store,
        #     embedding_provider=self.embedding_provider
        # )

        return {
            "indexing_pipeline": indexing_pipeline,
            # "rag_pipeline": rag_pipeline
        }

    def _initialize_pipeline_patterns(self) -> List[PipelinePattern]:
        """
        Initialize patterns for matching tasks to pipelines.

        Returns:
            A list of PipelinePattern instances
        """
        # Pattern for indexing SEC filings
        indexing_pattern = PipelinePattern(
            pattern=r"(?i)index|fetch|retrieve|get\s+(?:the\s+)?(?:sec\s+)?filing(?:s)?\s+for\s+([A-Z]+)(?:\s+|\.|$)",
            pipeline_name="indexing_pipeline",
            param_extractor=self._extract_indexing_params,
        )

        # Pattern for querying financial data
        # rag_pattern = PipelinePattern(
        #     pattern=r"(?i)(?:query|ask|analyze|search)(?:\s+about)?\s+(.+?)(?:\s+for\s+([A-Z]+))?(?:\.|$)",
        #     pipeline_name="rag_pipeline",
        #     param_extractor=self._extract_rag_params
        # )

        return [indexing_pattern]  # , rag_pattern]

    def _extract_indexing_params(self, task: str) -> Dict[str, Any]:
        """
        Extract parameters for the indexing pipeline.

        Args:
            task: The task to extract parameters from

        Returns:
            A dictionary of parameters for the indexing pipeline
        """
        # Extract ticker from task
        ticker_match = re.search(r"(?i)for\s+([A-Z]+)(?:\s+|\.|$)", task)
        ticker = ticker_match.group(1) if ticker_match else None

        # Extract filing type from task
        filing_type_map = {
            "10-k": "ANNUAL_REPORT",
            "10-q": "QUARTERLY_REPORT",
            "8-k": "CURRENT_REPORT",
            "annual": "ANNUAL_REPORT",
            "quarterly": "QUARTERLY_REPORT",
            "current": "CURRENT_REPORT",
        }

        filing_type = "QUARTERLY_REPORT"  # Default
        for key, value in filing_type_map.items():
            if re.search(rf"(?i){key}", task):
                filing_type = value
                break

        # Log parameter extraction if in debug mode
        if self.debug:
            logger.debug(
                f"Extracted indexing parameters: ticker={ticker}, filing_type={filing_type}"
            )

        return {
            "identifier": ticker,
            "filing_type": filing_type,
            "force_reindex": "force" in task.lower(),
        }

    def _extract_rag_params(self, task: str) -> Dict[str, Any]:
        """
        Extract parameters for the RAG pipeline.

        Args:
            task: The task to extract parameters from

        Returns:
            A dictionary of parameters for the RAG pipeline
        """
        # Extract the query from the task
        query_match = re.search(
            r"(?i)(?:query|ask|analyze|search)(?:\s+about)?\s+(.+?)(?:\s+for\s+([A-Z]+))?(?:\.|$)",
            task,
        )
        query = query_match.group(1) if query_match else task

        # Extract company ticker if present
        ticker = (
            query_match.group(2)
            if query_match and len(query_match.groups()) > 1
            else None
        )

        prompt_context = {}
        if ticker:
            prompt_context["company"] = ticker

        # Log parameter extraction if in debug mode
        if self.debug:
            logger.debug(f"Extracted RAG parameters: query='{query}', ticker={ticker}")

        return {"task_description": query, "prompt_context": prompt_context}

    async def process(self, task: str) -> Any:
        """
        Process a task using either a pipeline or an agent.

        Args:
            task: The task to process

        Returns:
            The result of processing the task
        """
        logger.info(f"Processing task: {task}")

        # Log trace point for debugging
        # if self.debug:
        #     await self.trace_tool.run("process_task_start", {"task": task})

        # Try to match the task to a pipeline pattern
        # for pattern in self.pipeline_patterns:
        #     if pattern.match(task):
        #         pipeline_name = pattern.pipeline_name
        #         params = pattern.extract_params(task)

        #         logger.info(f"Using pipeline {pipeline_name} with params {params}")

        #         # Log trace point for debugging
        #         if self.debug:
        #             await self.trace_tool.run(
        #                 "pipeline_matched",
        #                 {"pipeline": pipeline_name, "params": params}
        #             )

        #         # Run the pipeline
        #         pipeline = self.pipelines[pipeline_name]
        #         try:
        #             result = await pipeline.run(**params)

        #             # Log trace point for debugging
        #             if self.debug:
        #                 await self.trace_tool.run(
        #                     "pipeline_completed",
        #                     {"pipeline": pipeline_name, "success": True}
        #                 )

        #             return result
        #         except Exception as e:
        #             logger.error(f"Error running pipeline {pipeline_name}: {e}")

        #             # Log trace point for debugging
        #             if self.debug:
        #                 await self.trace_tool.run(
        #                     "pipeline_error",
        #                     {"pipeline": pipeline_name, "error": str(e)}
        #                 )

        #             # Fall back to agent if available
        #             if self.general_agent:
        #                 logger.info(f"Falling back to agent for task: {task}")
        #                 return await self.general_agent.run(
        #                     f"Error occurred in {pipeline_name}: {str(e)}. " +
        #                     f"Please handle this task: {task}"
        #                 )
        #             raise

        # If no pipeline pattern matched and we have a general agent, use it
        if self.general_agent:
            logger.info(f"Delegating task to agent: {task}")

            # # Log trace point for debugging
            # if self.debug:
            #     await self.trace_tool.run(
            #         "delegating_to_agent",
            #         {"task": task}
            #     )

            return await self.general_agent.run(task)

        # If we have no general agent, raise an error
        raise ValueError(f"No pipeline or agent available for task: {task}")

    async def create_agent_with_tools(
        self, verbose: bool = True, debug: bool = False
    ) -> IAgent:
        """
        Create a general-purpose agent with tools for all pipelines.

        Args:
            verbose: Whether to enable verbose output
            debug: Whether to enable debug logging

        Returns:
            An agent with tools for all pipelines
        """
        from infra.agents.base import LangChainAgent

        # Use provided values or fall back to controller settings
        verbose = verbose if verbose is not None else self.verbose
        debug = debug if debug is not None else self.debug

        # Create the agent
        agent = LangChainAgent(
            llm_provider=self.llm_provider,
            agent_type="openai-functions",
            verbose=verbose,
            debug=debug,
        )

        # Create tools for pipelines
        indexing_tool = IndexingPipelineTool(self.pipelines["indexing_pipeline"])
        # rag_tool = RAGQueryTool(self.pipelines["rag_pipeline"])

        # Add regular tools to agent
        agent.add_tool(indexing_tool)
        # agent.add_tool(rag_tool)

        # Add debug tools if debug mode is enabled
        # if debug:
        #     echo_tool = EchoTool()
        #     trace_tool = TracingTool(trace_id="agent_trace")

        #     agent.add_tool(echo_tool)
        #     agent.add_tool(trace_tool)

        #     logger.info(f"Debug tools added to agent: {echo_tool.name()}, {trace_tool.name()}")

        return agent
