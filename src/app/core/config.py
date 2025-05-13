"""
Configuration Settings
---------------------

This module contains all the configuration settings for the Analyst AI application.
It uses Pydantic to validate settings and environment variables, ensuring the app
has all the required values to function properly.

What this file does:
1. Defines application-wide settings (API versions, project names, etc.)
2. Loads and validates API keys for various financial data services
3. Sets up caching and rate limiting policies to optimize external API usage
4. Manages CORS configurations for web security

How it fits in the architecture:
- Central configuration hub accessed by all other modules
- Single source of truth for application settings
- Uses environment variables for sensitive data (API keys)

Financial importance:
- External financial APIs often have usage limits and costs
- Settings like caching and rate limiting help manage these costs
- Proper API key management ensures reliable access to financial data
"""

import os
from pathlib import Path
from typing import List, Union

from pydantic import AnyHttpUrl, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings with validation.

    This class uses Pydantic to:
    - Define the expected types of each setting
    - Provide default values where applicable
    - Validate values when the application starts
    - Load values from environment variables
    """

    # API configuration - defines how the API is structured and presented
    API_V1_STR: str = "/api/v1"  # Base URL prefix for API version 1
    PROJECT_NAME: str = "Analyst AI"  # Name displayed in documentation
    PROJECT_DESCRIPTION: str = (
        "AI-powered financial research assistant that automates "
        "stock valuation, investment research, and financial analysis."
    )  # Shown in API documentation
    VERSION: str = "0.1.0"  # Current software version (semantic versioning)

    # CORS configuration - controls which websites can access the API
    # This is critical for security when the API is called from web browsers
    CORS_ORIGINS: List[Union[str, AnyHttpUrl]] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:5173",
        "http://localhost:8000",
    ]

    # External API keys - credentials for accessing financial data services
    # These are intentionally loaded from environment variables for security
    # Each service provides different financial data and has different rate limits/costs
    POLYGON_API_KEY: str = os.getenv(
        "POLYGON_API_KEY", "5iq46sv8BkEtDKOUYeAVnTdqjXO44odg"
    )  # For real-time financial data
    SEC_API_KEY: str = os.getenv(
        "SEC_API_KEY",
        "e921f58fa84380083377ecee7781ba8945995f1e82112fb4b8593247f7408878",
    )  # For SEC filings and documents
    ALPHA_VANTAGE_API_KEY: str = os.getenv(
        "ALPHA_VANTAGE_API_KEY", ""
    )  # For stock data and fundamentals
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")  # For AI-powered analysis
    ANTHROPIC_API_KEY: str = os.getenv(
        "ANTHROPIC_API_KEY", ""
    )  # For Claude AI analysis

    # Directory settings
    # Important: This is the directory where data will be stored and is required by the excel_exporter
    DATA_DIR: str = "data"  # Directory for storing data files

    # Cache settings - helps reduce API calls to external services
    # Financial data doesn't change second-by-second, so caching makes sense
    # This both improves performance and reduces API costs
    CACHE_EXPIRY_MINUTES: int = 60  # How long to keep data before refreshing
    ENABLE_CACHE: bool = True  # Master switch for the caching system

    # Rate limiting - prevents hitting API rate limits
    # Financial data providers typically have strict rate limits
    # Exceeding these can result in temporary blocks or additional charges
    RATE_LIMIT_PER_MINUTE: int = 5  # Maximum allowed requests per minute

    # Environment setting - controls environment-specific behavior
    # This affects logging, debugging, and other development features
    ENVIRONMENT: str = os.getenv(
        "ENVIRONMENT", "development"
    )  # Options: development, testing, production

    # SEC Filing Analysis settings
    # These control how SEC filings are processed and analyzed
    SEC_FILING_CACHE_DIR: str = (
        "cache/sec_filings"  # Directory to store downloaded filings
    )
    SEC_ANALYSIS_CACHE_DIR: str = (
        "cache/sec_analysis"  # Directory to store analysis results
    )
    SEC_FILING_MAX_RETRIES: int = 5  # Maximum number of retries for SEC API requests
    SEC_FILING_RETRY_DELAY: int = 5  # Delay between retries in seconds
    SEC_ANALYSIS_MODEL: str = "gpt-4o"  # AI model for SEC filing analysis
    SEC_ANALYSIS_MAX_TOKENS: int = 4000  # Maximum tokens for AI analysis response
    SEC_ANALYSIS_PDF_DETAIL: str = "high"  # Detail level for PDF analysis (high/low)

    # Financial Analysis and Modeling settings
    FINANCIAL_ANALYSIS_MODEL: str = (
        "gpt-4o"  # AI model for financial analysis and modeling
    )
    FINANCIAL_ANALYSIS_MAX_TOKENS: int = 4000  # Maximum tokens for financial analysis

    # Premium SEC API settings
    SEC_API_PREMIUM: bool = True  # Whether premium API access is enabled
    SEC_API_PREMIUM_CONCURRENT_REQUESTS: int = (
        10  # Maximum concurrent requests for premium tier
    )
    SEC_API_PREMIUM_RATE_LIMIT: int = (
        20  # Requests per second for Query API (20 per second)
    )
    SEC_API_PREMIUM_SEARCH_RATE_LIMIT: int = (
        10  # Requests per second for Full-Text Search API (10 per second)
    )
    SEC_API_PREMIUM_EXTRACTOR_RATE_LIMIT: int = (
        10  # Requests per second for 10-K/10-Q/8-K Extractor API (10 per second)
    )
    SEC_API_PREMIUM_FILING_DOWNLOAD_LIMIT: int = (
        7000  # Filings per 5 minutes for Filing Download API (7,000 in 5 minutes)
    )
    SEC_API_PREMIUM_PDF_QUALITY: str = (
        "high"  # PDF quality for premium tier (high/medium/low)
    )

    @validator("CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, list):
            return v
        elif isinstance(v, str):
            return v
        raise ValueError(v)

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "env_file_encoding": "utf-8",
    }


# Create a singleton instance of settings
# This ensures the same settings object is used throughout the application
settings = Settings()
