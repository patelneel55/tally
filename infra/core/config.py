"""
Handles loading and validation of application configuration from various sources
like environment variables, .env files, and YAML configuration files.
"""

import logging
import os
from typing import Any, Dict, Optional, Union
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import yaml
from dotenv import load_dotenv

from .exceptions import ConfigurationError

logger = logging.getLogger(__name__)


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

    CACHE: str = Field("cache", alias="CACHE_DIR")

settings = Settings()
