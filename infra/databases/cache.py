import hashlib
import json  # Added for JSON support
import logging
import os
import pickle
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Type

from parse import parse
from sqlalchemy import (
    Column,
    DateTime,
    Index,
    LargeBinary,
    MetaData,
    PickleType,
    String,
    Table,
    Text,
    UnicodeText,
    create_engine,
    delete,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, sessionmaker

from infra.core.config import settings

# Setup logger
logger = logging.getLogger(__name__)


class CacheValueType(Enum):
    Pickle = "pickle"
    Bytes = "bytes"
    Text = "text"


Base = declarative_base()


class Cache:
    """
    A flexible caching implementation using SQLAlchemy, supporting dynamic table
    creation and different value storage types.
    """

    _orm_models: Dict[str, Type[Base]] = (
        {}
    )  # Class-level cache for generated ORM models

    def __init__(self, engine: Engine, table_name: str, column_mapping: Dict = None):
        """
        Initializes the Cache for a specific table and value type.

        Args:
            engine: A configured SQLAlchemy Engine instance.
            table_name: The name of the table to use for this cache instance.
            key_length: Max length for the cache key string column.

        Raises:
            TypeError: If engine is not a valid Engine instance.
            ValueError: If value_type is invalid or key_length is non-positive.
            ConnectionError: If the cache table cannot be initialized.
        """
        if not isinstance(engine, Engine):
            raise TypeError("engine must be a valid SQLAlchemy Engine instance.")
        self.engine = engine
        self.table_name = table_name

        # Get or create the dynamic ORM model for this table/type combination
        self._cache_model = self._get_or_create_cache_model(
            table_name, column_mapping=column_mapping
        )

        # Create table if it doesn't exist using this specific model's metadata
        try:
            logger.info(f"Ensuring cache table '{self.table_name}' exists...")
            # Create only the specific table associated with this model
            self._cache_model.metadata.create_all(
                self.engine, tables=[self._cache_model.__table__]
            )
            logger.info(f"Cache table '{self.table_name}' ready.")
        except SQLAlchemyError as e:
            logger.error(
                f"Failed to create or access cache table '{self.table_name}': {e}",
                exc_info=True,
            )
            raise ConnectionError(
                f"Failed to initialize cache table '{self.table_name}'"
            ) from e

        # Create a configured "Session" class bound to the engine
        self._SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )
        logger.info(f"Cache initialized for table '{self.table_name}'.")

        if settings.USE_LOCAL_CACHE:
            self.cache_dir = Path(settings.LOCAL_CACHE_DIR) / self.table_name

    @classmethod
    def as_dict(cls, instance):
        return {c.name: getattr(instance, c.name) for c in instance.__table__.columns}

    @classmethod
    def generate_id(cls, data: Any) -> str:
        try:
            serialized_data = json.dumps(
                data,
                default=lambda o: o.isoformat() if isinstance(o, date) else str(o),
                sort_keys=True,
            )
        except (TypeError, ValueError) as e:
            if isinstance(data, str):
                serialized_data = data.strip()
            else:
                serialized_data = data
        hash_obj = hashlib.sha256()
        hash_obj.update(serialized_data.encode("utf-8"))
        return hash_obj.hexdigest()

    @classmethod
    def _get_or_create_cache_model(
        cls, table_name: str, column_mapping: Dict
    ) -> Type[Base]:
        """Dynamically creates or retrieves a SQLAlchemy ORM model class."""
        model_key = f"{table_name}"
        if model_key in cls._orm_models:
            return cls._orm_models[model_key]

        logger.debug(f"Creating dynamic ORM model for table '{table_name}'")

        # Dynamically create the class using type()
        # Ensure Base is the same instance across all models if mixing in one app
        model_name = f"{table_name.capitalize()}Entry"
        attrs = {
            "__tablename__": table_name,
            "id": mapped_column(UnicodeText, primary_key=True),
            "expires_at": mapped_column(
                DateTime(timezone=True), nullable=True, index=True
            ),
            "created_at": mapped_column(
                DateTime(timezone=True),
                default=lambda: datetime.now(timezone.utc),
                nullable=False,
            ),
            "__repr__": lambda self: f"<{model_name}(key='{self.id}', created_at={self.created_at}, expires_at={self.expires_at})>",
        }
        attrs.update(column_mapping or {})
        DynamicCacheEntry = type(model_name, (Base,), attrs)

        cls._orm_models[model_key] = DynamicCacheEntry
        return DynamicCacheEntry

    # --- Helper methods ---
    def _get_expiration_ts(self, ttl: Optional[int]) -> Optional[datetime]:
        """Calculates the expiration timestamp from a TTL in seconds."""
        if ttl is None:
            return None
        if not isinstance(ttl, int) or ttl < 0:
            raise ValueError("TTL must be non-negative int or None.")
        return datetime.now(timezone.utc) + timedelta(seconds=ttl)

    def _is_expired(
        self, entry: Optional[Any]
    ) -> bool:  # Accepts the dynamic model type
        """Checks if a retrieved ORM entry object is expired."""
        if entry is None:
            return True
        if entry.expires_at is None:
            return False
        return entry.expires_at <= datetime.now(timezone.utc)

    def _format_cache_file_content(self, expires_at, created_at, value):
        return f"Expires at: {expires_at}\nCreated at: {created_at}\nValue:\n{value}"

    def _format_file_content_from_cache(self, content: str):
        parsed = parse(
            "Created at: {created_at}Expires at: {expires_at}\nCreated at: {created_at}\nValue:\n{value}",
            content,
        )
        return parsed.named

    def _read_from_file(self, file_path: Path):
        """Reads a file from the local cache directory."""
        try:
            with open(file_path, "rb") as f:
                return self._format_file_content_from_cache(f.read())
        except Exception as e:
            logger.error(
                f"Error reading local cache file '{file_path}': {e}", exc_info=True
            )
            return None

    def _write_to_file(self, file_path: Path, expires_at, created_at, value):
        """Writes a file to the local cache directory."""
        try:
            with open(file_path, "wb") as f:
                content = self._format_cache_file_content(
                    expires_at.isoformat(), created_at.isoformat(), value
                )
                f.write(content.encode("utf-8"))
        except Exception as e:
            logger.error(
                f"Error writing local cache file '{file_path}': {e}", exc_info=True
            )

    # --- Core Cache Methods ---

    def check(self, key: str) -> bool:
        """Checks if a key exists and has not expired."""
        logger.debug(f"Checking cache table '{self.table_name}' for key: {key}")
        try:
            # # Check local cache first
            # if settings.USE_LOCAL_CACHE:
            #     local_cache_path = self.cache_dir / key
            #     if local_cache_path.exists():
            #         result = self._read_from_file(local_cache_path)
            #         if result is not None:
            #             expires_at = datetime.fromisoformat(result["expires_at"])
            #             return expires_at > datetime.now(timezone.utc)

            # Fallback to remote cache if local cache fails
            with self._SessionLocal() as session:
                entry = session.get(self._cache_model, key)
                return self._is_expired(entry)
        except SQLAlchemyError as e:
            logger.error(
                f"DB error checking key '{key}' in '{self.table_name}': {e}",
                exc_info=True,
            )
            return False  # Treat DB errors as cache miss
        except Exception as e:
            logger.error(
                f"Unexpected error checking key '{key}' in '{self.table_name}': {e}",
                exc_info=True,
            )
            return False

    def get(self, key: str) -> Any | None:
        """Retrieves and deserializes an item from the cache."""
        logger.debug(f"Getting cache from table '{self.table_name}' for key: {key}")
        try:
            # Check local cache first
            # if settings.USE_LOCAL_CACHE:
            #     local_cache_path = self.cache_dir / key
            #     if local_cache_path.exists():
            #         result = self._read_from_file(local_cache_path)
            #         if result is not None and not self._is_expired(result):
            #             if self.value_type == CacheValueType.Pickle:
            #                 return pickle.loads(result["value"])
            #             else:
            #                 return result["value"]

            with self._SessionLocal() as session:
                entry = session.get(self._cache_model, key)

                if self._is_expired(entry):
                    logger.debug(
                        f"Cache miss or expired for key '{key}' in '{self.table_name}'."
                    )
                    if entry is not None:  # Delete if expired
                        try:
                            session.delete(entry)
                            session.commit()
                        except SQLAlchemyError:
                            session.rollback()
                            logger.warning(f"Failed deleting expired key '{key}'.")
                    return None

                try:
                    logger.debug(f"Cache hit for key '{key}' in '{self.table_name}'.")
                    return Cache.as_dict(entry)
                except Exception as e:
                    logger.error(
                        f"Unexpected error deserializing cache value for key '{key}': {e}",
                        exc_info=True,
                    )
                    return None

        except SQLAlchemyError as e:
            logger.error(
                f"DB error getting key '{key}' from '{self.table_name}': {e}",
                exc_info=True,
            )
            return None
        except Exception as e:
            logger.error(
                f"Unexpected error getting key '{key}' from '{self.table_name}': {e}",
                exc_info=True,
            )
            return None

    def write(self, key: str, ttl: Optional[int] = None, **kwargs) -> bool:
        """Serializes and writes an item to the cache."""
        logger.debug(
            f"Writing cache to table '{self.table_name}' for key: {key}, ttl: {ttl}"
        )

        # # Serialize based on the value_type of this cache instance
        # serialized_value: Any = value
        # try:
        #     if self.value_type == CacheValueType.Pickle:
        #         serialized_value = pickle.dumps(value)
        # except (pickle.PicklingError, TypeError, json.JSONDecodeError) as ser_e:
        #     logger.error(
        #         f"Failed to serialize value for key '{key}' (type: {self.value_type}): {ser_e}. Value not cached.",
        #         exc_info=True,
        #     )
        #     return False
        # except Exception as e:
        #     logger.error(
        #         f"Unexpected error serializing value for key '{key}': {e}",
        #         exc_info=True,
        #     )
        #     return False

        expires_at = self._get_expiration_ts(ttl)

        try:
            # # Write to local cache if applicable
            # if settings.USE_LOCAL_CACHE:
            #     local_cache_path = self.cache_dir / key
            #     if local_cache_path.exists():
            #         self._write_to_file(
            #             local_cache_path,
            #             expires_at,
            #             datetime.now(timezone.utc),
            #             serialized_value,
            #         )
            #         result = self._read_from_file(local_cache_path)
            #         if result is not None and not self._is_expired(result):
            #             if self.value_type == CacheValueType.Pickle:
            #                 return pickle.loads(result["value"])
            #             else:
            #                 return result["value"]

            with self._SessionLocal() as session:
                # Create ORM instance using the dynamic model
                entry = self._cache_model(
                    id=key,
                    expires_at=expires_at,
                    **kwargs,
                )
                session.merge(entry)
                session.commit()
                logger.info(
                    f"Successfully wrote cache for key '{key}' in '{self.table_name}'."
                )
                return True
        except SQLAlchemyError as e:
            logger.error(
                f"DB error writing key '{key}' to '{self.table_name}': {e}",
                exc_info=True,
            )
            session.rollback()
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error writing key '{key}' to '{self.table_name}': {e}",
                exc_info=True,
            )
            return False

    def delete(self, key: str) -> bool:
        """Deletes an item from the cache."""
        logger.debug(f"Deleting cache from table '{self.table_name}' for key: {key}")
        try:
            # Delete from local cache if applicable
            # if settings.USE_LOCAL_CACHE:
            #     local_cache_path = self.cache_dir / key
            #     os.remove(local_cache_path) if local_cache_path.exists() else None

            with self._SessionLocal() as session:
                entry = session.get(self._cache_model, key)
                if entry:
                    session.delete(entry)
                    session.commit()
                    logger.info(
                        f"Successfully deleted cache for key '{key}' from '{self.table_name}'."
                    )
                    return True
                else:
                    logger.debug(
                        f"Key '{key}' not found in '{self.table_name}' for deletion."
                    )
                    return False
        except SQLAlchemyError as e:
            logger.error(
                f"DB error deleting key '{key}' from '{self.table_name}': {e}",
                exc_info=True,
            )
            session.rollback()
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error deleting key '{key}' from '{self.table_name}': {e}",
                exc_info=True,
            )
            return False

    def clear(self) -> bool:
        """Removes all entries from this specific cache table."""
        logger.warning(f"Clearing ALL entries from cache table '{self.table_name}'...")
        try:
            # if settings.USE_LOCAL_CACHE:
            #     local_cache_path = self.cache_dir
            #     os.rmdir(local_cache_path) if local_cache_path.exists() else None

            with self._SessionLocal() as session:
                num_deleted = session.query(self._cache_model).delete()
                session.commit()
                logger.info(
                    f"Successfully cleared {num_deleted} entries from '{self.table_name}'."
                )
                return True
        except SQLAlchemyError as e:
            logger.error(
                f"Database error clearing cache table '{self.table_name}': {e}",
                exc_info=True,
            )
            session.rollback()
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error clearing cache table '{self.table_name}': {e}",
                exc_info=True,
            )
            return False

    def prune_expired(self) -> int:
        """Deletes all expired cache entries from this specific cache table."""
        logger.info(f"Pruning expired entries from cache table '{self.table_name}'...")
        num_deleted = 0
        try:
            with self._SessionLocal() as session:
                stmt = delete(self._cache_model).where(
                    self._cache_model.expires_at != None,
                    self._cache_model.expires_at <= datetime.now(timezone.utc),
                )
                result = session.execute(stmt)
                session.commit()
                num_deleted = result.rowcount
                logger.info(
                    f"Successfully pruned {num_deleted} expired entries from '{self.table_name}'."
                )
        except SQLAlchemyError as e:
            logger.error(
                f"DB error pruning expired entries from '{self.table_name}': {e}",
                exc_info=True,
            )
            session.rollback()
        except Exception as e:
            logger.error(
                f"Unexpected error pruning expired entries from '{self.table_name}': {e}",
                exc_info=True,
            )
        return num_deleted
