"""
Weaviate Vector Store
------------------

This module provides a vector store implementation using Weaviate as the backend.
It implements the IVectorStore interface and provides additional methods for
managing documents in the vector store.
"""

import logging
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

import weaviate
from langchain_community.retrievers import WeaviateHybridSearchRetriever
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever
from langchain_core.vectorstores import VectorStore
from weaviate import Client
from weaviate.classes.config import DataType, Property
from weaviate.exceptions import WeaviateBaseError

from infra.core.config import settings
from infra.core.interfaces import IVectorStore

# @dataclass
# class WeaviateConfig:
#     """Configuration for Weaviate connection."""

#     url: str
#     api_key: Optional[str] = None
#     additional_headers: Optional[Dict[str, str]] = None
#     class_name: str = "Document"
#     batch_size: int = 100
#     text_field: str = "text"
#     metadata_field: str = "metadata"
logger = logging.getLogger(__name__)


class WeaviateVectorStore(IVectorStore):
    """Weaviate vector store implementation.

    This class implements the IVectorStore interface and provides methods for
    interacting with a Weaviate vector database.
    """

    def __init__(
        self,
        index_name: str,
        client: Any = None,
    ):
        self._client = client
        self.collection_name = index_name
        self._vectorstore = None # Lazy loading

    def _get_client(self) -> Client:
        if self._client is None:
            logger.info(
                f"Initializing Weaviate client..."
            )
            weaviate.connect_to_custom(
                http_host=settings.WEAVIATE_HTTP_URL,
                grpc_host=settings.WEAVIATE_GRPC_URL,
                grpc_port=50051,
                http_port=80,
                grpc_secure=False,
                http_secure=False,
            )
        return self._client

    def _initialize(self, embeddings: Embeddings, metadata: Dict = None):
        if self._vectorstore is None:
            logger.info(
                f"Initializing Weaviate for collection: {self.collection_name}..."
            )
            self._vectorstore = WeaviateHybridSearchRetriever(
                client=self._get_client(),
                index_name=self.collection_name,
                embedding=embeddings
            )

        if not metadata:
            return

        schema = self._get_client().schema.get()
        existing_classes = {c["class"]: c for c in schema["classes"]}
        class_exists = self.collection_name in existing_classes
        properties = [
            Property(name=k, dataType=self._get_weviate_type(v))
            for k, v in metadata.items()
        ]
        properties.append(Property(name="page_content", dataType=DataType.TEXT))

        if not class_exists:
            self._get_client().schema.create_class({
                "class": self.collection_name,
                "vectorizer": "none", # Using external embeddings
                "properties": properties,
            })
            return

        existing_properties = {p["name"] for p in existing_classes[self.collection_name]["properties"]}
        for k, v in metadata:

        schema = self._get_client().schema.get()
        if not any(c["class"] == self.collection_name for c in schema["classes"]):



    def _dict_to_weaviate_properties(dict: Dict) -> List[Dict]:
        return []

    def get_metadata_properties():

    def get_vectorstore(self, embeddings: Embeddings):
        weaviate.connect_to_local()
        pass

    def add_documents(self, documents: List[Document], embeddings: Embeddings) -> None:
        pass

    def as_retriever(self, embeddings: Embeddings, search_type: str = "similarity", search_kwargs: Optional[Dict[str, Any]] = None) -> BaseRetriever:
        pass

    def get_metadata_properties(self):
        pass



    def __init__(self, config: WeaviateConfig):
        """Initialize Weaviate vector store.
        """


        self.config = config
        self._client = None
        self._schema_initialized = False

    def _connect(self) -> None:
        """Establish connection to Weaviate server.

        Raises:
            ConnectionError: If connection to Weaviate fails
        """
        if self._client is not None:
            return

        try:
            auth_config = (
                weaviate.auth.AuthApiKey(api_key=self.config.api_key)
                if self.config.api_key
                else None
            )

            self._client = weaviate.Client(
                url=self.config.url,
                auth_client_secret=auth_config,
                additional_headers=self.config.additional_headers,
            )

            # Check connection
            self._client.is_ready()

        except WeaviateBaseError as e:
            self._client = None
            raise ConnectionError(f"Failed to connect to Weaviate: {str(e)}") from e

    def _ensure_schema(self) -> None:
        """Ensures the required schema exists in Weaviate.

        Raises:
            RuntimeError: If schema creation fails
        """
        if self._schema_initialized:
            return

        self._connect()

        try:
            # Check if class already exists
            schema = self._client.schema.get()
            classes = (
                [c["class"] for c in schema["classes"]] if "classes" in schema else []
            )

            if self.config.class_name not in classes:
                # Create class if it doesn't exist
                class_obj = {
                    "class": self.config.class_name,
                    "vectorizer": "none",  # We'll supply vectors explicitly
                    "properties": [
                        {
                            "name": self.config.text_field,
                            "dataType": ["text"],
                        },
                        {
                            "name": self.config.metadata_field,
                            "dataType": ["object"],
                        },
                    ],
                }
                self._client.schema.create_class(class_obj)

            self._schema_initialized = True

        except WeaviateBaseError as e:
            raise RuntimeError(f"Failed to create or validate schema: {str(e)}") from e

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
        # This is a bit complex as we need to adapt to LangChain's Weaviate wrapper
        # For now, we'll return self as we're implementing our own methods
        # In a production environment, we would use LangChain's WeaviateVectorStore
        from langchain_community.vectorstores import Weaviate as LangChainWeaviate

        self._connect()
        self._ensure_schema()

        try:
            return LangChainWeaviate(
                client=self._client,
                index_name=self.config.class_name,
                text_key=self.config.text_field,
                embedding=embeddings,
                by_text=False,  # We're using our own embedding logic
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to initialize LangChain VectorStore: {str(e)}"
            ) from e

    def add_documents(self, documents: List[Document], embeddings: Embeddings) -> None:
        """
        Embeds and adds/updates documents in the vector store.

        Args:
            documents: A list of LangChain Document objects to add.
            embeddings: The LangChain Embeddings object to use for embedding.

        Raises:
            VectorStoreError: If adding documents fails.
            EmbeddingError: If embedding the documents fails.
        """
        self._connect()
        self._ensure_schema()

        try:
            # Extract texts for embedding
            texts = [doc.page_content for doc in documents]

            # Get embeddings
            embeddings_list = embeddings.embed_documents(texts)

            # Prepare batch
            with self._client.batch as batch:
                batch.batch_size = self.config.batch_size

                for i, doc in enumerate(documents):
                    # Generate UUID based on content or use existing id if available
                    doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, doc.page_content))

                    # Add to batch
                    batch.add_data_object(
                        data_object={
                            self.config.text_field: doc.page_content,
                            self.config.metadata_field: doc.metadata,
                        },
                        class_name=self.config.class_name,
                        uuid=doc_id,
                        vector=embeddings_list[i],
                    )

        except Exception as e:
            raise RuntimeError(
                f"Failed to add documents to vector store: {str(e)}"
            ) from e

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
        vectorstore = self.get_vectorstore(embeddings)

        try:
            search_kwargs = search_kwargs or {}
            return vectorstore.as_retriever(
                search_type=search_type, search_kwargs=search_kwargs
            )
        except Exception as e:
            raise RuntimeError(f"Failed to create retriever: {str(e)}") from e

    # Additional methods beyond the IVectorStore interface

    def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict]] = None,
        embeddings: Embeddings = None,
    ) -> List[str]:
        """Adds text documents and associated metadata to the vector store.

        Args:
            texts: List of text strings to add
            metadatas: Optional list of metadata dictionaries
            embeddings: The embeddings model to use

        Returns:
            List of UUIDs for the added documents

        Raises:
            ValueError: If embeddings model is not provided
            RuntimeError: If adding texts fails
        """
        if embeddings is None:
            raise ValueError("Embeddings model must be provided")

        self._connect()
        self._ensure_schema()

        metadatas = metadatas or [{} for _ in texts]
        if len(metadatas) != len(texts):
            raise ValueError("Number of metadata items must match number of texts")

        # Convert to Document objects
        documents = [
            Document(page_content=text, metadata=metadata)
            for text, metadata in zip(texts, metadatas)
        ]

        # Get embeddings
        try:
            # Extract texts for embedding
            embeddings_list = embeddings.embed_documents(texts)

            # Generate UUIDs for documents
            doc_ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, text)) for text in texts]

            # Prepare batch
            with self._client.batch as batch:
                batch.batch_size = self.config.batch_size

                for i, (text, metadata, doc_id) in enumerate(
                    zip(texts, metadatas, doc_ids)
                ):
                    # Add to batch
                    batch.add_data_object(
                        data_object={
                            self.config.text_field: text,
                            self.config.metadata_field: metadata,
                        },
                        class_name=self.config.class_name,
                        uuid=doc_id,
                        vector=embeddings_list[i],
                    )

            return doc_ids

        except Exception as e:
            raise RuntimeError(f"Failed to add texts: {str(e)}") from e

    def similarity_search(
        self, query: str, k: int = 4, embeddings: Embeddings = None
    ) -> List[Document]:
        """Returns the top-k most similar documents to the query.

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

        self._connect()
        self._ensure_schema()

        try:
            # Get query embedding
            query_embedding = embeddings.embed_query(query)

            # Perform vector search
            result = (
                self._client.query.get(
                    self.config.class_name,
                    [self.config.text_field, self.config.metadata_field],
                )
                .with_near_vector({"vector": query_embedding})
                .with_limit(k)
                .do()
            )

            # Extract results
            objects = result["data"]["Get"][self.config.class_name]

            # Convert to Document objects
            documents = []
            for obj in objects:
                text = obj[self.config.text_field]
                metadata = obj[self.config.metadata_field]
                documents.append(Document(page_content=text, metadata=metadata))

            return documents

        except Exception as e:
            raise RuntimeError(f"Failed to perform similarity search: {str(e)}") from e

    def delete(self, ids: List[str]) -> None:
        """Deletes documents by their IDs.

        Args:
            ids: List of UUIDs to delete

        Raises:
            RuntimeError: If deletion fails
        """
        self._connect()

        try:
            for doc_id in ids:
                self._client.data_object.delete(
                    uuid=doc_id, class_name=self.config.class_name
                )
        except Exception as e:
            raise RuntimeError(f"Failed to delete documents: {str(e)}") from e
