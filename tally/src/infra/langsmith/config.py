"""LangSmith configuration module.

This module handles LangSmith configuration and initialization.
"""
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class LangSmithSettings(BaseSettings):
    """LangSmith configuration settings.
    
    Attributes:
        api_key: LangSmith API key
        project_name: Name of the project in LangSmith
        tracing_enabled: Whether to enable tracing
        endpoint: Optional custom endpoint for LangSmith
    """
    api_key: str = Field(..., description="LangSmith API key")
    project_name: str = Field(..., description="Name of the project in LangSmith")
    tracing_enabled: bool = Field(True, description="Whether to enable tracing")
    endpoint: Optional[str] = Field(None, description="Optional custom endpoint for LangSmith")

    class Config:
        """Pydantic configuration."""
        env_prefix = "LANGSMITH_"
        case_sensitive = False


def get_langsmith_settings() -> LangSmithSettings:
    """Get LangSmith settings from environment variables.
    
    Returns:
        LangSmithSettings: Configured LangSmith settings
    """
    return LangSmithSettings() 