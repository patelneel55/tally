import logging
from datetime import datetime, timezone
from typing import Optional

from langchain_core.documents import Document

from infra.databases.cache import SQLAlchemyCache
from infra.databases.models import Cache
from infra.embeddings.models import IEmbeddingProvider
from infra.embeddings.providers import OpenAIEmbeddingProvider
from infra.utils import recursive_sort
from infra.vector_stores.models import IVectorStore
from infra.vector_stores.weaviate import WeaviateVectorStore


logger = logging.getLogger(__name__)

DEFAULT_TTL = 3600  # Default Time-To-Live for cache entries in seconds (1 hour)
DEFAULT_SEMANTIC_THRESHOLD = 0.9  # Default similarity threshold for semantic cache hits


class LLMCache(Cache):
    def __init__(
        self,
        cache_store: SQLAlchemyCache,
        llm_name: str,
        vector_store: Optional[IVectorStore] = None,
        embedding_provider: Optional[IEmbeddingProvider] = None,
        default_ttl: int = DEFAULT_TTL,
        default_semantic_threshold: float = DEFAULT_SEMANTIC_THRESHOLD,
        enable_exact_cache: bool = True,
        enable_semantic_cache: bool = True,
    ):
        self.cache_store = cache_store  # For storing actual LLM responses (exact match or semantic hit payload)
        self.embedding_provider = embedding_provider or OpenAIEmbeddingProvider()
        self.vector_store = (
            vector_store or WeaviateVectorStore()
        )  # For storing embeddings for semantic search

        self.default_ttl = default_ttl
        self.default_semantic_threshold = default_semantic_threshold

        self.enable_exact_cache = enable_exact_cache
        self.enable_semantic_cache = enable_semantic_cache

        if self.enable_semantic_cache and (not embedding_provider or not vector_store):
            raise ValueError(
                "Semantic caching enabled but embedding_provider or vector_store is missing."
            )

        self.stats = {"exact_hits": 0, "semantic_hits": 0, "misses": 0, "errors": 0}
        logger.debug(
            f"LLMCacheManager initialized. Exact Cache: {self.enable_exact_cache}, Semantic Cache: {self.enable_semantic_cache}"
        )
        if self.enable_semantic_cache:
            logger.debug(f"  Semantic threshold: {self.default_semantic_threshold}")
        self._llm_provider = llm_name

    def _get_cache_key_metadata(
        self, prompt: str, llm_kwargs: Optional[dict] = None
    ) -> dict:
        metadata = {
            "embedding_model": "TEMP",  # TODO(neelp): Add model here
            "prompt": prompt,
            "llm_provider": self._llm_provider,
            "llm_kwargs": llm_kwargs,
        }

        return recursive_sort(metadata)

    def get(
        self,
        key: str,
        semantic_threshold: Optional[float] = None,
        llm_kwargs: Optional[dict] = None,
    ) -> str | None:
        semantic_threshold = semantic_threshold or self.default_semantic_threshold

        # Try to find exact match else use semantic match
        if self.enable_exact_cache:
            cache_key = self.cache_store.generate_id(
                self._get_cache_key_metadata(key, llm_kwargs)
            )
            response = self._retrieve_cache_response(cache_key)
            if response:
                return response

        # Try semantic caching instead if exact cache is not a match
        if self.enable_semantic_cache:
            embeddings = self.embedding_provider.get_embedding_model()
            retriever = self.vector_store.as_retriever(
                embeddings,
                search_type="similarity_score_threshold",
                search_kwargs={
                    "score_threshold": semantic_threshold,
                    "k": 1,
                },
            )
            documents = retriever.invoke(key)
            if documents:
                document = documents[0]
                cache_key = document.metadata["cache_key"]
                response = self._retrieve_cache_response(self, cache_key)
                if response:
                    return response
                else:
                    # Cleanup embeddings if there is a semantic match but there is no
                    # associated cache entry in the cache_store
                    self.vector_store.delete([document.metadata["id"]])
        return None

    def write(
        self,
        key: str,
        ttl: Optional[int] = None,
        content: str = "",
        llm_kwargs: Optional[dict] = None,
    ):
        cache_key = self.cache_store.generate_id(
            self._get_cache_key_metadata(key, llm_kwargs)
        )
        if not self.cache_store.write(cache_key, ttl, response=content):
            return False

        if self.enable_semantic_cache:
            try:
                document = Document(
                    page_content=key,
                    metadata={
                        "cache_key": cache_key,
                        "created_at": datetime.now(timezone.utc),
                        **self._get_cache_key_metadata(key, llm_kwargs),
                    },
                )
                self.vector_store.add_documents(
                    documents=[document],
                    embeddings=self.embedding_provider.get_embedding_model(),
                )
            except Exception as e:
                logger.error(
                    f"Error adding documents: {e}",
                    exc_info=True,
                )
                return False
        return True

    def _retrieve_cache_response(self, cache_key: str) -> str:
        cache_entry = self.cache_store.get(cache_key)
        if cache_entry:
            if not hasattr(cache_entry, "response"):
                raise ValueError(
                    f"Cache is expected to have 'response' column for LLM caching: {self.cache_store.table_name}"
                )
            self.stats["exact_hits"] += 1
            return cache_entry["response"]
        return None
