import asyncio
import hashlib
import json
import logging
from datetime import date as Date
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import aiohttp
from langchain_core.documents import Document
from pydantic import BaseModel, Field, field_validator

import infra.acquisition.models as models
from infra.acquisition.models import (
    AcquisitionOutput,
    DataFormat,
    FilingType,
    SECFiling,
)
from infra.core.config import settings
from infra.core.exceptions import DataFetchError, ValidationError
from infra.core.interfaces import IDataFetcher, IDocumentLoader

# Set up logging
logger = logging.getLogger(__name__)


class EDGARPDFLoader(IDocumentLoader):
    """
    A EDGAR PDF loader that loads PDF documents from a given path (URL or local path)
    and returns the raw PDF data
    """

    def __init__(self, api_key: str):
        """
        Initializes the EDGARPDFLoader with the specified API key.
        """
        self.api_key = api_key or settings.SEC_API_KEY
        if not self.api_key:
            raise ValueError("SEC API key is not set")

        self.pdf_generator_url = "https://api.sec-api.io/filing-reader"
        self.session = None

    async def load(self, sources: List[AcquisitionOutput]) -> List[Document]:
        documents = []
        for source in sources:
            documents.extend(self._process_pdf_filings(source))
        return documents

    async def _process_pdf_filings(self, src: AcquisitionOutput) -> List[Document]:
        """
        Process filings to download PDF versions.

        Args:
            filings: List of SECFiling objects

        Returns:
            List of SECFiling objects with PDF content and local file paths
        """
        logger.info(f"Processing {len(src.get_uris())} filings for PDF download")
        docs = []
        for uri in src.get_uris():
            # TODO(neelp): Use remote caching system
            # Generate a cache path for this filing
            cache_path = self._get_cache_path(src.get_metadata())

            # Check if we already have this filing cached
            if cache_path.exists():
                logger.info(
                    f"Using cached PDF for {filing.ticker} {filing.formType} from {filing.filing_date}"
                )
                # Add the file path to the filing object
                filing.pdf_path = str(cache_path)
                processed_filings.append(filing)
                continue
            sec_url = self._convert_to_sec_gov_url(uri)
            if not sec_url:
                logger.warning(f"Invalid document URL format: {filing.documentURL}")
                continue

            logger.info(
                f"Downloading {src.get_metadata().get("formType")} filing for {src.get_metadata().get("ticker")} from {src.get_metadata().get("filing_date")} as PDF"
            )
            # Download the filing as PDF
            pdf_data = await self._download_filing_as_pdf(sec_url)

            if pdf_data:
                # Save to cache
                # TODO(neelp): Use remote caching system
                with open(cache_path, "wb") as f:
                    f.write(pdf_data)

                # Add the file path to the filing object
                filing.pdf_path = str(cache_path)

                # Save metadata for future reference
                self._save_filing_metadata(filing, cache_path, "pdf")

                logger.info(
                    f"Successfully downloaded and cached PDF for {filing.ticker} {filing.formType}"
                )
                processed_filings.append(filing)
            else:
                logger.error(
                    f"Failed to download PDF for {filing.ticker} {filing.formType}"
                )
        return docs

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
        # Replace any slashes in formType with hyphens for valid filenames
        clean_form_type = filing.formType.replace("/", "-")
        filename = f"{filing.ticker}_{clean_form_type}_{filing.accessionNo}.pdf"

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

    async def _make_http_request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
        binary: bool = False,
        max_retries: int = 3,
    ) -> Optional[Union[str, bytes]]:
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
                    async with session.get(
                        url, params=params, timeout=timeout
                    ) as response:
                        if response.status == 200:
                            return (
                                await response.read()
                                if binary
                                else await response.text()
                            )
                        elif response.status == 429:  # Too Many Requests
                            logger.warning(
                                f"Rate limit hit, retrying in {retry_delay} seconds"
                            )
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                        else:
                            error_text = await response.text()
                            logger.error(
                                f"API error: {url}, {response.status}, {error_text}"
                            )
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
            "quality": "high",  # High quality PDFs
        }

        return await self._make_http_request(
            url=self.pdf_generator_url,
            params=params,
            timeout=60,  # Longer timeout for PDF generation
            binary=True,
        )

    def _save_filing_metadata(
        self, filing: SECFiling, file_path: Path, metadata_type: str
    ) -> None:
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
            "metadata_type": metadata_type,
        }

        # Add the specific file path based on metadata type
        if metadata_type == "pdf":
            metadata["pdf_path"] = str(file_path)
        elif metadata_type == "html":
            metadata["html_path"] = str(file_path)

        # Create metadata directory if it doesn't exist
        metadata_dir = self.cache_dir / "metadata"
        metadata_dir.mkdir(exist_ok=True)

        # Create a unique filename for the metadata
        metadata_filename = f"{filing.ticker}_{filing.formType}_{filing.accessionNo}_{metadata_type}.json"
        metadata_path = metadata_dir / metadata_filename

        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
