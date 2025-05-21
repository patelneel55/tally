from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Union

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever
from langchain_core.vectorstores import VectorStore
from pydantic import BaseModel, Field


FilterValuesTypeList = Union[
    Sequence[str], Sequence[bool], Sequence[float], Sequence[int], Sequence[datetime]
]
FilterValueType = Union[int, float, str, bool, datetime, None, FilterValuesTypeList]


class SearchKwargs(BaseModel):
    k: int = Field(10, description="Top k objects to be returned")
    filters: Dict[str, FilterValueType] = Field(
        None, description="The filters to apply on the semantic vector search"
    )


class IVectorStore(ABC):
    """Interface for interacting with vector databases."""

    @abstractmethod
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

    @abstractmethod
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
    @abstractmethod
    def collection_name(self) -> str:
        pass

    @abstractmethod
    def set_collection(self, name: str, metadata: Dict):
        pass

    @abstractmethod
    def as_retriever(
        self,
        embeddings: Embeddings,
        search_type: str = "similarity",
        search_kwargs: Optional[SearchKwargs] = None,
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

    @abstractmethod
    def delete(self, ids: List[str]) -> None:
        pass
