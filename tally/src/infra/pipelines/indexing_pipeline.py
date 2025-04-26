"""
Indexing Pipeline
----------------

This module contains the implementation of the IndexingPipeline, which
handles the process of fetching, loading, parsing, chunking and storing
documents in a vector database.
"""

import logging
import os
from typing import List
from typing import Optional
from typing import Union

from infra.acquisition.models import IDataFetcher
from infra.acquisition.sec_fetcher import EDGARFetcher
from infra.embeddings.models import IEmbeddingProvider
from infra.ingestion.models import IDocumentLoader
from infra.ingestion.web_loader import WebLoader
from infra.llm.models import ILLMProvider
from infra.preprocessing.models import IParser
from infra.preprocessing.models import ISplitter
from infra.preprocessing.sec_parser import SECParser
from infra.preprocessing.sec_parser import SECSplitter
from infra.vector_stores.models import IVectorStore


# Set up logging
logger = logging.getLogger(__name__)


class IndexingPipeline:
    """
    Pipeline for fetching, processing, and indexing documents.
    Handles the complete workflow from data acquisition to vector store embedding.
    """

    def __init__(
        self,
        fetcher: IDataFetcher,
        loader: IDocumentLoader,
        parser: IParser,
        splitter: ISplitter,
        embedding_provider: IEmbeddingProvider,
        vector_store: IVectorStore,
    ):
        """
        Initialize the indexing pipeline with the necessary components.

        Args:
            fetcher: Component for fetching data from sources
            loader: Component for loading documents from sources
            parser: Component for parsing documents
            splitter: Component for splitting documents into chunks
            embedding_provider: Component for generating embeddings
            vector_store: Component for storing document vectors
        """
        # Initialize with provided components or defaults
        self.fetcher = fetcher
        self.loader = loader
        self.parser = parser
        self.splitter = splitter
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store

    async def run(self, **kwargs):
        """
        Run the complete indexing pipeline.

        Args:
            identifier: Entity identifier (e.g., ticker symbol)
            filing_type: Type of filing to fetch (e.g., QUARTERLY_REPORT)
            data_format: Format of data to fetch
            force_reindex: Whether to force reindexing even if data exists

        Returns:
            List of document chunks that were indexed
        """
        logger.info(f"Starting indexing pipeline")

        try:
            # Step 1: Fetch filings
            filings = await self.fetcher.fetch(**kwargs)
            logger.info(f"Found {len(filings)} filings")

            # Step 2: Load documents
            docs = await self.loader.load(filings)
            logger.info(f"Loaded {len(docs)} documents")

            # Step 3: Parse documents
            parsed_docs = self.parser.parse(docs)
            logger.info(f"Parsed into {len(parsed_docs)} documents")

            # Step 4: Split documents
            split_docs = await self.splitter.split_documents(parsed_docs)
            logger.info(f"Split into {len(split_docs)} chunks")

            # Step 5: Embed and index documents
            embedding_model = self.embedding_provider.get_embedding_model()
            self.vector_store.add_documents(split_docs, embedding_model)
            logger.info(f"Indexed {len(split_docs)} document chunks")

            return f"Successfully indexed {len(split_docs)} document chunks into the '{self.vector_store.collection_name}' collection. You may now search the collection for relevant documents."

        except Exception as e:
            logger.error(f"Error in indexing pipeline: {e}")
            raise
