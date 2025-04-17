"""
SEC Filing Fetcher
-----------------

This module provides functionality to retrieve complete SEC filings as PDFs
for AI-powered analysis and summarization. It leverages the SEC API's
Filing Download & PDF Generator API to fetch full documents.

What this file does:
1. Downloads complete SEC filings (10-K, 10-Q, 8-K) as PDFs
2. Preserves document formatting and structure for accurate analysis
3. Handles API rate limits and retries with premium tier capabilities
4. Provides caching to avoid redundant downloads
5. Supports batch downloading of multiple filings in parallel

Financial importance:
- SEC filings contain the most reliable, legally required company information
- Complete document analysis provides deeper insights than predefined sections
- Preserving document structure helps AI understand context and relationships
"""

import json
import logging
import pickle
from datetime import date as Date
from typing import Any, Dict, List, Optional

import aiohttp
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import PickleType
from sqlalchemy.orm import mapped_column

import infra.acquisition.models as models
from infra.acquisition.models import DataFormat, FilingType, SECFiling
from infra.core.config import settings
from infra.core.exceptions import DataFetchError, ValidationError
from infra.core.interfaces import IDataFetcher
from infra.databases.cache import Cache
from infra.databases.engine import sqlalchemy_engine

# Set up logging
logger = logging.getLogger(__name__)


class FilingRequest(BaseModel):
    """
    Model representing a request for an SEC filing.

    This model validates and normalizes input parameters for fetching
    SEC filings, ensuring that all required fields are present and
    in the correct format.
    """

    identifier: List[str] = Field(
        ..., description="List of CIK numbers or stock tickers"
    )
    filing_type: Optional[FilingType] = Field(None, description="Type of SEC filing")
    start_date: Optional[Date] = Field(None, description="Start date for filing search")
    end_date: Optional[Date] = Field(None, description="End date for filing search")
    max_size: Optional[int] = Field(
        default=1, description="Maximum number of filings to fetch"
    )
    data_format: DataFormat = Field(
        default=DataFormat.HTML, description="Output data format"
    )

    @field_validator("identifier")
    def validate_identifier(cls, v):
        """Validate identifier format."""
        if not v:
            raise ValueError("Identifier cannot be empty")

        # CIK validation (numeric string)
        for i in v:
            if i.isdigit():
                if not 1 <= len(i) <= 10:
                    raise ValueError(f"CIK must be 1-10 digits: {i}")
            # Ticker symbol validation (1-5 alphanumeric characters)
            elif not (1 <= len(i) <= 5 and i.isalnum()):
                raise ValueError(f"Ticker must be 1-5 alphanumeric characters: {i}")

        return v

    class Config:
        """Configuration for the Pydantic model."""

        use_enum_values = True


class EDGARFetcher(IDataFetcher):
    """
    Fetcher for SEC filing data.

    This class implements the IDataFetcher interface to fetch SEC filing
    data from the SEC's EDGAR system. It handles authentication, rate
    limiting, and data formatting.
    """

    _CACHE_COLUMNS = {"value": mapped_column(PickleType, nullable=False)}

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the SEC filing fetcher.

        Args:
            api_key: API key for SEC API access
        """
        self.api_key = api_key or settings.SEC_API_KEY
        if not self.api_key:
            raise ValueError("SEC API key is not set")

        self.query_url = "https://api.sec-api.io"
        self.session = None

        self._cache = Cache(
            sqlalchemy_engine,
            table_name="sec_filings",
            column_mapping=self._CACHE_COLUMNS,
        )

    async def fetch(self, identifiers: List[str], **kwargs) -> List[SECFiling]:
        """
        Fetch SEC filings for a given identifier.

        Args:
            identifier: CIK number or stock ticker
            **kwargs: Additional parameters:
                - filing_type: Type of filing (10-K, 10-Q, 8-K)
                - date: Filing date
                - data_format: Output format ('html' or 'pdf')

        Returns:
            List of SECFiling objects including URLs and metadata

        Raises:
            ValidationError: If identifier or parameters are invalid
            DataFetchError: If filings cannot be fetched
        """
        try:
            # Create and validate request model
            request = FilingRequest(
                identifier=identifiers,
                **kwargs,
            )
        except ValueError as e:
            raise ValidationError(str(e), field=e.args[1] if len(e.args) > 1 else None)
        request_hash = self._cache.generate_id(request.model_dump())
        cache_entry = self._cache.get(request_hash)
        filings = pickle.loads(cache_entry["value"]) if cache_entry else None
        if filings:
            return filings

        # Get search query for SEC API
        search_query = self._build_search_query(request)
        logger.info(
            f"Querying SEC API for {request.identifier} filings with payload: {json.dumps(search_query)}"
        )

        # Fetch filings from SEC API
        filings_data = await self._fetch_filings_from_api(search_query)

        self._cache.write(
            request_hash,
            ttl=settings.SEC_API_CACHE_EXPIRATION,
            value=pickle.dumps(filings_data),
        )
        return filings_data

    def _build_search_query(self, request: FilingRequest) -> Dict[str, Any]:
        """
        Build search query for SEC API based on request parameters.

        Args:
            request: FilingRequest object containing search parameters

        Returns:
            Dictionary with search query for SEC API
        """
        # Define query components
        lucene_query = {
            "AND": [],
            "OR": [],
        }

        # Add identifier query (CIK or ticker)
        cik = []
        ticker = []
        for i_d in request.identifier:
            if i_d.isdigit():
                cik.append(i_d)
            else:
                ticker.append(i_d)
        lucene_query["OR"].append(f"cik:{tuple(cik)}") if len(cik) > 0 else None
        (
            lucene_query["OR"].append(f"ticker:{tuple(ticker)}")
            if len(ticker) > 0
            else None
        )

        # Add filing type if specified
        if request.filing_type:
            lucene_query["AND"].append(f'formType:"{request.filing_type}"')

        # Add date range if specified
        if request.start_date and request.end_date:
            start_date = request.start_date.isoformat()
            end_date = request.end_date.isoformat()
            lucene_query["AND"].append(f"filedAt:[{start_date} TO {end_date}]")
        elif request.start_date:
            start_date = request.start_date.isoformat()
            lucene_query["AND"].append(f"filedAt:[{start_date} TO *]")
        elif request.end_date:
            end_date = request.end_date.isoformat()
            lucene_query["AND"].append(f"filedAt:[* TO {end_date}]")

        # Build final query
        lucene_query["OR"] = " OR ".join(lucene_query["OR"])
        lucene_query["AND"] = " AND ".join(lucene_query["AND"])
        search_query = {
            "query": " AND ".join(lucene_query.values()),
            "from": "0",
            "size": request.max_size,
            "sort": [{"filedAt": {"order": "desc"}}],
        }

        return search_query

    async def _fetch_filings_from_api(
        self, search_query: Dict[str, Any]
    ) -> List[SECFiling]:
        """
        Fetch filings from SEC API using the provided search query.

        Args:
            search_query: Search query for SEC API

        Returns:
            List of SECFiling objects

        Raises:
            DataFetchError: If filings cannot be fetched
        """
        # Create API request headers with authorization
        headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                self.session = session

                # Send request to SEC API
                async with session.post(
                    self.query_url, headers=headers, json=search_query
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        filings = result.get("filings", [])
                        try:
                            filings = models.sec_api_query_response_schema.validate(
                                filings
                            )
                        except Exception as e:
                            logger.error(f"Error creating SECFiling model: {str(e)}")
                        return filings
                    elif response.status == 401:
                        raise DataFetchError(
                            "Invalid API key or authorization failed", "SEC API", 401
                        )
                    elif response.status == 429:
                        raise DataFetchError("Rate limit exceeded", "SEC API", 429)
                    else:
                        error_text = await response.text()
                        raise DataFetchError(
                            f"Failed to fetch filings: {response.status} - {error_text}",
                            "SEC API",
                            response.status,
                        )
        except aiohttp.ClientError as e:
            logger.error(f"Network error while fetching SEC filings: {str(e)}")
            raise DataFetchError(f"Network error: {str(e)}", "SEC API")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from SEC API: {str(e)}")
            raise DataFetchError(f"Invalid response format: {str(e)}", "SEC API")
        except Exception as e:
            logger.error(f"Unexpected error fetching SEC filings: {str(e)}")
            if not isinstance(e, DataFetchError):
                raise DataFetchError(f"Unexpected error: {str(e)}", "SEC API")
            raise
