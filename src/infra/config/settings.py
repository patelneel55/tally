"""
Handles loading and validation of application configuration from various sources
like environment variables, .env files, and YAML configuration files.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings with validation.

    This class uses Pydantic to:
    - Define the expected types of each setting
    - Provide default values where applicable
    - Validate values when the application starts
    - Load values from environment variables
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=True,
    )

    VERSION: str = "0.0.1"  # Current software version (semantic versioning)

    # External API keys - credentials for accessing financial data services
    # These are intentionally loaded from environment variables for security
    SEC_API_KEY: str = Field(..., alias="SEC_API_KEY")
    OPENAI_API_KEY: str = Field(..., alias="OPENAI_API_KEY")
    POLYGON_API_KEY: str = Field(..., alias="POLYGON_API_KEY")

    LOCAL_CACHE_DIR: str = Field("cache", alias="CACHE_DIR")
    USE_LOCAL_CACHE: bool = Field(False, alias="USE_LOCAL_CACHE")

    # Database configuration - connection string for the database
    # This should be set to a valid database URL
    # e.g., "postgresql://user:password@localhost/dbname"
    #
    # The databases will be used for caching and storing all relevant
    # data for the infrastructure
    DB_ENGINE_URL: str = Field(..., alias="DB_ENGINE_URL")
    WEAVIATE_HTTP_URL: str = Field(..., alias="WEAVIATE_HTTP_URL")
    WEAVIATE_GRPC_URL: str = Field(..., alias="WEAVIATE_GRPC_URL")

    SEC_API_CACHE_EXPIRATION: int = Field(
        60 * 60 * 24, alias="SEC_API_CACHE_EXPIRATION"
    )  # 1 day in seconds

    LANGSMITH_TRACING: bool = Field(False, alias="LANGSMITH_TRACING")
    LANGSMITH_API_KEY: str = Field(..., alias="LANGSMITH_API_KEY")
    LANGSMITH_ENDPOINT: str = Field(
        "https://api.smith.langchain.com", alias="LANGSMITH_ENDPOINT"
    )
    LANGSMITH_PROJECT: str = Field(..., alias="LANGSMITH_PROJECT")


_settings_instance: Settings | None = None


def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
