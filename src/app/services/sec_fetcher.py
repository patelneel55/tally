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

How it fits in the architecture:
- Provides the data acquisition layer for SEC filing analysis
- Works alongside the existing SEC API integration
- Feeds documents into the AI analysis pipeline

Financial importance:
- SEC filings contain the most reliable, legally required company information
- Complete document analysis provides deeper insights than predefined sections
- Preserving document structure helps AI understand context and relationships
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from datetime import date, datetime
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import BinaryIO, Dict, List, Optional, Tuple, Union

import aiohttp
from pydantic import BaseModel, Field

from app.core.config import settings
from app.models.financial_statements import FilingType


# Set up logging
logger = logging.getLogger(__name__)


# SEC Filing Model
class SECFiling(BaseModel):
    """SEC Filing information."""

    id: str = None
    symbol: str
    company_name: str
    filing_type: str
    filing_date: datetime
    document_url: str
    description: Optional[str] = None
    form_id: Optional[str] = None
    filing_period: Optional[str] = None
    report_date: Optional[date] = None
    fiscal_year: Optional[int] = None
    fiscal_quarter: Optional[int] = None

    model_config = {"extra": "allow"}


# API endpoints
SEC_ARCHIVE_API_ENDPOINT = "https://archive.sec-api.io"
SEC_PDF_GENERATOR_API_ENDPOINT = "https://api.sec-api.io/filing-reader"
SEC_QUERY_API_ENDPOINT = (
    "https://api.sec-api.io"  # Base endpoint for all SEC API requests
)
SEC_FILING_DOWNLOAD_API_ENDPOINT = "https://api.sec-api.io/filing-download"

# Filing types of interest for full document analysis
FILING_TYPES_FOR_ANALYSIS = [
    FilingType.FORM_10K,
    FilingType.FORM_10Q,
    FilingType.FORM_8K,
]

# Rate limiting semaphore - Premium tier allows more concurrent requests
# but we'll still implement a semaphore to avoid overwhelming the API
PREMIUM_RATE_LIMIT = 20  # Concurrent requests for premium tier (Query API limit)
PREMIUM_SEARCH_RATE_LIMIT = 10  # Requests per second for Full-Text Search API
PREMIUM_FILING_DOWNLOAD_LIMIT = (
    7000 / 300
)  # Filings per second (7000 per 5 minutes = ~23.3 per second)

# Historical filing configuration
HISTORICAL_10Q_COUNT = 4  # Number of recent 10-Q filings to fetch
HISTORICAL_10K_COUNT = 1  # Number of recent 10-K filings to fetch


class SECFilingFetcher:
    """
    Service for retrieving complete SEC filings as PDFs.

    This class handles the downloading of full SEC filings in PDF format
    for AI-powered analysis. It manages API rate limits, retries, and
    caching to ensure efficient and reliable access to filing documents.
    """

    def __init__(self):
        """
        Initialize the SEC filing fetcher with API credentials.

        Sets up the necessary API keys and creates cache directories
        for storing downloaded filings to avoid redundant API calls.
        """
        self.api_key = settings.SEC_API_KEY

        if not self.api_key:
            logger.warning("SEC API key not found, PDF filing retrieval will not work")
        else:
            logger.info("SEC Filing Fetcher initialized with premium API access")

        # Create cache directory for storing downloaded filings
        self.cache_dir = Path("cache/sec_filings")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Create directory for storing filing URLs
        self.urls_dir = Path("cache/sec_filing_urls")
        self.urls_dir.mkdir(parents=True, exist_ok=True)

        # Create directory for storing filing metadata
        self.metadata_dir = Path("cache/sec_filing_metadata")
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

        # Rate limiting semaphores for different API endpoints
        self.query_semaphore = asyncio.Semaphore(PREMIUM_RATE_LIMIT)
        self.search_semaphore = asyncio.Semaphore(PREMIUM_SEARCH_RATE_LIMIT)
        self.download_semaphore = asyncio.Semaphore(int(PREMIUM_FILING_DOWNLOAD_LIMIT))

        # Last request timestamps for rate limiting
        self.last_query_time = 0
        self.last_search_time = 0
        self.last_download_time = 0

        # Minimum time between requests (in seconds)
        self.min_query_interval = (
            1.0 / PREMIUM_RATE_LIMIT
        )  # e.g., 1/20 = 0.05s between requests
        self.min_search_interval = (
            1.0 / PREMIUM_SEARCH_RATE_LIMIT
        )  # e.g., 1/10 = 0.1s between requests
        self.min_download_interval = (
            1.0 / PREMIUM_FILING_DOWNLOAD_LIMIT
        )  # Time between download requests

    async def get_filing_pdf(self, filing: SECFiling) -> Optional[Path]:
        """
        Retrieve a SEC filing as a PDF.

        This function fetches a complete SEC filing document as a PDF file,
        either from the cache (if available) or by downloading it from the
        SEC API. The PDF preserves the original document structure and
        formatting for accurate AI analysis.

        Args:
            filing: SECFiling object containing metadata about the filing

        Returns:
            Path to the downloaded PDF file, or None if retrieval failed

        Raises:
            ValueError: If the filing URL is invalid or the API key is missing
        """
        if not self.api_key:
            raise ValueError("SEC API key is required for PDF filing retrieval")

        if not filing.document_url:
            raise ValueError("Filing document URL is missing")

        # Check if we already have this filing cached
        cache_path = self._get_cache_path(filing)
        if cache_path.exists() and settings.ENABLE_CACHE:
            logger.info(
                f"Using cached PDF for {filing.symbol} {filing.filing_type} from {filing.filing_date}"
            )
            return cache_path

        # Convert SEC.gov URL to a format suitable for the PDF Generator API
        sec_url = self._convert_to_sec_gov_url(filing.document_url)
        if not sec_url:
            raise ValueError(f"Invalid document URL format: {filing.document_url}")

        logger.info(
            f"Downloading {filing.filing_type} filing for {filing.symbol} from {filing.filing_date} as PDF"
        )

        try:
            # Use the appropriate semaphore for PDF generation (uses the query API)
            async with self.query_semaphore:
                # Apply rate limiting
                current_time = time.time()
                time_since_last_request = current_time - self.last_query_time
                if time_since_last_request < self.min_query_interval:
                    await asyncio.sleep(
                        self.min_query_interval - time_since_last_request
                    )

                self.last_query_time = time.time()

                # Download the filing as PDF
                pdf_data = await self._download_filing_as_pdf(sec_url)

                if pdf_data:
                    # Save to cache
                    with open(cache_path, "wb") as f:
                        f.write(pdf_data)

                    # Save metadata for future reference
                    self._save_filing_metadata(filing, cache_path)

                    logger.info(
                        f"Successfully downloaded and cached PDF for {filing.symbol} {filing.filing_type}"
                    )
                    return cache_path
                else:
                    logger.error(
                        f"Failed to download PDF for {filing.symbol} {filing.filing_type}"
                    )
                    return None

        except Exception as e:
            logger.error(
                f"Error downloading PDF for {filing.symbol} {filing.filing_type}: {e}"
            )
            return None

    async def _download_filing_as_pdf(self, sec_url: str) -> Optional[bytes]:
        """
        Download a SEC filing as a PDF using the PDF Generator API.

        This function handles the actual API call to convert and download
        a SEC filing as a PDF document. It includes retry logic for handling
        rate limits and temporary failures.

        Args:
            sec_url: The SEC.gov URL of the filing to download

        Returns:
            Binary PDF data if successful, None otherwise
        """
        params = {
            "token": self.api_key,
            "url": sec_url,
            "quality": "high",  # Premium tier supports high quality PDFs
        }

        # Implement retry logic with exponential backoff
        max_retries = settings.SEC_FILING_MAX_RETRIES
        retry_delay = settings.SEC_FILING_RETRY_DELAY

        # No need for additional rate limiting here as it's already handled in the calling method

        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        SEC_PDF_GENERATOR_API_ENDPOINT,
                        params=params,
                        timeout=60,  # Longer timeout for PDF generation
                    ) as response:
                        if response.status == 200:
                            return await response.read()
                        elif (
                            response.status == 202
                        ):  # Cache miss, PDF generation started
                            response_json = await response.json()
                            retry_seconds = 5  # Default retry time

                            # Extract retry time from response if available
                            if "message" in response_json:
                                message = response_json["message"]
                                logger.info(f"PDF generation in progress: {message}")

                                # Extract retry time from message if available
                                retry_match = re.search(
                                    r"Retry in (\d+) seconds", message
                                )
                                if retry_match:
                                    retry_seconds = int(retry_match.group(1))

                            # Wait for the specified time before retrying
                            logger.info(
                                f"Waiting {retry_seconds} seconds for PDF generation to complete"
                            )
                            await asyncio.sleep(retry_seconds)

                            # Don't increment the attempt counter for cache miss
                            # This is not a failure, just a delay
                            continue
                        elif response.status == 429:  # Too Many Requests
                            logger.warning(
                                f"Rate limit hit, retrying in {retry_delay} seconds"
                            )
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                        else:
                            error_text = await response.text()
                            logger.error(f"API error: {response.status}, {error_text}")
                            return None
            except asyncio.TimeoutError:
                logger.warning(
                    f"Request timed out, retrying ({attempt+1}/{max_retries})"
                )
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
            except Exception as e:
                logger.error(f"Error during PDF download: {e}")
                return None

        logger.error(f"Failed to download PDF after {max_retries} attempts")
        return None

    def _convert_to_sec_gov_url(self, url: str) -> Optional[str]:
        """
        Convert an API URL to a SEC.gov URL format.

        The PDF Generator API requires URLs in the SEC.gov format.
        This function handles the conversion from our internal URL format.

        Args:
            url: The URL to convert

        Returns:
            SEC.gov formatted URL if conversion is successful, None otherwise
        """
        # If it's already a SEC.gov URL, return it as is
        if url.startswith("https://www.sec.gov/"):
            # Remove inline XBRL parameters if present
            return url.replace("/ix?doc=", "")

        # If it's a linkToFilingDetails URL from the SEC API
        if "sec-api.io" in url:
            # Extract the path after /Archives/
            parts = url.split("/Archives/")
            if len(parts) > 1:
                return f"https://www.sec.gov/Archives/{parts[1]}"

        # If we can't convert it, return None
        logger.warning(f"Could not convert URL to SEC.gov format: {url}")
        return None

    def _get_cache_path(self, filing: SECFiling) -> Path:
        """
        Generate a cache file path for a filing.

        Creates a unique filename based on the filing's metadata to
        ensure proper caching and retrieval.

        Args:
            filing: SECFiling object containing metadata about the filing

        Returns:
            Path object for the cache file location
        """
        # Create a unique filename based on filing metadata
        filing_date_str = filing.filing_date.strftime("%Y-%m-%d")
        filename = f"{filing.symbol}_{filing.filing_type}_{filing_date_str}.pdf"

        # Create a subdirectory for the symbol to organize cache
        symbol_dir = self.cache_dir / filing.symbol
        symbol_dir.mkdir(exist_ok=True)

        return symbol_dir / filename

    def _save_filing_metadata(self, filing: SECFiling, pdf_path: Path) -> None:
        """
        Save filing metadata for future reference.

        Stores information about the filing and its cached location
        to enable faster lookups and better cache management.

        Args:
            filing: SECFiling object containing metadata about the filing
            pdf_path: Path to the cached PDF file
        """
        metadata = {
            "symbol": filing.symbol,
            "filing_type": filing.filing_type,
            "filing_date": filing.filing_date.isoformat(),
            "document_url": filing.document_url,
            "filing_id": filing.id,
            "pdf_path": str(pdf_path),
            "cached_at": datetime.now().isoformat(),
        }

        # Create a unique filename for the metadata
        metadata_filename = f"{filing.symbol}_{filing.filing_type}_{filing.filing_date.isoformat()}.json"
        metadata_path = self.metadata_dir / metadata_filename

        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

    async def batch_download_filings(
        self, filings: List[SECFiling]
    ) -> Dict[str, Optional[Path]]:
        """
        Download multiple filings in parallel.

        This function optimizes the downloading of multiple filings by
        processing them concurrently, respecting rate limits while
        maximizing throughput. With premium API access, we can download
        up to 7,000 filings per 5 minutes.

        Args:
            filings: List of SECFiling objects to download

        Returns:
            Dictionary mapping filing IDs to their downloaded PDF paths
        """
        logger.info(f"Batch downloading {len(filings)} filings")

        # Create a semaphore to limit concurrent downloads based on the premium tier limit
        # We'll use a more conservative limit than the maximum to ensure reliability
        batch_semaphore = asyncio.Semaphore(min(20, int(PREMIUM_FILING_DOWNLOAD_LIMIT)))

        async def download_with_rate_limit(
            filing: SECFiling,
        ) -> Tuple[str, Optional[Path]]:
            """Download a single filing with rate limiting."""
            async with batch_semaphore:
                # Apply rate limiting
                current_time = time.time()
                time_since_last_request = current_time - self.last_download_time
                if time_since_last_request < self.min_download_interval:
                    await asyncio.sleep(
                        self.min_download_interval - time_since_last_request
                    )

                self.last_download_time = time.time()

                # Download the filing
                try:
                    pdf_path = await self.get_filing_pdf(filing)
                    return filing.id, pdf_path
                except Exception as e:
                    logger.error(
                        f"Error downloading {filing.symbol} {filing.filing_type}: {e}"
                    )
                    return filing.id, None

        # Create tasks for each filing with rate limiting
        tasks = [download_with_rate_limit(filing) for filing in filings]

        # Execute tasks concurrently
        results = await asyncio.gather(*tasks)

        # Convert results to dictionary
        return dict(results)

    async def get_filing_by_accession_number(
        self, accession_number: str, symbol: str
    ) -> Optional[Path]:
        """
        Retrieve a filing by its SEC accession number.

        This function is useful when you have the accession number but not
        the full filing URL. It constructs the appropriate URL and downloads
        the filing.

        Args:
            accession_number: SEC accession number (e.g., "0000320193-23-000106")
            symbol: Company ticker symbol

        Returns:
            Path to the downloaded PDF file, or None if retrieval failed
        """
        # Format the accession number for URL construction
        formatted_accn = accession_number.replace("-", "")

        # Construct the SEC.gov URL
        sec_url = f"https://www.sec.gov/Archives/edgar/data/{self._get_cik_from_symbol(symbol)}/{formatted_accn}/{accession_number}.txt"

        # Create a temporary filing object for caching
        filing = SECFiling(
            symbol=symbol,
            filing_type=FilingType.OTHER,  # We don't know the type yet
            filing_date=date.today(),  # We don't know the date yet
            document_url=sec_url,
            filing_id=accession_number,
        )

        # Download the filing
        return await self.get_filing_pdf(filing)

    def _get_cik_from_symbol(self, symbol: str) -> str:
        """
        Get the CIK (Central Index Key) for a company symbol.

        This is a placeholder implementation. In a real-world scenario,
        you would either have a mapping of symbols to CIKs or use an API
        to look up the CIK.

        Args:
            symbol: Company ticker symbol

        Returns:
            CIK as a string
        """
        # This is a simplified implementation
        # In a real-world scenario, you would use a more robust approach
        # such as querying an API or using a pre-populated database

        # Common CIKs for testing
        cik_map = {
            "AAPL": "320193",
            "MSFT": "789019",
            "GOOGL": "1652044",
            "AMZN": "1018724",
            "META": "1326801",
        }

        return cik_map.get(symbol, "000000000")  # Default CIK if not found

    def clear_cache(self, older_than_days: Optional[int] = None) -> int:
        """
        Clear the filing cache.

        Removes cached filings to free up disk space. Can optionally
        remove only files older than a specified number of days.

        Args:
            older_than_days: Only remove files older than this many days

        Returns:
            Number of files removed
        """
        count = 0

        if older_than_days is not None:
            cutoff_time = time.time() - (older_than_days * 86400)

            for path in self.cache_dir.glob("**/*.pdf"):
                if path.stat().st_mtime < cutoff_time:
                    path.unlink()
                    count += 1
        else:
            # Remove all files
            for path in self.cache_dir.glob("**/*.pdf"):
                path.unlink()
                count += 1

        logger.info(f"Cleared {count} files from the SEC filing cache")
        return count

    async def get_historical_filings(self, symbol: str) -> Dict[str, List[SECFiling]]:
        """
        Retrieve historical SEC filings for a company.

        This function fetches the most recent 10-K filing and the last four 10-Q filings
        for a given company symbol. It uses the SEC Query API to find the filings and
        then downloads them in parallel using the batch download functionality.

        Args:
            symbol: Company ticker symbol

        Returns:
            Dictionary mapping filing types to lists of SECFiling objects

        Example:
            {
                "10-K": [SECFiling(...)],
                "10-Q": [SECFiling(...), SECFiling(...), SECFiling(...), SECFiling(...)]
            }
        """
        logger.info(f"Fetching historical filings for {symbol}")

        # Initialize result dictionary
        historical_filings = {"10-K": [], "10-Q": []}

        try:
            # Step 1: Query the SEC API to find the most recent filings
            form_10k_filings = await self._query_sec_filings(
                symbol=symbol, form_type="10-K", limit=HISTORICAL_10K_COUNT
            )

            form_10q_filings = await self._query_sec_filings(
                symbol=symbol, form_type="10-Q", limit=HISTORICAL_10Q_COUNT
            )

            # Step 2: Convert API results to SECFiling objects
            for filing_data in form_10k_filings:
                filing = self._convert_api_result_to_filing(
                    filing_data, symbol, FilingType.FORM_10K
                )
                if filing:
                    historical_filings["10-K"].append(filing)

            for filing_data in form_10q_filings:
                filing = self._convert_api_result_to_filing(
                    filing_data, symbol, FilingType.FORM_10Q
                )
                if filing:
                    historical_filings["10-Q"].append(filing)

            # Step 3: Download all filings in parallel
            all_filings = historical_filings["10-K"] + historical_filings["10-Q"]
            if all_filings:
                logger.info(
                    f"Downloading {len(all_filings)} historical filings for {symbol}"
                )
                await self.batch_download_filings(all_filings)

            return historical_filings

        except Exception as e:
            logger.error(f"Error fetching historical filings for {symbol}: {e}")
            return historical_filings

    async def _query_sec_filings(
        self, symbol: str, form_type: str = None, limit: int = 5
    ) -> List[Dict]:
        """
        Query the SEC API for filings of a specific type.

        This function uses the SEC Query API to find filings of a specific type
        for a given company symbol, sorted by filing date (most recent first).

        Args:
            symbol: Company ticker symbol
            form_type: Filing type (e.g., "10-K", "10-Q"). If None, fetch all types.
            limit: Maximum number of filings to return

        Returns:
            List of filing data dictionaries from the SEC API
        """
        if not self.api_key:
            raise ValueError("SEC API key is required for querying filings")

        # Apply rate limiting
        async with self.query_semaphore:
            current_time = time.time()
            time_since_last_request = current_time - self.last_query_time
            if time_since_last_request < self.min_query_interval:
                await asyncio.sleep(self.min_query_interval - time_since_last_request)

            self.last_query_time = time.time()

            try:
                # Construct the query payload according to the SEC API documentation
                # Use the exact query format as specified in the documentation
                if form_type:
                    query_string = f'formType:"{form_type}" AND ticker:{symbol}'
                else:
                    query_string = f"ticker:{symbol}"

                query_payload = {
                    "query": query_string,
                    "from": "0",  # Must be a string per the API docs
                    "size": str(limit),  # Must be a string per the API docs
                    "sort": [{"filedAt": {"order": "desc"}}],
                }

                # Log detailed information
                logger.info(
                    f"SEC API KEY (first 4 chars): {self.api_key[:4] if self.api_key else 'None'}"
                )
                logger.info(f"API Endpoint: {SEC_QUERY_API_ENDPOINT}")
                logger.info(
                    f"Querying SEC API for {symbol} filings with payload: {json.dumps(query_payload)}"
                )

                headers = {
                    "Authorization": self.api_key,
                    "Content-Type": "application/json",
                }

                logger.info(f"Request headers: {headers}")

                async with aiohttp.ClientSession() as session:
                    logger.info(f"Making API request to SEC API...")
                    async with session.post(
                        f"{SEC_QUERY_API_ENDPOINT}",  # Add the /query path to the base endpoint
                        headers=headers,
                        json=query_payload,
                    ) as response:
                        response_text = await response.text()
                        logger.info(f"SEC API response status: {response.status}")
                        logger.info(f"SEC API response headers: {response.headers}")
                        # logger.info(f"SEC API response (full): {response_text}")

                        if response.status == 200:
                            data = json.loads(response_text)
                            # The API returns a structure with "filings" array containing the actual filing data
                            filings = data.get("filings", [])
                            logger.info(f"SEC API found {len(filings)} filings")
                            return filings
                        else:
                            logger.error(
                                f"SEC API error: {response.status}, {response_text}"
                            )
                            # Return an empty list instead of raising an exception
                            return []
            except Exception as e:
                logger.error(f"Error querying SEC filings: {str(e)}")
                import traceback

                logger.error(f"Traceback: {traceback.format_exc()}")
                # Return an empty list instead of raising an exception
                return []

    def _convert_api_result_to_filing(
        self, filing_data: Dict, symbol: str, filing_type: FilingType
    ) -> Optional[SECFiling]:
        """
        Convert SEC API result to a SECFiling object.

        This function extracts the relevant information from the SEC API response
        and creates a SECFiling object that can be used for downloading and analysis.

        Args:
            filing_data: Filing data dictionary from the SEC API
            symbol: Company ticker symbol
            filing_type: Filing type enum value

        Returns:
            SECFiling object if conversion is successful, None otherwise
        """
        try:
            # Extract filing date
            filing_date_str = filing_data.get("filedAt", "")
            if not filing_date_str:
                return None

            filing_date = datetime.fromisoformat(
                filing_date_str.replace("Z", "+00:00")
            ).date()

            # Retrieve documentUrl from documentFormatFiles if available and matches filing_type
            doc_format_files = filing_data.get("documentFormatFiles")
            document = None
            if doc_format_files and isinstance(doc_format_files, list):
                for doc in doc_format_files:
                    if doc.get("type") == filing_type:
                        document_url = doc.get("documentUrl")
                        break
            if not document_url:
                return None

            # Extract filing ID (accession number)
            filing_id = filing_data.get("accessionNo", "")
            if not filing_id:
                return None

            return SECFiling(
                symbol=symbol,
                company_name=filing_data.get("companyName"),
                filing_type=filing_type,
                filing_date=filing_date,
                document_url=document_url,
                id=filing_id,
            )
        except Exception as e:
            logger.error(f"Error converting API result to filing: {e}")
            return None


# Create a singleton instance of the fetcher
sec_filing_fetcher = SECFilingFetcher()

# Also create an alias with the new name for compatibility with updated code
sec_fetcher = sec_filing_fetcher

# For testing purposes, create a mock instance
# This will be used by tests to avoid hitting the real SEC API
mock_sec_filing_fetcher = SECFilingFetcher()


# For testing purposes, create a mock version that returns test data
class MockSECFilingFetcher:
    """Mock implementation of SECFilingFetcher for testing purposes."""

    def __init__(self):
        """Initialize the mock fetcher."""
        self.logger = logging.getLogger(__name__)
        self.cache_dir = Path("cache/sec_filings")
        os.makedirs(self.cache_dir, exist_ok=True)

    def get_filing(
        self,
        ticker: str,
        filing_type: FilingType,
        fiscal_year: int,
        fiscal_period: str = None,
    ):
        """
        Return a mock filing for testing purposes.

        Args:
            ticker: Company ticker symbol
            filing_type: Type of filing (10-K, 10-Q, 8-K)
            fiscal_year: Fiscal year of the filing
            fiscal_period: Fiscal period (Q1, Q2, etc.) - only for 10-Q

        Returns:
            A mock SECFiling object
        """
        self.logger.info(
            f"Mock fetcher returning filing for {ticker} {filing_type} {fiscal_year} {fiscal_period}"
        )

        # Create a mock filing object
        filing_date = (
            datetime(fiscal_year, 12, 31)
            if filing_type == FilingType.FORM_10K
            else datetime(fiscal_year, 3, 31)
        )

        mock_filing = SECFiling(
            id=f"mock-{ticker}-{filing_type}-{fiscal_year}-{fiscal_period or ''}",
            ticker=ticker,
            company_name=f"{ticker} Inc.",
            filing_type=filing_type,
            filing_date=filing_date,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period or "FY",
            form_url=f"https://www.sec.gov/mock/{ticker}/{filing_type}/{fiscal_year}/{fiscal_period or ''}",
            document_url=f"https://www.sec.gov/mock/{ticker}/{filing_type}/{fiscal_year}/{fiscal_period or ''}/document",
            filing_html="<html><body><h1>Mock Filing</h1><p>This is a mock filing for testing purposes.</p></body></html>",
            accession_no=f"0000000-{fiscal_year}-123456",
            file_number="123-45678",
            cik="0000123456",
            period_end_date=filing_date,
        )

        return mock_filing
