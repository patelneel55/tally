from abc import ABC
from abc import abstractmethod
from enum import Enum

from langchain_core.embeddings import Embeddings


class IEmbeddingProvider(ABC):
    """Interface for providing text embedding models."""

    @abstractmethod
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


class OpenAIEmbeddingModels(str, Enum):
    SMALL3 = "text-embedding-3-small"
    LARGE3 = "text-embedding-3-large"
