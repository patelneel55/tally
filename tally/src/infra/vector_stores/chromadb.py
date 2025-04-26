import logging
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever
from langchain_core.vectorstores import VectorStore

from infra.vector_stores.models import IVectorStore


logger = logging.getLogger(__name__)


class ChromaVectorStore(IVectorStore):
    """
    Vector store implementation using Chroma as the backend.

    This class implements the IVectorStore interface and provides methods for
    interacting with a Chroma vector database.
    """

    DEFAULT_COLLECTION_NAME = "langchain"

    def __init__(
        self,
        persist_directory: str = "cache/db/chroma",
        collection_name: str = DEFAULT_COLLECTION_NAME,
    ):
        """
        Initialize Chroma vector store.

        Args:
            persist_directory: Directory to persist the Chroma database
            collection_name: Name of the collection in Chroma
        """
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        self.collection_name = collection_name
        self._vectorstore = None  # Lazy initialization

    def _initialize(self, embeddings: Embeddings) -> VectorStore:
        """
        Initialize Chroma database with the given embeddings.

        Args:
            embeddings: Embeddings function to use

        Returns:
            Initialized VectorStore
        """
        # Initialize Chroma only when needed, requires embedding function
        if (
            self._vectorstore is None
            or self._vectorstore._embedding_function != embeddings
        ):
            if self._vectorstore is not None:
                logger.warn("Reinitializing Chroma DB with new embedding function.")

            logger.info(
                f"Initializing Chroma DB for collection: {self.collection_name}..."
            )
            try:
                self._vectorstore = Chroma(
                    collection_name=self.collection_name,
                    embedding_function=embeddings,
                    persist_directory=str(self.persist_directory.resolve()),
                )
                logger.info(f"Chroma DB initialized at: {self.persist_directory}")
            except Exception as e:
                logger.error(f"Failed to initialize Chroma DB: {str(e)}")
                raise RuntimeError(f"Failed to initialize Chroma DB: {str(e)}") from e
        return self._vectorstore

    def get_vectorstore(self, embeddings: Embeddings) -> VectorStore:
        """
        Gets or initializes the underlying LangChain VectorStore instance,
        configured with the provided embedding function.

        Args:
           embeddings: The LangChain Embeddings object to use.

        Returns:
            A configured LangChain VectorStore instance.
        """
        return self._initialize(embeddings)

    def add_documents(self, documents: List[Document], embeddings: Embeddings) -> None:
        """
        Embeds and adds/updates documents in the vector store.

        Args:
            documents: A list of LangChain Document objects to add.
            embeddings: The LangChain Embeddings object to use for embedding.

        Raises:
            Exception: If adding documents fails.
        """
        if not documents:
            logger.warning("No documents to add.")
            return

        logger.info(
            f"Adding {len(documents)} documents to Chroma collection '{self.collection_name}'..."
        )
        try:
            instance = self.get_vectorstore(embeddings)
            uuids = instance.add_documents(documents)
            logger.info(f"Documents added: {len(uuids)}")
        except Exception as e:
            logger.error(f"Failed to add documents: {str(e)}")
            raise RuntimeError(f"Failed to add documents: {str(e)}") from e

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
            Exception: If the retriever cannot be created.
        """
        logger.info(
            f"Creating retriever for Chroma collection '{self.collection_name}' with search_type '{search_type}'..."
        )
        try:
            vs = self.get_vectorstore(embeddings)
            search_kwargs = search_kwargs or {"k": 10}  # Default to retrieve top 4
            return vs.as_retriever(search_type=search_type, search_kwargs=search_kwargs)
        except Exception as e:
            raise RuntimeError(f"Failed to create retriever: {str(e)}") from e

    def similarity_search(
        self, query: str, k: int = 4, embeddings: Embeddings = None
    ) -> List[Document]:
        """
        Returns the top-k most similar documents to the query.

        Args:
            query: The query text
            k: Number of documents to return
            embeddings: The embeddings model to use

        Returns:
            List of Document objects

        Raises:
            ValueError: If embeddings model is not provided
            RuntimeError: If search fails
        """
        if embeddings is None:
            raise ValueError("Embeddings model must be provided")

        try:
            vs = self.get_vectorstore(embeddings)
            return vs.similarity_search(query, k=k)
        except Exception as e:
            raise RuntimeError(f"Failed to perform similarity search: {str(e)}") from e

    def delete(self, ids: List[str]) -> None:
        """
        Deletes documents by their IDs.

        Args:
            ids: List of IDs to delete

        Raises:
            RuntimeError: If deletion fails
        """
        if not self._vectorstore:
            raise ValueError(
                "Vector store not initialized. Call get_vectorstore() first."
            )

        try:
            for doc_id in ids:
                self._vectorstore._collection.delete(ids=[doc_id])

            # Persist changes
            if self.persist_directory:
                self._vectorstore.persist()

        except Exception as e:
            raise RuntimeError(f"Failed to delete documents: {str(e)}") from e

    def get_document_by_id(self, doc_id: str) -> Optional[Document]:
        """
        Retrieves a document by its ID.

        Args:
            doc_id: ID of the document to retrieve

        Returns:
            Document object if found, None otherwise

        Raises:
            ValueError: If vector store is not initialized
            RuntimeError: If retrieval fails
        """
        if not self._vectorstore:
            raise ValueError(
                "Vector store not initialized. Call get_vectorstore() first."
            )

        try:
            # Get document from Chroma
            result = self._vectorstore._collection.get(ids=[doc_id])

            if not result or not result["documents"] or not result["documents"][0]:
                return None

            # Convert to Document
            text = result["documents"][0]
            metadata = (
                result["metadatas"][0]
                if result["metadatas"] and result["metadatas"][0]
                else {}
            )

            return Document(page_content=text, metadata=metadata)
        except Exception as e:
            raise RuntimeError(f"Failed to get document: {str(e)}") from e
