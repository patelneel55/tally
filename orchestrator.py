import logging
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any
from typing import Dict
from typing import Optional

from infra.core.exceptions import AcquisitionError
from infra.core.exceptions import PipelineError

# Import necessary interfaces and concrete pipeline types
from infra.core.interfaces import IVectorStore  # Or IManifestManager if using manifest
from infra.core.models import AnalysisResult  # Assuming you use this

from infra.acquisition.interfaces import IDataFetcher
from infra.pipelines.indexing_pipeline import IndexingPipeline
from infra.pipelines.rag_pipeline import (
    RAGFinancialAnalysisPipeline,  # Or your specific RAG pipeline class
)


logger = logging.getLogger(__name__)


class QueryOrchestrator:
    def __init__(
        self,
        rag_pipeline: RAGFinancialAnalysisPipeline,
        indexing_pipeline: IndexingPipeline,
        data_fetcher: IDataFetcher,
        # Option A: Use Vector Store for checks
        vector_store: IVectorStore,
        # Option B: Use external manifest
        # manifest_manager: IManifestManager,
        config: Dict[str, Any],  # Pass relevant config section
    ):
        self.rag_pipeline = rag_pipeline
        self.indexing_pipeline = indexing_pipeline
        self.data_fetcher = data_fetcher
        self.vector_store = vector_store  # Use this OR manifest_manager
        # self.manifest_manager = manifest_manager
        self.config = config.get("orchestration", {})
        self.default_staleness_days = self.config.get("default_staleness_days", 7)

    def _identify_source_entity(self, query: str) -> Optional[str]:
        """
        Parses the query to identify the core entity (e.g., Ticker symbol).
        This can range from simple regex/keyword extraction to complex NLP/NER.
        Example: Simple extraction for "risks for AAPL".
        """
        # --- Simple Example ---
        parts = query.split()
        # Look for potential tickers (crude example)
        for part in reversed(parts):
            if part.isupper() and len(part) <= 5:
                # Very basic check, could be company name too. Needs refinement.
                logger.info(f"Identified potential source entity: {part}")
                return part
        logger.warning(f"Could not identify a source entity in query: '{query}'")
        return None  # Needs robust implementation

    def _needs_indexing(self, source_entity: str) -> bool:
        """
        Checks if the identified source needs to be indexed or re-indexed.
        Uses either the vector store metadata or an external manifest.
        """
        max_staleness = self.config.get(
            f"staleness_days_{source_entity}", self.default_staleness_days
        )

        # --- Option A: Using Vector Store Metadata ---
        try:
            # Assumes 'check_source_exists' handles staleness check based on 'indexed_at' metadata
            exists_and_fresh = self.vector_store.check_source_exists(
                source_identifier=source_entity,
                metadata_field=self.config.get(
                    "source_metadata_field", "source_entity"
                ),  # Configurable field name
                max_staleness_days=max_staleness,
            )
            logger.info(
                f"Checked vector store for '{source_entity}'. Exists and fresh: {exists_and_fresh}"
            )
            return not exists_and_fresh
        except Exception as e:
            logger.error(
                f"Error checking vector store for '{source_entity}': {e}", exc_info=True
            )
            # Decide behavior on error: default to indexing? Default to skipping?
            return True  # Default to indexing if check fails

        # --- Option B: Using External Manifest ---
        # try:
        #     is_indexed = self.manifest_manager.is_indexed(source_entity, max_staleness)
        #     logger.info(f"Checked manifest for '{source_entity}'. Indexed and fresh: {is_indexed}")
        #     return not is_indexed
        # except Exception as e:
        #     logger.error(f"Error checking manifest for '{source_entity}': {e}", exc_info=True)
        #     return True # Default to indexing if check fails

    def handle_query(
        self, query: str
    ) -> AnalysisResult:  # Or return type of your RAG pipeline
        """
        Handles an incoming query, performs on-demand indexing if needed, then runs RAG.
        """
        logger.info(f"Received query: '{query}'")
        start_time = datetime.now(timezone.utc)

        source_entity = self._identify_source_entity(query)

        if not source_entity:
            logger.warning(
                "No source entity identified, proceeding directly to RAG without indexing check."
            )
            # Optionally, you could skip RAG or use a generic context
        else:
            # Check if indexing is needed
            if self._needs_indexing(source_entity):
                logger.info(f"Indexing required for source: {source_entity}")
                try:
                    # 1. Fetch Data
                    fetch_params = self.config.get(
                        f"fetch_params_{source_entity}", {}
                    )  # Source-specific fetch params
                    logger.info(
                        f"Fetching data for '{source_entity}' with params: {fetch_params}"
                    )
                    # data_uris = self.data_fetcher.fetch(source_entity, params=fetch_params)
                    # ---> Mocking fetch for now
                    data_uris = [
                        f"./fake_data/{source_entity}_report.pdf"
                    ]  # Replace with actual fetch call
                    logger.info(f"Data URIs obtained: {data_uris}")

                    if not data_uris:
                        logger.warning(
                            f"No data URIs found after fetching for {source_entity}. Skipping indexing."
                        )
                    else:
                        # 2. Run Indexing Pipeline for each fetched resource
                        for uri in data_uris:
                            try:
                                logger.info(f"Running indexing pipeline for URI: {uri}")
                                self.indexing_pipeline.run(
                                    uri
                                )  # Assumes pipeline handles metadata tagging
                            except PipelineError as e:
                                logger.error(
                                    f"Indexing failed for {uri}: {e}", exc_info=True
                                )
                                # Decide: Continue with other URIs? Abort?
                            except Exception as e:
                                logger.error(
                                    f"Unexpected error during indexing for {uri}: {e}",
                                    exc_info=True,
                                )

                        # 3. Optional: Mark as indexed in manifest if using Option B
                        # self.manifest_manager.mark_indexed(source_entity, datetime.now(timezone.utc))

                except AcquisitionError as e:
                    logger.error(
                        f"Data acquisition failed for {source_entity}: {e}",
                        exc_info=True,
                    )
                    # Decide: Proceed to RAG anyway? Return error?
                except Exception as e:
                    logger.error(
                        f"Unexpected error during acquisition/indexing phase for {source_entity}: {e}",
                        exc_info=True,
                    )
            else:
                logger.info(
                    f"Source '{source_entity}' is already indexed and fresh. Skipping indexing."
                )

        # 3. Run RAG Pipeline (always runs, potentially with newly indexed data)
        try:
            logger.info("Proceeding to RAG pipeline...")
            result = self.rag_pipeline.run(
                task_description=query
            )  # Pass the original query
            # Add timing info if AnalysisResult model supports it
            if hasattr(result, "pipeline_duration_seconds"):
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                result.pipeline_duration_seconds = duration
            return result
        except PipelineError as e:
            logger.error(f"RAG pipeline failed: {e}", exc_info=True)
            # Return an error state or raise
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error during RAG pipeline execution: {e}", exc_info=True
            )
            raise


# In main.py or your application entry point:
# ... initialize all components (fetcher, pipelines, vs/manifest, config) ...
# orchestrator = QueryOrchestrator(rag_pipeline, indexing_pipeline, fetcher, vector_store, config)
# response = orchestrator.handle_query("What were the main risks discussed in the latest AAPL 10-K?")
# print(response)
