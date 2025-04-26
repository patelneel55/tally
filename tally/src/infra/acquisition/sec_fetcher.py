"""
SEC Filing Fetcher
-----------------

This module provides functionality to retrieve complete SEC filings as HTML/PDF.
It leverages the SEC-API's Filing Download & PDF Generator API to fetch full documents.

Financial importance:
- SEC filings contain the most reliable, legally required company information
- Complete document analysis provides deeper insights than predefined sections
- Preserving document structure helps AI understand context and relationships
"""

import json
import logging
import pickle
from datetime import date as Date
from datetime import datetime
from enum import Enum
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import aiohttp
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator
from schema import And
from schema import Or
from schema import Schema
from schema import Use
from sqlalchemy import PickleType
from sqlalchemy.orm import mapped_column

from infra.acquisition.exceptions import DataFetchError
from infra.acquisition.exceptions import ValidationError
from infra.acquisition.models import AcquisitionOutput
from infra.acquisition.models import BaseMetadata
from infra.acquisition.models import DataFormat
from infra.acquisition.models import IDataFetcher
from infra.collections.models import ChunkType
from infra.config.settings import get_settings
from infra.databases.cache import Cache
from infra.databases.engine import get_sqlalchemy_engine


# Set up logging
logger = logging.getLogger(__name__)


class FilingType(str, Enum):
    """SEC filing types enumeration."""

    ANNUAL_REPORT = "10-K"
    QUARTERLY_REPORT = "10-Q"
    CURRENT_REPORT = "8-K"
    PROXY_STATEMENT = "DEF 14A"
    REGISTRATION_STATEMENT = "S-1"


class FilingRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

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
    def validate_identifier(cls, v: List[str]):
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


class SECFiling(BaseMetadata, AcquisitionOutput):
    """
    Represents an SEC filing document with associated metadata.

    This model is used to structure the data returned from the SEC API
    and provide a consistent interface for working with filing documents.
    """

    model_config = ConfigDict(populate_by_name=True)

    accessionNo: str = Field(..., description="SEC filing accession number")
    formType: str = Field(..., description="Type of SEC filing (e.g. 10-K, 10-Q)")
    filing_date: datetime = Field(
        ..., description="Date the filing was submitted", alias="filedAt"
    )
    company_name: str = Field(..., description="Name of the filing company")
    ticker: str = Field(..., description="Stock ticker symbol")
    cik: str = Field(..., description="SEC Central Index Key (CIK)")
    documentURL: Optional[str] = Field("", description="URL to the filing document")

    @field_validator("filing_date", mode="before")
    def parse_datetime(cls, value):
        """Convert ISO format string to datetime object."""
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value

    def get_uris(self) -> List[str]:
        """Return a list of URIs for the filing."""
        uris = []
        if self.documentURL:
            uri = self._convert_to_sec_gov_url(self.documentURL)
            uris.append(uri)
        return uris

    def get_metadata(self) -> Dict[str, Any]:
        """Return metadata for the filing."""
        return self.model_dump()

    def _convert_to_sec_gov_url(self, url: str) -> Optional[str]:
        """
        Convert an API URL to a SEC.gov URL format.

        The PDF Generator API requires URLs in the SEC.gov format.

        Args:
            url: The URL to convert

        Returns:
            SEC.gov formatted URL if conversion is successful, None otherwise
        """
        # If it's already a SEC.gov URL, return it as is
        if url.startswith("https://www.sec.gov/"):
            # Remove inline XBRL parameters if present
            return url.replace("/ix?doc=", "")

        # If it's a URL from the SEC API
        if "sec-api.io" in url:
            # Extract the path after /Archives/
            parts = url.split("/Archives/")
            if len(parts) > 1:
                return f"https://www.sec.gov/Archives/{parts[1]}"
        return url


sec_api_query_response_schema = Schema(
    [
        And(
            {
                "accessionNo": And(str, len),
                "formType": And(str, len),
                "cik": And(str, len),
                "companyName": And(str, len),
                "filedAt": And(str, len),
                "ticker": And(str, len),
                "documentFormatFiles": Or(
                    [
                        {
                            "type": And(str, len),
                            "documentUrl": And(str, len),
                        }
                    ],
                    None,
                    ignore_extra_keys=True,
                ),
            },
            Use(
                lambda x: SECFiling(
                    accessionNo=x["accessionNo"],
                    formType=x["formType"],
                    filing_date=x["filedAt"],
                    company_name=x["companyName"],
                    ticker=x["ticker"],
                    cik=x["cik"],
                    documentURL=next(
                        (
                            d["documentUrl"]
                            for d in (x["documentFormatFiles"] or [])
                            if d["type"] == x["formType"]
                        ),
                        "",
                    ),
                    chunk_type=ChunkType.TEXT,
                ),
            ),
            ignore_extra_keys=True,
        )
    ],
    ignore_extra_keys=True,
)


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
        self.api_key = api_key or get_settings().SEC_API_KEY
        if not self.api_key:
            raise ValueError("SEC API key is not set")

        self.query_url = "https://api.sec-api.io"
        self.session = None

        self._cache = Cache(
            get_sqlalchemy_engine(),
            table_name="sec_filings",
            column_mapping=self._CACHE_COLUMNS,
        )

    async def fetch(self, **kwargs) -> List[SECFiling]:
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
            request = FilingRequest(**kwargs)
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
            ttl=get_settings().SEC_API_CACHE_EXPIRATION,
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
        clauses = []

        # Add identifier query (CIK or ticker)
        ciks = [i.lstrip("0") for i in request.identifier if i.isdigit()]
        tickers = [i.upper() for i in request.identifier if not i.isdigit()]

        if ciks and tickers:
            cik_query = f"cik:({', '.join(ciks)})"
            ticker_query = f"ticker:({', '.join(tickers)})"
            clauses.append(f"({cik_query} OR {ticker_query})")
        elif ciks:
            cik_query = f"cik:({', '.join(ciks)})"
            clauses.append(cik_query)
        elif tickers:
            ticker_query = f"ticker:({', '.join(tickers)})"
            clauses.append(ticker_query)

        # Add filing type if specified
        if request.filing_type:
            clauses.append(f'formType:"{request.filing_type}"')

        # Add date range if specified
        if request.start_date or request.end_date:
            start = request.start_date.isoformat() if request.start_date else "*"
            end = request.end_date.isoformat() if request.end_date else "*"
            clauses.append(f"filedAt:[{start} TO {end}]")

        # Build final query
        search_query = {
            "query": " AND ".join(clauses),
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
                            filings = sec_api_query_response_schema.validate(filings)
                        except Exception as e:
                            logger.error(f"Error validating SECFiling model: {str(e)}")
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
