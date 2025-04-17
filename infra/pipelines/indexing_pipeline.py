"""
Indexing Pipeline
----------------

This module contains the implementation of the IndexingPipeline, which
handles the process of fetching, loading, parsing, chunking and storing
documents in a vector database.
"""

import logging
import os
from typing import List, Optional, Union

from infra.acquisition.sec_fetcher import (
    DataFormat,
    EDGARFetcher,
    FilingType,
    SECFiling,
)
from infra.core.interfaces import (
    IDataFetcher,
    IDocumentLoader,
    IEmbeddingProvider,
    IParser,
    ISplitter,
    IVectorStore,
    ILLMProvider,
)
from infra.ingestion.web_loader import WebLoader
from infra.parsers.html_parser import HTMLParser
from infra.parsers.pdf_parser import PDFParser
from infra.preprocessing.markdown_splitter import MarkdownSplitter
from infra.preprocessing.sec_parser import SECParser, SECSplitter
from infra.vector_stores.chromadb import ChromaVectorStore

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class IndexingPipeline:
    """
    Pipeline for fetching, processing, and indexing documents.
    Handles the complete workflow from data acquisition to vector store embedding.
    """

    def __init__(
        self,
        fetcher: Optional[IDataFetcher] = None,
        loader: Optional[IDocumentLoader] = None,
        parser: Optional[IParser] = None,
        splitter: Optional[ISplitter] = None,
        embedding_provider: Optional[IEmbeddingProvider] = None,
        llm_provider: Optional[ILLMProvider] = None,
        vector_store: Optional[IVectorStore] = None,
        cache_dir: str = "cache/saved_documents",
        should_save_intermediates: bool = False,
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
            cache_dir: Directory to save intermediate documents if should_save_intermediates is True
            should_save_intermediates: Whether to save intermediate documents to disk
        """
        # Initialize with provided components or defaults
        self.fetcher = fetcher or EDGARFetcher()
        self.loader = loader or WebLoader(crawl_strategy="all", max_crawl_depth=0)
        self.parser = parser or SECParser()
        self.llm_provider = llm_provider
        self.splitter = splitter or SECSplitter(llm_provider=self.llm_provider)
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.cache_dir = cache_dir
        self.should_save_intermediates = should_save_intermediates

        # Create cache directory if needed
        if self.should_save_intermediates:
            os.makedirs(self.cache_dir, exist_ok=True)

    def save_docs(self, docs, step, ticker, doc_type, ext):
        """
        Save the documents to the specified location for debugging/caching.

        Args:
            docs: List of documents to save
            step: Processing step name (for filename)
            ticker: Company ticker symbol
            doc_type: Type of document (e.g., 10-K)
            ext: File extension to use
        """
        if not self.should_save_intermediates:
            return

        for i, doc in enumerate(docs):
            url_hash = hash(doc.metadata.get("source", "unknown"))
            output_path = (
                f"{self.cache_dir}/{step}/{ticker}_{doc_type}_{url_hash}_{i}.{ext}"
            )

            # Create directory if it doesn't exist
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            # Write document to file
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(f"{doc.page_content}\n\n")

            logger.info(
                f"Document {doc.metadata.get('source', 'unknown')}, index {i} written to {output_path}"
            )

    async def run(
        self,
        *,
        identifier: str,
        filing_type: Union[FilingType, str],
        data_format: DataFormat = DataFormat.HTML,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ):
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
        logger.info(f"Starting indexing pipeline for {identifier} {filing_type.value}")

        # Convert string filing type to enum if needed
        if isinstance(filing_type, str):
            filing_type = FilingType(filing_type)

        try:
            # Step 1: Fetch filings
            filings = await self.fetcher.fetch(
                identifiers=[identifier],
                filing_type=filing_type,
                data_format=data_format,
                start_date=start_date,
                end_date=end_date,
            )
            logger.info(
                f"Found {len(filings)} {filing_type.value} filings for {identifier}"
            )

            # Step 2: Load documents
            docs = await self.loader.load(filings)
            logger.info(f"Loaded {len(docs)} documents")
            if self.should_save_intermediates:
                self.save_docs(docs, "load", identifier, filing_type.value, "html")

            # Step 3: Parse documents
            parsed_docs = self.parser.parse(docs)
            logger.info(f"Parsed into {len(parsed_docs)} documents")
            if self.should_save_intermediates:
                self.save_docs(
                    parsed_docs, "parse", identifier, filing_type.value, "md"
                )

            # Step 4: Split documents
            split_docs = await self.splitter.split_documents(parsed_docs)
            logger.info(f"Split into {len(split_docs)} chunks")
            if self.should_save_intermediates:
                self.save_docs(split_docs, "split", identifier, filing_type.value, "md")

            # Step 5: Embed and index documents
            if self.embedding_provider and self.vector_store:
                embedding_model = self.embedding_provider.get_embedding_model()
                self.vector_store.add_documents(split_docs, embedding_model)
                logger.info(f"Indexed {len(split_docs)} document chunks")
            else:
                logger.warning(
                    "Embedding provider or vector store not provided, skipping indexing step"
                )

            return split_docs

        except Exception as e:
            logger.error(
                f"Error in indexing pipeline for {identifier} {filing_type.value}: {e}"
            )
            raise
