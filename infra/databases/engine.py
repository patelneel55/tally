import logging

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from infra.core.config import settings

logger = logging.getLogger(__name__)

# Create the engine instance as a singleton
try:
    sqlalchemy_engine: Engine = create_engine(
        settings.DB_ENGINE_URL, pool_size=5, max_overflow=10, echo=False
    )
    with sqlalchemy_engine.connect() as connection:
        logger.info(
            f"Successfully connected to database via engine: {sqlalchemy_engine.url.render_as_string(hide_password=True)}"
        )

except OperationalError as e:
    logger.error(f"!!! Database connection failed: {e} !!!")
    logger.error(
        f"Database URL used (password hidden): {sqlalchemy_engine.url.render_as_string(hide_password=True)}"
    )
    # Decide how to handle this - exit, raise, etc.
    raise ConnectionError("Failed to create database engine.") from e
except Exception as e:
    logger.error(f"!!! Failed to create database engine: {e} !!!", exc_info=True)
    raise ConnectionError("Failed to create database engine.") from e
