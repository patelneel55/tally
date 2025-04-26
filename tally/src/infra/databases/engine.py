import logging

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from infra.config.settings import get_settings


logger = logging.getLogger(__name__)

# Create the engine instance as a singleton
_sql_alchemy_instance: Engine | None = None


def get_sqlalchemy_engine() -> Engine:
    global _sql_alchemy_instance
    if _sql_alchemy_instance is None:
        try:
            _sql_alchemy_instance = create_engine(
                get_settings().DB_ENGINE_URL, pool_size=5, max_overflow=10, echo=False
            )
            with _sql_alchemy_instance.connect() as connection:
                logger.info(
                    f"Successfully connected to database via engine: {_sql_alchemy_instance.url.render_as_string(hide_password=True)}"
                )

        except OperationalError as e:
            logger.error(f"!!! Database connection failed: {e} !!!")
            logger.error(
                f"Database URL used (password hidden): {_sql_alchemy_instance.url.render_as_string(hide_password=True)}"
            )
            # Decide how to handle this - exit, raise, etc.
            raise ConnectionError("Failed to create database engine.") from e
        except Exception as e:
            logger.error(
                f"!!! Failed to create database engine: {e} !!!", exc_info=True
            )
            raise ConnectionError("Failed to create database engine.") from e
    return _sql_alchemy_instance
