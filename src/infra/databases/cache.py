import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Generator, Optional, Type

from sqlalchemy import DateTime, UnicodeText
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Query, declarative_base, mapped_column, sessionmaker

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from infra.config.settings import get_settings
from infra.databases.models import Cache
from infra.utils import find_project_root


# Setup logger
logger = logging.getLogger(__name__)


Base = declarative_base()


def bootstrap_migrations(engine: Engine, alembic_ini_path: str = "alembic.ini"):
    alembic_cfg = Config(
        str(find_project_root(Path(__file__).resolve()) / alembic_ini_path)
    )
    alembic_cfg.set_main_option(
        "sqlalchemy.url", engine.url.render_as_string(hide_password=False)
    )

    command.upgrade(alembic_cfg, "head")
    if get_settings().AUTO_MIGRATE_DB:
        conn = engine.connect()
        mc = MigrationContext.configure(
            connection=conn,
            opts={
                "compare_type": True,
                "compare_server_default": True,
                "target_metadata": Base.metadata,
            },
        )
        diffs = compare_metadata(mc, Base.metadata)
        conn.close()

        if diffs:
            command.revision(
                alembic_cfg,
                message="SQLAlchemyCache: autogen schema change",
                autogenerate=True,
            )
            command.upgrade(alembic_cfg, "head")
        else:
            logger.debug("No schema changes detected; skipping revision step")


class SQLAlchemyCache(Cache):
    """
    A flexible caching implementation using SQLAlchemy, supporting dynamic table
    creation and different value storage types.
    """

    _orm_models: Dict[str, Type[Base]] = (
        {}
    )  # Class-level SQLAlchemyCache for generated ORM models

    _bootstrap_migrations = False

    def __init__(self, engine: Engine, table_name: str, column_mapping: Dict = None):
        """
        Initializes the SQLAlchemyCache for a specific table and value type.

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
        self._column_mapping = column_mapping or {}

        # Get or create the dynamic ORM model for this table/type combination
        self._cache_model = self._get_or_create_cache_model(
            table_name, column_mapping=self._column_mapping
        )
        # Create table if it doesn't exist using this specific model's metadata
        logger.info(f"Ensuring cache table '{self.table_name}' exists...")
        # Create only the specific table associated with this model
        if not SQLAlchemyCache._bootstrap_migrations:
            bootstrap_migrations(self.engine)
            SQLAlchemyCache._bootstrap_migrations = True
        logger.info(f"Cache table '{self.table_name}' ready.")

        # Create a configured "Session" class bound to the engine
        self._SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )
        logger.info(f"Cache initialized for table '{self.table_name}'.")

        if get_settings().USE_LOCAL_CACHE:
            self.cache_dir = Path(get_settings().LOCAL_CACHE_DIR) / self.table_name

    @classmethod
    def as_dict(cls, instance):
        return {c.name: getattr(instance, c.name) for c in instance.__table__.columns}

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

    def get_model(self) -> Any:
        return self._cache_model

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

    # --- Core Cache Methods ---

    def get(self, key: str) -> Any | None:
        """Retrieves and deserializes an item from the cache."""
        logger.debug(f"Getting cache from table '{self.table_name}' for key: {key}")
        try:
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

        expires_at = self._get_expiration_ts(ttl)

        try:
            with self._SessionLocal() as session:
                # Create ORM instance using the dynamic model
                entry = self._cache_model(
                    id=key,
                    expires_at=expires_at,
                    **kwargs,
                )
                session.merge(entry)
                session.commit()
                logger.debug(
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
                stmt = self.delete(self._cache_model).where(
                    self._cache_model.expires_at != None,  # noqa: E711
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

    @contextmanager
    def query_builder(
        self,
    ) -> Generator[Query, None, None]:  # Renamed to query_builder to clarify intent
        """
        Provides a SQLAlchemy Query object for building queries on the cache model.
        The underlying session is automatically committed (or rolled back on error)
        and closed upon exiting the 'with' block.

        Usage:
        with cache.query_builder() as q:
            results = q.filter_by(id='my_key').all()
            # ... perform more query operations within the same session context

        Returns:
            A SQLAlchemy Query object.
        """
        session = self._SessionLocal()
        try:
            yield session.query(self._cache_model)
            session.commit()
        except SQLAlchemyError as e:
            logger.error(f"Database error during query operation: {e}", exc_info=True)
            session.rollback()
            raise  # Re-raise the exception after logging and rolling back
        except Exception as e:
            logger.error(f"Unexpected error during query operation: {e}", exc_info=True)
            session.rollback()
            raise  # Re-raise the exception
        finally:
            session.close()
