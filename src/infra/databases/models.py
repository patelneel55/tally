import hashlib
import json
import logging
from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Optional


logger = logging.getLogger(__name__)


class Cache(ABC):
    def __init__(self):
        pass

    @classmethod
    def generate_id(cls, data: Any) -> str:
        try:
            serialized_data = json.dumps(
                data,
                default=lambda o: o.isoformat() if isinstance(o, date) else str(o),
                sort_keys=True,
            )
        except (TypeError, ValueError):
            if isinstance(data, str):
                serialized_data = data.strip()
            else:
                serialized_data = data
        hash_obj = hashlib.sha256()
        hash_obj.update(serialized_data.encode("utf-8"))
        return hash_obj.hexdigest()

    def check(self, key: str, ttl: Optional[int] = None, **kwargs) -> "CacheContext":
        return CacheContext(self, key, ttl, kwargs)

    @abstractmethod
    def get(self, key: str, **kwargs) -> Any | None:
        pass

    @abstractmethod
    def write(self, key: str, ttl: Optional[int] = None, **kwargs) -> None:
        pass


class CacheContext:
    def __init__(self, cache: Cache, key: str, ttl: Optional[int] = None, **kwargs):
        self.cache_store = cache
        self._is_hit = False
        self._cached_value = None
        self._value_to_cache = None

        self._key = key
        self.ttl = ttl
        self._kwargs = kwargs

    def __enter__(self):
        """Called when entering the 'with' block. Checks the cache"""
        self._cached_value = self.cache_store.get(self._key, **self._kwargs)
        if self._cached_value is not None:
            self._is_hit = True
        return self

    @property
    def is_hit(self) -> bool:
        return self._is_hit

    @property
    def should_compute(self) -> bool:
        return not self._is_hit

    @property
    def cache_value(self) -> Any:
        if self._value_to_cache:
            return self._value_to_cache
        return self._cached_value

    def set_value(self, **value_kwargs):
        self._value_to_cache = value_kwargs

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            logger.warning(
                f"CacheContext({self._key}): Exception occurred ('{exc_type.__name__}'). Not caching."
            )
            return False

        if self.should_compute and self._value_to_cache:
            logger.debug(f"CacheContext({self._key}): Cache MISS. Caching...")
            self.cache_store.write(self._key, ttl=self.ttl, **self._value_to_cache)
        elif self.should_compute and not self._value_to_cache:
            logger.debug(
                f"CacheContext({self._key}): Cache MISS. No value provided to cache."
            )
        elif self._is_hit:
            logger.debug(f"CacheContext({self._key}): Cache HIT.")
