import asyncio
import logging
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Union

import aiohttp
from langchain_core.documents import Document
from sqlalchemy import LargeBinary
from sqlalchemy.orm import mapped_column

from infra.acquisition.models import AcquisitionOutput
from infra.acquisition.sec_fetcher import SECFiling
from infra.config.settings import get_settings
from infra.databases.cache import Cache
from infra.databases.engine import get_sqlalchemy_engine
from infra.ingestion.models import IDocumentLoader


# Set up logging
logger = logging.getLogger(__name__)


class EDGARPDFLoader(IDocumentLoader):
    """
    A EDGAR PDF loader that loads PDF documents from a given path (URL or local path)
    and returns the raw PDF data
    """

    _CACHE_COLUMNS = {
        "pdf_content": mapped_column(LargeBinary, nullable=False),
    }

    def __init__(self, api_key: str):
        """
        Initializes the EDGARPDFLoader with the specified API key.
        """
        self.api_key = api_key or get_settings().SEC_API_KEY
        if not self.api_key:
            raise ValueError("SEC API key is not set")

        self.pdf_generator_url = "https://api.sec-api.io/filing-reader"
        self.session = None
        self._cache = Cache(
            engine=get_sqlalchemy_engine(),
            table_name="pdf_loader",
            column_mapping=self._CACHE_COLUMNS,
        )

    async def load(self, sources: List[AcquisitionOutput]) -> List[Document]:
        documents = []
        for source in sources:
            documents.extend(await self._process_pdf_filings(source))
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
        metadata = src.get_metadata()
        for uri in src.get_uris():
            metadata.source = uri
            request_hash = self._cache.generate_id(uri)
            cache_entry = self._cache.get(request_hash)
            pdf_data: bytes = cache_entry.get("pdf_content") if cache_entry else None
            if pdf_data:
                docs.append(
                    Document(page_content=pdf_data, metadata=metadata.model_dump())
                )
                continue

            if not isinstance(metadata, SECFiling):
                raise ValueError(
                    f"Invalid metadata type: {type(metadata)}. Expected SECFiling."
                )
            metadata._convert_to_sec_gov_url(uri)
            sec_url = metadata._convert_to_sec_gov_url(uri)
            if not sec_url:
                logger.warning(f"Invalid document URL format: {uri}")
                continue

            logger.info(
                f"Downloading {metadata.formType} filing for {metadata.ticker} from {metadata.filing_date} as PDF"
            )
            # Download the filing as PDF
            pdf_data = await self._download_filing_as_pdf(sec_url)
            docs.append(Document(page_content=pdf_data, metadata=metadata.model_dump()))
            logger.info(
                f"Successfully downloaded and cached PDF for {metadata.ticker} {metadata.formType}"
            )
            self._cache.write(
                request_hash,
                pdf_content=pdf_data,
            )
        return docs

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

        # for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        return await response.read()
                    elif response.status == 429:  # Too Many Requests
                        logger.warning(
                            f"Rate limit hit, retrying in {retry_delay} seconds"
                        )
                        # await asyncio.sleep(retry_delay)
                        # retry_delay *= 2  # Exponential backoff
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"API error: {url}, {response.status}, {error_text}"
                        )
                        return None
        except Exception as e:
            logger.error(f"Error during HTTP request: {e}")
            # await asyncio.sleep(retry_delay)
            # retry_delay *= 2

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
