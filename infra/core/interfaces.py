"""
Core Interfaces
--------------

This module defines the core interfaces used throughout the infrastructure
layer. These interfaces establish the contract that all concrete implementations
must follow.
"""

import abc
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional, Union

# Import base types from LangChain for interoperability
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseLanguageModel
from langchain_core.output_parsers import BaseOutputParser
from langchain_core.prompts import BasePromptTemplate
from langchain_core.retrievers import BaseRetriever
from langchain_core.vectorstores import VectorStore
from infra.acquisition.models import AcquisitionOutput

class IDataFetcher(ABC):
    """
    Abstract base class for data fetchers.

    This interface defines the contract that all data fetchers must implement.
    It provides a standardized way to fetch data from various sources while
    maintaining consistent error handling and response formats.
    """

    @abstractmethod
    async def fetch(self, **kwargs) -> Any:
        """
        Fetch data for a given identifier.

        Args:
            identifier: List of unique identifiers for the data to fetch (e.g., ticker symbol)
            **kwargs: Additional parameters specific to the data source

        Returns:
            The fetched data in a standardized format

        Raises:
            DataFetchError: If the data cannot be fetched
            ValidationError: If the input parameters are invalid
        """
        pass

    # @abstractmethod
    # async def fetch_batch(self, identifiers: List[str], **kwargs) -> Dict[str, Any]:
    #     """
    #     Fetch data for multiple identifiers in parallel.

    #     Args:
    #         identifiers: List of unique identifiers
    #         **kwargs: Additional parameters specific to the data source

    #     Returns:
    #         Dictionary mapping identifiers to their fetched data

    #     Raises:
    #         DataFetchError: If any of the data cannot be fetched
    #         ValidationError: If the input parameters are invalid
    #     """
    #     pass

    # @abstractmethod
    # async def fetch_historical(
    #     self,
    #     identifier: str,
    #     start_date: Optional[Union[datetime, date]] = None,
    #     end_date: Optional[Union[datetime, date]] = None,
    #     **kwargs
    # ) -> List[Any]:
    #     """
    #     Fetch historical data for a given identifier.

    #     Args:
    #         identifier: Unique identifier for the data to fetch
    #         start_date: Start date for historical data
    #         end_date: End date for historical data
    #         **kwargs: Additional parameters specific to the data source

    #     Returns:
    #         List of historical data points

    #     Raises:
    #         DataFetchError: If the historical data cannot be fetched
    #         ValidationError: If the input parameters are invalid
    #     """
    #     pass

    # @abstractmethod
    # def validate_identifier(self, identifier: str) -> bool:
    #     """
    #     Validate if an identifier is in the correct format.

    #     Args:
    #         identifier: Identifier to validate

    #     Returns:
    #         True if the identifier is valid, False otherwise
    #     """
    #     pass

    # @abstractmethod
    # def get_rate_limit(self) -> Dict[str, int]:
    #     """
    #     Get the rate limits for this data fetcher.

    #     Returns:
    #         Dictionary containing rate limit information:
    #         {
    #             "requests_per_second": int,
    #             "requests_per_minute": int,
    #             "requests_per_hour": int
    #         }
    #     """
    #     pass


class IDocumentLoader(ABC):
    """
    Interface for loading data from a specific URI into LangChain
    Document objects.
    """

    @abstractmethod
    async def load(self, sources: List[AcquisitionOutput]) -> List[Document]:
        """
        Loads content from the given URI into Document objects.

        Args:
            source_uri: Concrete URI (e.g., "/path/to/file.pdf", "http://...").

        Returns:
            List of LangChain Document objects with initial content and metadata.

        Raises:
            IngestionError: If loading from the URI fails (e.g., file access error,
                            HTTP error).
            FileNotFoundError: If source_uri is a local path that doesn't exist.
        """
        pass


class IParser(ABC):
    """
    Abstract base class for parsers.

    This interface defines the contract that all parsers must implement.
    It provides a standardized way to parse data from various sources while
    maintaining consistent error handling and response formats.
    """

    SUPPORTED_FORMATS = Literal["json", "markdown"]

    @abstractmethod
    def parse(
        self, docs: List[Document], output_format: SUPPORTED_FORMATS = "markdown"
    ) -> List[Document]:
        """
        Loads and parses a file from the given path into LangChain Documents.

        Args:
            file_path: The path to the file to parse
            output_format: The format to output the parsed data in

        Returns:
            A list of LangChain Documents. Each Document typically contains
            a chunk of the parsed content, with the metadata containing the
            original file path and other relevant information.

        Raises:
            ParserError: If the file cannot be parsed
            FileNotFoundError: If the file does not exist
        """
        pass


class ISplitter(abc.ABC):
    """Interface for splitting documents into smaller chunks."""

    @abc.abstractmethod
    def split_documents(self, documents: List[Document]) -> List[Document]:
        """
        Splits a list of documents into smaller chunks suitable for LLM context windows.

        Args:
            documents: A list of LangChain Document objects.

        Returns:
            A list of chunked LangChain Document objects.
        """
        pass


class IEmbeddingProvider(abc.ABC):
    """Interface for providing text embedding models."""

    @abc.abstractmethod
    def get_embedding_model(self) -> Embeddings:
        """
        Returns a configured LangChain Embeddings instance
        (e.g., OpenAIEmbeddings, HuggingFaceEmbeddings).

        Returns:
            A LangChain Embeddings object.

        Raises:
            ConfigurationError: If the embedding model cannot be configured/loaded.
        """
        pass


class IVectorStore(abc.ABC):
    """Interface for interacting with vector databases."""

    @abc.abstractmethod
    def get_vectorstore(self, embeddings: Embeddings) -> VectorStore:
        """
        Gets or initializes the underlying LangChain VectorStore instance,
        configured with the provided embedding function.

        Args:
           embeddings: The LangChain Embeddings object to use.

        Returns:
            A configured LangChain VectorStore instance.

        Raises:
            VectorStoreError: If the vector store cannot be accessed or initialized.
        """
        pass

    @abc.abstractmethod
    def add_documents(self, documents: List[Document], embeddings: Embeddings):
        """
        Embeds and adds/updates documents in the vector store.

        Args:
            documents: A list of LangChain Document objects to add.
            embeddings: The LangChain Embeddings object to use for embedding.

        Raises:
            VectorStoreError: If adding documents fails.
            EmbeddingError: If embedding the documents fails.
        """
        pass

    @property
    @abc.abstractmethod
    def collection_name(self) -> str:
        pass

    @abc.abstractmethod
    def set_collection(self, name: str, metadata: Dict):
        pass

    @abc.abstractmethod
    def as_retriever(
        self,
        embeddings: Embeddings,
        search_type: str = "similarity",
        search_kwargs: Optional[Dict[str, Any]] = None,
    ) -> BaseRetriever:
        """
        Returns a LangChain retriever configured for this vector store.

        Args:
            embeddings: The LangChain Embeddings object to use.
            search_type: The type of search to perform (e.g., "similarity", "mmr").
            search_kwargs: Dictionary of keyword arguments for the search (e.g., {"k": 4}).

        Returns:
            A configured LangChain BaseRetriever instance.

        Raises:
            VectorStoreError: If the retriever cannot be created.
        """
        pass


class IPromptStrategy(abc.ABC):
    """Interface for creating LLM prompts based on different strategies."""

    @abc.abstractmethod
    def create_prompt(
        self,
        context: Dict[str, Any],
        task_description: str,
        retrieved_docs: Optional[List[Document]] = None,
    ) -> BasePromptTemplate:
        """
        Creates a LangChain prompt template based on the specific strategy.
        For RAG strategies, it should incorporate the retrieved_docs.

        Args:
            context: A dictionary containing general context information
                     (might include specific document chunks if not RAG).
            task_description: A description of the task for the LLM.
            retrieved_docs: Optional list of relevant documents retrieved
                             from the vector store for RAG pipelines.

        Returns:
            A configured LangChain BasePromptTemplate instance.
        """
        pass


class ILLMProvider(abc.ABC):
    """Interface for providing configured LLM instances."""

    @abc.abstractmethod
    def get_model(self) -> BaseLanguageModel:
        """
        Returns a configured LangChain BaseLanguageModel instance
        (e.g., ChatOpenAI, ChatAnthropic).

        Returns:
            A LangChain BaseLanguageModel object.

        Raises:
            ConfigurationError: If the LLM cannot be configured/loaded.
            LLMError: If there's an issue communicating with the LLM API during setup.
        """
        pass


class IOutputFormatter(abc.ABC):
    """Interface for formatting the final output of the analysis."""

    @abc.abstractmethod
    def get_parser(self) -> BaseOutputParser:
        """
        Returns a LangChain BaseOutputParser instance configured to parse
        the expected LLM response format (e.g., JsonOutputParser, StrOutputParser).

        Returns:
            A LangChain BaseOutputParser instance.
        """
        pass

    @abc.abstractmethod
    def format(self, parsed_data: Any) -> str:
        """
        Formats the data parsed by the output parser into the final desired
        string representation (e.g., a JSON string, CSV row, Markdown text).

        Args:
            parsed_data: The data structure returned by this formatter's associated parser.

        Returns:
            A string containing the final formatted output.

        Raises:
            OutputFormattingError: If formatting fails.
        """
        pass


class IPipelineStep(abc.ABC):
    """Optional: Interface for defining a single, reusable step within a pipeline."""

    @abc.abstractmethod
    def execute(self, input_data: Any) -> Any:
        """
        Executes the logic of this pipeline step.

        Args:
            input_data: Data passed from the previous step or initial input.

        Returns:
            Output data to be passed to the next step or as the final result.

        Raises:
             PipelineError: Or a more specific subclass if execution fails.
        """
        pass
