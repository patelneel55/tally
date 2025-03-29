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
import logging
import os
from typing import Any, Dict, List, Optional, Union
from datetime import date as Date
from enum import Enum
from infra.core.interfaces import IDataFetcher
from infra.core.exceptions import ValidationError, DataFetchError
from pydantic import BaseModel, Field, field_validator
import aiohttp
import json
from datetime import datetime
from pathlib import Path
import asyncio


# Set up logging
logger = logging.getLogger(__name__)


class FilingType(str, Enum):
    """SEC filing types enumeration."""
    ANNUAL_REPORT = "10-K"
    QUARTERLY_REPORT = "10-Q"
    CURRENT_REPORT = "8-K"
    PROXY_STATEMENT = "DEF 14A"
    REGISTRATION_STATEMENT = "S-1"


class DataFormat(str, Enum):
    """Data format options for SEC filings."""
    HTML = "html"
    PDF = "pdf"


class SECFiling(BaseModel):
    """
    Represents an SEC filing document with associated metadata.
    
    This model is used to structure the data returned from the SEC API
    and provide a consistent interface for working with filing documents.
    """
    accessionNo: str = Field(..., description="SEC filing accession number")
    formType: str = Field(..., description="Type of SEC filing (e.g. 10-K, 10-Q)")
    filing_date: datetime = Field(..., description="Date the filing was submitted", alias="filedAt")
    company_name: str = Field(..., description="Name of the filing company")
    ticker: str = Field(..., description="Stock ticker symbol")
    cik: str = Field(..., description="SEC Central Index Key (CIK)")
    documentURL: Optional[str] = Field(None, description="URL to the filing document")
    textURL: Optional[str] = Field(None, description="URL to the plain text version", alias="linkToTxt")
    pdf_path: Optional[str] = Field(None, description="Local path to cached PDF file")
    html_path: Optional[str] = Field(None, description="Local path to cached HTML file")
    
    class Config:
        populate_by_name = True
        
    @field_validator('filing_date', mode='before')
    def parse_datetime(cls, value):
        """Convert ISO format string to datetime object."""
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        return value


class FilingRequest(BaseModel):
    """
    Model representing a request for an SEC filing.
    
    This model validates and normalizes input parameters for fetching
    SEC filings, ensuring that all required fields are present and
    in the correct format.
    """
    identifier: str = Field(..., description="CIK number or stock ticker")
    filing_type: Optional[FilingType] = Field(None, description="Type of SEC filing")
    date: Optional[Date] = Field(None, description="Filing date")
    data_format: DataFormat = Field(default=DataFormat.PDF, description="Output data format")
    
    @field_validator('identifier')
    def validate_identifier(cls, v):
        """Validate identifier format."""
        if not v:
            raise ValueError("Identifier cannot be empty")
        
        # CIK validation (numeric string)
        if v.isdigit():
            if not 1 <= len(v) <= 10:
                raise ValueError("CIK must be 1-10 digits")
        # Ticker symbol validation (1-5 alphanumeric characters)
        elif not (1 <= len(v) <= 5 and v.isalnum()):
            raise ValueError("Ticker must be 1-5 alphanumeric characters")
        
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

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the SEC filing fetcher.
        
        Args:
            api_key: API key for SEC API access
        """
        self.api_key = api_key or os.getenv("SEC_API_KEY")
        if not self.api_key:
            raise ValueError("SEC API key is not set")

        self.base_url = "https://archive.sec-api.io"
        self.pdf_generator_url = "https://api.sec-api.io/filing-reader"
        self.query_url = "https://api.sec-api.io"
        self.download_url = "https://api.sec-api.io/filing-download"
        self.session = None

        # Create cache directory for storing downloaded filings
        self.cache_dir = Path("cache/sec_filings")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def fetch(self, identifier: str, **kwargs) -> List[SECFiling]:
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
                identifier=identifier,
                filing_type=kwargs.get('filing_type'),
                date=kwargs.get('date'),
                data_format=kwargs.get('data_format', DataFormat.PDF)
            )
        except ValueError as e:
            raise ValidationError(str(e), field=e.args[1] if len(e.args) > 1 else None)
            
        # Get search query for SEC API
        search_query = self._build_search_query(request)
        
        # Log detailed information
        logger.info(f"SEC API Query: {search_query}")
        logger.info(f"SEC API KEY (first 4 chars): {self.api_key[:4] if self.api_key else 'None'}")
        logger.info(f"API Endpoint: {self.query_url}")
        logger.info(f"Querying SEC API for {request.identifier} filings with payload: {json.dumps(search_query)}")
        
        # Fetch filings from SEC API
        filings_data = await self._fetch_filings_from_api(search_query)

        # Filter filings based on date if specified
        if request.date:
            processed_filings = self._filter_filings_by_date(processed_filings, request.date)
        
        # Process the filings based on requested data format
        if request.data_format == DataFormat.PDF:
            # Download PDFs for filings
            processed_filings = await self._process_pdf_filings(filings_data)
        else:
            # Get HTML content for filings
            processed_filings = await self._process_html_filings(filings_data)
            
        return processed_filings

    def _build_search_query(self, request: FilingRequest) -> Dict[str, Any]:
        """
        Build search query for SEC API based on request parameters.
        
        Args:
            request: FilingRequest object containing search parameters
            
        Returns:
            Dictionary with search query for SEC API
        """
        # Define query components
        query_parts = []
        
        # Add identifier query (CIK or ticker)
        identifier_field = "cik" if request.identifier.isdigit() else "ticker"
        query_parts.append(f"{identifier_field}:{request.identifier}")
        
        # Add filing type if specified
        if request.filing_type:
            query_parts.append(f'formType:"{request.filing_type}"')
        
        # Add date range if specified 
        if request.date:
            date_str = request.date.isoformat()
            query_parts.append(f'filedAt:[{date_str} TO {date_str}T23:59:59]')
            
        # Build final query
        search_query = {
            "query": " AND ".join(query_parts),
            "from": "0",
            "size": "10",
            "sort": [{"filedAt": {"order": "desc"}}]
        }
        
        return search_query
    
    async def _fetch_filings_from_api(self, search_query: Dict[str, Any]) -> List[SECFiling]:
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
                    self.query_url, 
                    headers=headers,
                    json=search_query
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        filings = result.get("filings", [])
                        return self._convert_api_results_to_filings(filings)
                    elif response.status == 401:
                        raise DataFetchError("Invalid API key or authorization failed", "SEC API", 401)
                    elif response.status == 429:
                        raise DataFetchError("Rate limit exceeded", "SEC API", 429)
                    else:
                        error_text = await response.text()
                        raise DataFetchError(
                            f"Failed to fetch filings: {response.status} - {error_text}",
                            "SEC API",
                            response.status
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
    
    def _convert_api_results_to_filings(self, filings_data: List[Dict[str, Any]]) -> List[SECFiling]:
        """
        Convert API results to SECFiling objects.
        
        Args:
            filings_data: List of filing data dictionaries from SEC API
            
        Returns:
            List of SECFiling objects
        """
        filings = []
        for filing in filings_data:
            # Extract document URL from documentFormatFiles if available
            doc_url = None
            if filing.get("documentFormatFiles"):
                for doc in filing.get("documentFormatFiles", []):
                    if doc.get("type") == filing.get("formType"):
                        doc_url = doc.get("documentUrl")
                        break
            
            # Create SECFiling model instance
            try:
                filing_data = SECFiling(
                    accessionNo=filing.get("accessionNo"),
                    formType=filing.get("formType"),
                    filedAt=filing.get("filedAt"),
                    company_name=filing.get("companyName"),
                    ticker=filing.get("ticker"),
                    cik=filing.get("cik"),
                    documentURL=doc_url,
                    linkToTxt=filing.get("linkToTxt")
                )
                filings.append(filing_data)
            except Exception as e:
                logger.error(f"Error creating SECFiling model: {str(e)}")
                continue
                
        return filings
    
    async def _process_pdf_filings(self, filings: List[SECFiling]) -> List[SECFiling]:
        """
        Process filings to download PDF versions.
        
        Args:
            filings: List of SECFiling objects
            
        Returns:
            List of SECFiling objects with PDF content and local file paths
        """
        logger.info(f"Processing {len(filings)} filings for PDF download")
        
        processed_filings = []
        for filing in filings:
            try:
                if not filing.documentURL:
                    logger.warning(f"Missing document URL for {filing.ticker} {filing.formType}")
                    continue
                
                # Generate a cache path for this filing
                cache_path = self._get_cache_path(filing)
                
                # Check if we already have this filing cached
                if cache_path.exists():
                    logger.info(f"Using cached PDF for {filing.ticker} {filing.formType} from {filing.filing_date}")
                    # Add the file path to the filing object
                    filing.pdf_path = str(cache_path)
                    processed_filings.append(filing)
                    continue
                
                # Convert URL to SEC.gov format for PDF generation
                sec_url = self._convert_to_sec_gov_url(filing.documentURL)
                if not sec_url:
                    logger.warning(f"Invalid document URL format: {filing.documentURL}")
                    continue
                
                logger.info(f"Downloading {filing.formType} filing for {filing.ticker} from {filing.filing_date} as PDF")
                
                # Download the filing as PDF
                pdf_data = await self._download_filing_as_pdf(sec_url)
                
                if pdf_data:
                    # Save to cache
                    with open(cache_path, 'wb') as f:
                        f.write(pdf_data)
                    
                    # Add the file path to the filing object
                    filing.pdf_path = str(cache_path)
                    
                    # Save metadata for future reference
                    self._save_filing_metadata(filing, cache_path, 'pdf')
                    
                    logger.info(f"Successfully downloaded and cached PDF for {filing.ticker} {filing.formType}")
                    processed_filings.append(filing)
                else:
                    logger.error(f"Failed to download PDF for {filing.ticker} {filing.formType}")
            except Exception as e:
                logger.error(f"Error processing PDF for {filing.ticker} {filing.formType}: {e}")
        
        return processed_filings
        
    def _get_cache_path(self, filing: SECFiling) -> Path:
        """
        Generate a cache file path for a filing.
        
        Args:
            filing: SECFiling object
            
        Returns:
            Path object for the cache file location
        """
        # Create a unique filename based on filing metadata
        filing_date_str = filing.filing_date.strftime("%Y-%m-%d")
        filename = f"{filing.ticker}_{filing.formType}_{filing.accessionNo}.pdf"
        
        # Create a subdirectory for the ticker to organize cache
        ticker_dir = self.cache_dir / filing.ticker
        ticker_dir.mkdir(exist_ok=True)
        
        return ticker_dir / filename
    
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
        
        # If we can't convert it, return None
        logger.warning(f"Could not convert URL to SEC.gov format: {url}")
        return None
    
    async def _make_http_request(self, url: str, params: Optional[Dict[str, Any]] = None, 
                          timeout: int = 30, binary: bool = False, max_retries: int = 3) -> Optional[Union[str, bytes]]:
        """
        Make an HTTP request with retry logic.
        
        Args:
            url: URL to request
            params: Optional query parameters
            timeout: Request timeout in seconds
            binary: Whether to return binary data or text
            max_retries: Maximum number of retry attempts
            
        Returns:
            Response content as string or bytes, or None if failed
        """
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params, timeout=timeout) as response:
                        if response.status == 200:
                            return await response.read() if binary else await response.text()
                        elif response.status == 429:  # Too Many Requests
                            logger.warning(f"Rate limit hit, retrying in {retry_delay} seconds")
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                        else:
                            error_text = await response.text()
                            logger.error(f"API error: {url}, {response.status}, {error_text}")
                            return None
            except Exception as e:
                logger.error(f"Error during HTTP request: {e}")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
        
        logger.error(f"Failed to complete HTTP request after {max_retries} attempts")
        return None
        
    async def _download_filing_as_pdf(self, sec_url: str) -> Optional[bytes]:
        """
        Download a SEC filing as a PDF using the PDF Generator API.
        
        Args:
            sec_url: The SEC.gov URL of the filing to download
            
        Returns:
            Binary PDF data if successful, None otherwise
        """
        params = {
            "token": self.api_key,
            "url": sec_url,
            "quality": "high"  # High quality PDFs
        }
        
        return await self._make_http_request(
            url=self.pdf_generator_url,
            params=params,
            timeout=60,  # Longer timeout for PDF generation
            binary=True
        )
    
    def _save_filing_metadata(self, filing: SECFiling, file_path: Path, metadata_type: str) -> None:
        """
        Save filing metadata for future reference.
        
        Args:
            filing: SECFiling object
            file_path: Path to the cached file (PDF or HTML)
            metadata_type: Type of metadata to save ('pdf' or 'html')
        """
        metadata = {
            "ticker": filing.ticker,
            "filing_type": filing.formType,
            "filing_date": filing.filing_date.isoformat(),
            "accession_no": filing.accessionNo,
            "document_url": filing.documentURL,
            "text_url": filing.textURL,
            "company_name": filing.company_name,
            "cik": filing.cik,
            "cached_at": datetime.now().isoformat(),
            "metadata_type": metadata_type
        }
        
        # Add the specific file path based on metadata type
        if metadata_type == 'pdf':
            metadata["pdf_path"] = str(file_path)
        elif metadata_type == 'html':
            metadata["html_path"] = str(file_path)
        
        # Create metadata directory if it doesn't exist
        metadata_dir = self.cache_dir / "metadata"
        metadata_dir.mkdir(exist_ok=True)
        
        # Create a unique filename for the metadata
        metadata_filename = f"{filing.ticker}_{filing.formType}_{filing.accessionNo}_{metadata_type}.json"
        metadata_path = metadata_dir / metadata_filename
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    async def _process_html_filings(self, filings: List[SECFiling]) -> List[SECFiling]:
        """
        Process filings to retrieve HTML content.
        
        Args:
            filings: List of SECFiling objects
            
        Returns:
            List of SECFiling objects with HTML content
        """
        logger.info(f"Processing {len(filings)} filings for HTML retrieval")
        
        processed_filings = []
        for filing in filings:
            try:
                if not filing.textURL:
                    logger.warning(f"Missing text URL for {filing.ticker} {filing.formType}")
                    continue
                
                # Generate a cache path for this filing's HTML content
                cache_path = self._get_html_cache_path(filing)
                
                # Check if we already have this filing cached
                if cache_path.exists():
                    logger.info(f"Using cached HTML for {filing.ticker} {filing.formType} from {filing.filing_date}")
                    # Add the file path to the filing object for reference
                    filing.html_path = str(cache_path)
                    processed_filings.append(filing)
                    continue
                
                logger.info(f"Retrieving HTML content for {filing.formType} filing for {filing.ticker} from {filing.filing_date}")
                
                # Retrieve the HTML content
                # Extract the path after "edgar/data" from the document URL
                if "edgar/data" in filing.documentURL:
                    # Extract the path after "edgar/data"
                    path_parts = filing.documentURL.split("edgar/data")
                    if len(path_parts) > 1:
                        edgar_path = f"edgar/data{path_parts[1]}"
                        # Construct the archive URL with the extracted path
                        archive_url = f"https://archive.sec-api.io/{edgar_path}?token={self.api_key}"
                        filing.textURL = archive_url
                    else:
                        logger.warning(f"Could not extract path from document URL: {filing.documentURL}")
                else:
                    logger.warning(f"Document URL does not contain 'edgar/data': {filing.documentURL}")
                html_content = await self._fetch_filing_html(filing.textURL)
                
                if html_content:
                    # Save to cache
                    with open(cache_path, 'w', encoding='utf-8') as f:
                        f.write(html_content)
                    
                    # Add the file path to the filing object for reference
                    filing.html_path = str(cache_path)
                    
                    # Save metadata for future reference
                    self._save_filing_metadata(filing, cache_path, 'html')
                    
                    logger.info(f"Successfully retrieved and cached HTML for {filing.ticker} {filing.formType}")
                    processed_filings.append(filing)
                else:
                    logger.error(f"Failed to retrieve HTML for {filing.ticker} {filing.formType}")
            except Exception as e:
                logger.error(f"Error processing HTML for {filing.ticker} {filing.formType}: {e}")
        
        return processed_filings
    
    def _get_html_cache_path(self, filing: SECFiling) -> Path:
        """
        Generate a cache file path for a filing's HTML content.
        
        Args:
            filing: SECFiling object
            
        Returns:
            Path object for the HTML cache file location
        """
        # Create a unique filename based on filing metadata
        filing_date_str = filing.filing_date.strftime("%Y-%m-%d")
        filename = f"{filing.ticker}_{filing.formType}_{filing.accessionNo}.html"
        
        # Create a subdirectory for HTML files
        html_dir = self.cache_dir / "html" / filing.ticker
        html_dir.mkdir(parents=True, exist_ok=True)
        
        return html_dir / filename
    
    async def _fetch_filing_html(self, url: str) -> Optional[str]:
        """
        Fetch the HTML content of a filing.
        
        Args:
            url: URL to the filing's text or HTML version
            
        Returns:
            HTML content as string if successful, None otherwise
        """
        return await self._make_http_request(
            url=url,
            timeout=30,
            binary=False
        )
    
    def _filter_filings_by_date(self, filings: List[SECFiling], target_date: Date) -> List[SECFiling]:
        """
        Filter filings by date.
        
        Args:
            filings: List of SECFiling objects
            target_date: Date to filter by
            
        Returns:
            Filtered list of SECFiling objects
        """
        filtered_filings = []
        target_datetime = datetime.combine(target_date, datetime.min.time())
        
        for filing in filings:
            if filing.filing_date.date() == target_date:
                filtered_filings.append(filing)
                
        return filtered_filings
    