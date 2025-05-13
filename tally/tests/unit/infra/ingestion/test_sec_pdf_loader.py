"""Tests for the EDGARPDFLoader class."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.documents import Document

from infra.acquisition.models import AcquisitionOutput
from infra.acquisition.sec_fetcher import SECFiling
from infra.ingestion.sec_pdf_loader import EDGARPDFLoader


@pytest.fixture
def sample_sec_filing():
    """Create a sample SECFiling for testing."""
    return SECFiling(
        accessionNo="0001193125-23-012345",
        formType="10-K",
        filing_date="2023-02-15",
        company_name="Test Company Inc.",
        ticker="TEST",
        cik="0000123456",
        documentURL="https://www.sec.gov/Archives/edgar/data/123456/000123456789012345/test-20230215.htm",
        chunk_type="text",
    )


@pytest.fixture
def acquisition_output(sample_sec_filing):
    """Create a sample AcquisitionOutput for testing."""
    # Mock the AcquisitionOutput from a SECFiling
    output = MagicMock(spec=AcquisitionOutput)
    output.get_uris.return_value = [sample_sec_filing.documentURL]
    output.get_metadata.return_value = sample_sec_filing
    return output


@pytest.mark.parametrize(
    ("mock_sqlalchemy_engine", "mock_cache", "mock_settings"),
    [
        (
            "infra.ingestion.sec_pdf_loader",
            "infra.ingestion.sec_pdf_loader",
            "infra.ingestion.sec_pdf_loader",
        )
    ],
    indirect=True,
)
class TestEDGARPDFLoader:
    """Tests for the EDGARPDFLoader class."""

    def test_init(self, mock_sqlalchemy_engine, mock_cache, mock_settings):
        """Test initialization of EDGARPDFLoader."""
        # Test with API key provided
        loader = EDGARPDFLoader(api_key="test_key")
        assert loader.api_key == "test_key"
        assert loader.pdf_generator_url == "https://api.sec-api.io/filing-reader"

        # Test with API key from settings
        loader = EDGARPDFLoader(api_key=None)
        assert loader.api_key == "test_api_key"  # From mock_settings

    def test_init_no_api_key(self, mock_sqlalchemy_engine, mock_cache, mock_settings):
        """Test initialization fails when no API key is provided."""
        # Override the mock settings to return None for SEC_API_KEY
        mock_settings.return_value.SEC_API_KEY = None

        with pytest.raises(ValueError, match="SEC API key is not set"):
            EDGARPDFLoader(api_key=None)

    @pytest.mark.asyncio
    async def test_load_with_cache_hit(
        self, mock_sqlalchemy_engine, mock_cache, mock_settings, acquisition_output
    ):
        """Test loading documents with cache hit."""
        # Configure mock cache to return cached PDF data
        sample_pdf_data = "%PDF-1.5\nTest PDF content"
        mock_cache_instance = mock_cache
        mock_cache_instance.generate_id.return_value = "test_cache_id"
        mock_cache_instance.get.return_value = {"pdf_content": sample_pdf_data}

        # Create the loader
        loader = EDGARPDFLoader(api_key="test_key")

        # Call load method
        docs = await loader.load([acquisition_output])

        # Verify results
        assert len(docs) == 1
        assert isinstance(docs[0], Document)
        assert docs[0].page_content == sample_pdf_data

        # Verify cache was checked
        mock_cache_instance.generate_id.assert_called_once()
        mock_cache_instance.get.assert_called_once_with("test_cache_id")

        # Verify download was not attempted
        mock_cache_instance.write.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_with_cache_miss(
        self,
        mock_sqlalchemy_engine,
        mock_cache,
        mock_settings,
        acquisition_output,
        sample_sec_filing,
    ):
        """Test loading documents with cache miss."""
        # Configure mock cache to return no cached data
        sample_pdf_data = "%PDF-1.5\nTest PDF content"
        mock_cache_instance = mock_cache
        mock_cache_instance.generate_id.return_value = "test_cache_id"
        mock_cache_instance.get.return_value = None

        # Create the loader
        loader = EDGARPDFLoader(api_key="test_key")

        # Mock the _download_filing_as_pdf method
        with patch.object(
            loader, "_download_filing_as_pdf", AsyncMock(return_value=sample_pdf_data)
        ):
            # Call load method
            docs = await loader.load([acquisition_output])

            # Verify results
            assert len(docs) == 1
            assert isinstance(docs[0], Document)
            assert docs[0].page_content == sample_pdf_data

            # Verify cache was checked
            mock_cache_instance.generate_id.assert_called_once()
            mock_cache_instance.get.assert_called_once_with("test_cache_id")

            # Verify PDF was downloaded and cached
            loader._download_filing_as_pdf.assert_called_once()
            mock_cache_instance.write.assert_called_once_with(
                "test_cache_id", pdf_content=sample_pdf_data
            )

    @pytest.mark.asyncio
    async def test_download_filing_as_pdf(
        self, mock_sqlalchemy_engine, mock_cache, mock_settings
    ):
        """Test downloading a filing as PDF."""
        # Sample PDF data
        sample_pdf_data = b"%PDF-1.5\nTest PDF content"

        # Create the loader
        loader = EDGARPDFLoader(api_key="test_key")

        # Mock the _make_http_request method
        with patch.object(
            loader, "_make_http_request", AsyncMock(return_value=sample_pdf_data)
        ):
            # Call download method
            sec_url = "https://www.sec.gov/Archives/edgar/data/123456/000123456789012345/test-20230215.htm"
            result = await loader._download_filing_as_pdf(sec_url)

            # Verify results
            assert result == sample_pdf_data

            # Verify HTTP request was made with correct parameters
            loader._make_http_request.assert_called_once_with(
                url="https://api.sec-api.io/filing-reader",
                params={
                    "token": "test_key",
                    "url": sec_url,
                    "quality": "high",
                },
                timeout=60,
                binary=True,
            )

    # @pytest.mark.asyncio
    # async def test_make_http_request_success(
    #     self, mock_sqlalchemy_engine, mock_cache, mock_settings
    # ):
    #     """Test successful HTTP request."""
    #     # Sample response data
    #     sample_data = b"Test response data"

    #     # Create the loader
    #     loader = EDGARPDFLoader(api_key="test_key")

    #     # Mock aiohttp.ClientSession and its response
    #     mock_response = MagicMock()
    #     mock_response.status = 200
    #     mock_response.read = AsyncMock(return_value=sample_data)

    #     mock_session = MagicMock()
    #     mock_session.get = AsyncMock(return_value=mock_response)

    #     # Mock the ClientSession context manager
    #     with patch("aiohttp.ClientSession", return_value=mock_session):
    #         # Call method
    #         result = await loader._make_http_request(
    #             url="https://test-url.com",
    #             params={"test": "param"},
    #             timeout=30,
    #             binary=True,
    #         )

    #         # Verify results
    #         assert result == sample_data

    #         # Verify HTTP request was made with correct parameters
    #         mock_session.get.assert_called_once_with(
    #             "https://test-url.com", params={"test": "param"}, timeout=30
    #         )

    # @pytest.mark.asyncio
    # async def test_make_http_request_error(
    #     self, mock_sqlalchemy_engine, mock_cache, mock_settings, mock_aiohttp_session
    # ):
    #     """Test HTTP request with error response."""
    #     # Create the loader
    #     loader = EDGARPDFLoader(api_key="test_key")

    #     mock_session, mock_response = mock_aiohttp_session
    #     # Call method
    #     result = await loader._make_http_request(
    #         url="https://test-url.com", params={"test": "param"}
    #     )

    #     # Verify results
    #     assert result is None

    #     # Verify HTTP request was made
    #     mock_session.get.assert_called_once()
    #     # Verify error response was read
    #     mock_response.text.assert_called_once()
