import logging
from datetime import date
from datetime import datetime
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Union
from typing import get_args
from typing import get_origin
from uuid import UUID

import weaviate
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever
from langchain_core.vectorstores import VectorStore
from langchain_weaviate.vectorstores import WeaviateVectorStore as LCWeaviate
from pydantic import BaseModel
from weaviate import WeaviateClient
from weaviate.classes.config import DataType
from weaviate.classes.config import Property

from infra.config.settings import get_settings
from infra.vector_stores.models import IVectorStore


logger = logging.getLogger(__name__)


class WeaviateVectorStore(IVectorStore):
    """Weaviate vector store implementation.

    This class implements the IVectorStore interface and provides methods for
    interacting with a Weaviate vector database.
    """

    def __init__(
        self,
        index_name: str = "langchain",
        client: Any = None,
        text_key: str = "page_content",
    ):
        self._client = client
        self._collection_name = index_name
        self._text_key = text_key
        self._vectorstore = None  # Lazy loading

    def _close(self):
        if self._client is not None:
            self._client.close()
            self._client = None

    def _get_client(self) -> WeaviateClient:
        if self._client is None:
            logger.info(f"Initializing Weaviate client...")
            self._client = weaviate.connect_to_custom(
                http_host=get_settings().WEAVIATE_HTTP_URL,
                grpc_host=get_settings().WEAVIATE_GRPC_URL,
                grpc_port=50051,
                http_port=80,
                grpc_secure=False,
                http_secure=False,
            )
        return self._client

    def _initialize(self, embeddings: Embeddings, metadata: Dict = None) -> VectorStore:
        if self._vectorstore is None:
            logger.info(
                f"Initializing Weaviate for collection: {self._collection_name}..."
            )
            self._vectorstore = LCWeaviate(
                client=self._get_client(),
                index_name=self._collection_name,
                text_key=self._text_key,
                embedding=embeddings,
            )

        if not metadata:
            return self._vectorstore
        self._ensure_class_exists(self._collection_name, metadata)
        return self._vectorstore

    def get_vectorstore(self, embeddings: Embeddings) -> VectorStore:
        return self._initialize(embeddings)

    def add_documents(self, documents: List[Document], embeddings: Embeddings) -> None:
        if not documents:
            logger.warning("No documents to add.")
            return

        logger.info(
            f"Adding {len(documents)} documents to Weaviate collection '{self._collection_name}'..."
        )
        try:
            instance = self.get_vectorstore(embeddings)
            uuids = instance.add_documents(documents)
            logger.info(f"Documents added: {len(uuids)}")
            self._close()
        except Exception as e:
            logger.error(f"Failed to add documents: {str(e)}")
            raise RuntimeError(f"Failed to add documents: {str(e)}") from e

    def as_retriever(
        self,
        embeddings: Embeddings,
        search_type: str = "similarity",
        search_kwargs: Optional[Dict[str, Any]] = None,
    ) -> BaseRetriever:
        logger.info(
            f"Creating retriever for Weaviate collection '{self._collection_name}' with search_type '{search_type}'..."
        )
        try:
            vs = self.get_vectorstore(embeddings)
            weaviate_search_kwargs = {"k": search_kwargs.get("k", 10)}
            # if "filter" in search_kwargs:
            #     weaviate_search_kwargs["where"] = self.convert_metadata_to_where_clause(search_kwargs.get("filter"))
            return vs.as_retriever(
                search_type=search_type, search_kwargs=weaviate_search_kwargs
            )
        except Exception as e:
            raise RuntimeError(f"Failed to create retriever: {str(e)}") from e

    def convert_metadata_to_where_clause(self, metadata: dict) -> dict:
        """Convert metadata filter to Weaviate v4.x where filter format."""
        # In Weaviate v4.x, filters use a different structure
        where_filter = {}

        for key, value in metadata.items():
            # Handle different value types
            if isinstance(value, str):
                where_filter[key] = {"$eq": value}
            elif isinstance(value, (int, float)):
                where_filter[key] = {"$eq": value}
            elif isinstance(value, bool):
                where_filter[key] = {"$eq": value}
            elif isinstance(value, list):
                where_filter[key] = {"$in": value}
            else:
                # Default to string equality for other types
                where_filter[key] = {"$eq": str(value)}

        return where_filter

    def set_collection(self, name: str, metadata: Dict):
        self._collection_name = name
        self._ensure_class_exists(name, metadata)
        self._vectorstore = None

    @property
    def collection_name(self) -> str:
        return self._collection_name

    def _ensure_class_exists(self, collection_name: str, metadata: Dict):
        # Updated for Weaviate v4.x API
        existing_classes = list(
            self._get_client().collections.list_all(simple=True).keys()
        )
        class_exists = collection_name in existing_classes
        properties = {
            k: Property(
                name=k,
                data_type=self._get_weaviate_type(type(v)),
                skip_vectorization=True,
            )
            for k, v in metadata.items()
        }
        properties[self._text_key] = Property(
            name=self._text_key, data_type=DataType.TEXT
        )

        if not class_exists:
            self._get_client().collections.create(
                name=collection_name,
                vectorizer_config=None,  # Using external embeddings with "none" vectorizer
                properties=list(properties.values()),
            )
            return

        # Add missing properties to existing class
        if class_exists:
            collection = self._get_client().collections.get(collection_name)
            existing_props = {
                prop.name for prop in collection.config.get(simple=True).properties
            }
            for prop_name, prop in properties.items():
                if prop_name not in existing_props:
                    collection.config.add_property(prop)

    def _get_weaviate_type(self, annotation: type) -> str:
        origin = get_origin(annotation)
        args = get_args(annotation)

        # Handle Optional[T]
        if origin is Union and type(None) in args:
            non_none_args = [arg for arg in args if arg is not type(None)]
            if non_none_args:
                return self._get_weaviate_type(non_none_args[0])

        # Handle List[T] or list[T]
        if origin in {list, List}:
            inner_type = args[0]
            return {
                str: DataType.TEXT_ARRAY,
                int: DataType.INT_ARRAY,
                bool: DataType.BOOL_ARRAY,
                float: DataType.NUMBER_ARRAY,
                date: DataType.DATE_ARRAY,
                datetime: DataType.DATE_ARRAY,
                UUID: DataType.UUID_ARRAY,
                BaseModel: DataType.OBJECT_ARRAY,
            }.get(inner_type, DataType.TEXT_ARRAY)

        # Scalar type mapping
        return {
            str: DataType.TEXT,
            int: DataType.INT,
            bool: DataType.BOOL,
            float: DataType.NUMBER,
            date: DataType.DATE,
            datetime: DataType.DATE,
            UUID: DataType.UUID,
            BaseModel: DataType.OBJECT,
        }.get(annotation, DataType.TEXT)
