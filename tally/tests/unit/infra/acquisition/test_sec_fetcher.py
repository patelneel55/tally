"""
Tests for the SEC Fetcher
------------------------

This module tests the SEC fetcher functionality for retrieving SEC filings.
"""

import json
import pickle
from datetime import date
from datetime import datetime
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import aiohttp
import pytest
from aiohttp import ClientError
from pydantic import ValidationError

from infra.acquisition.exceptions import ValidationError as AcquisitionValidationError
from infra.acquisition.models import DataFormat
from infra.acquisition.sec_fetcher import DataFetchError
from infra.acquisition.sec_fetcher import EDGARFetcher
from infra.acquisition.sec_fetcher import FilingRequest
from infra.acquisition.sec_fetcher import FilingType
from infra.acquisition.sec_fetcher import SECFiling
from infra.acquisition.sec_fetcher import sec_api_query_response_schema
from infra.collections.models import ChunkType


# More reliable approach to mocking aiohttp Session
class MockResponse:
    def __init__(self, data, status=200):
        self._data = data
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def json(self):
        return self._data

    async def text(self):
        return str(self._data)


class MockClientSession:
    def __init__(self, response=None, side_effect=None):
        self.response = response
        self.side_effect = side_effect
        self.post_called = False
        self.post_args = None
        self.post_kwargs = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def post(self, *args, **kwargs):
        self.post_called = True
        self.post_args = args
        self.post_kwargs = kwargs

        if self.side_effect:
            raise self.side_effect

        return self.response


class TestFilingRequest:
    def test_valid_filing_request_cik_and_ticker(self):
        data = {
            "identifier": ["0000320193", "AAPL"],
            "filing_type": FilingType.ANNUAL_REPORT,
            "start_date": date(2023, 1, 1),
            "end_date": date(2023, 12, 31),
            "max_size": 5,
            "data_format": DataFormat.HTML,
        }
        req = FilingRequest(**data)
        assert req.identifier == ["0000320193", "AAPL"]
        assert (
            req.filing_type == FilingType.ANNUAL_REPORT.value
        )  # or "10-K" if use_enum_values=True
        assert req.start_date == date(2023, 1, 1)
        assert req.end_date == date(2023, 12, 31)
        assert req.max_size == 5
        assert req.data_format == DataFormat.HTML

    def test_valid_filing_request_only_cik(self):
        data = {"identifier": ["0000320193"], "max_size": 1}
        req = FilingRequest(**data)
        assert req.identifier == ["0000320193"]
        assert req.filing_type is None
        assert req.start_date is None
        assert req.end_date is None
        assert req.max_size == 1
        assert req.data_format == DataFormat.HTML  # Default

    def test_valid_filing_request_only_ticker(self):
        data = {"identifier": ["MSFT"]}
        req = FilingRequest(**data)
        assert req.identifier == ["MSFT"]
        assert req.max_size == 1  # Default
        assert req.data_format == DataFormat.HTML  # Default

    def test_filing_request_default_values(self):
        data = {"identifier": ["GOOGL"]}
        req = FilingRequest(**data)
        assert req.max_size == 1
        assert req.data_format == DataFormat.HTML
        assert req.filing_type is None
        assert req.start_date is None
        assert req.end_date is None

    def test_invalid_identifier_empty_list(self):
        with pytest.raises(ValidationError) as exc_info:
            FilingRequest(identifier=[])
        assert "Identifier cannot be empty" in str(exc_info.value)

    def test_invalid_identifier_cik_too_long(self):
        with pytest.raises(ValidationError) as exc_info:
            FilingRequest(identifier=["12345678901"])
        assert "CIK must be 1-10 digits: 12345678901" in str(exc_info.value)

    def test_invalid_identifier_cik_not_digit(self):
        # This case is handled by the ticker validation if not all digits
        # If we want a specific CIK error for non-digits, validator needs change
        # Current validator: if it's digits, checks length. If not digits, checks ticker rules.
        pass

    def test_invalid_identifier_ticker_too_long(self):
        with pytest.raises(ValidationError) as exc_info:
            FilingRequest(identifier=["ABCDEF"])
        assert "Ticker must be 1-5 alphanumeric characters: ABCDEF" in str(
            exc_info.value
        )

    def test_invalid_identifier_ticker_not_alnum(self):
        with pytest.raises(ValidationError) as exc_info:
            FilingRequest(identifier=["AB_CD"])
        assert "Ticker must be 1-5 alphanumeric characters: AB_CD" in str(
            exc_info.value
        )

    def test_invalid_identifier_mixed_valid_and_invalid(self):
        with pytest.raises(ValidationError) as exc_info:
            FilingRequest(identifier=["AAPL", "INVALIDTICKERTOOLONG"])
        assert (
            "Ticker must be 1-5 alphanumeric characters: INVALIDTICKERTOOLONG"
            in str(exc_info.value)
        )

    def test_filing_type_enum_value(self):
        req = FilingRequest(identifier=["TSLA"], filing_type="10-Q")
        assert req.filing_type == FilingType.QUARTERLY_REPORT.value

    def test_invalid_filing_type(self):
        with pytest.raises(ValidationError):
            FilingRequest(identifier=["TSLA"], filing_type="INVALID-TYPE")

    def test_date_conversion(self):
        req = FilingRequest(
            identifier=["IBM"], start_date="2023-01-01", end_date="2023-12-31"
        )
        assert req.start_date == date(2023, 1, 1)
        assert req.end_date == date(2023, 12, 31)

    def test_max_size_validation(self):
        # Pydantic handles type validation for int.
        # If we had custom rules (e.g. >0), we would test them.
        req = FilingRequest(identifier=["AMZN"], max_size=10)
        assert req.max_size == 10

    def test_data_format_enum_value(self):
        req = FilingRequest(identifier=["NFLX"], data_format="pdf")
        assert req.data_format == DataFormat.PDF

    def test_invalid_data_format(self):
        with pytest.raises(ValidationError):
            FilingRequest(identifier=["NFLX"], data_format="invalid_format")


class TestFilingType:
    """Tests for the FilingType enum."""

    def test_filing_type_enum_values(self):
        """Test that FilingType enum has the expected values."""
        assert FilingType.ANNUAL_REPORT == "10-K"
        assert FilingType.QUARTERLY_REPORT == "10-Q"
        assert FilingType.CURRENT_REPORT == "8-K"
        assert FilingType.PROXY_STATEMENT == "DEF 14A"
        assert FilingType.REGISTRATION_STATEMENT == "S-1"

    def test_filing_type_enum_members(self):
        """Test that FilingType enum has the expected members."""
        assert "ANNUAL_REPORT" in FilingType.__members__
        assert "QUARTERLY_REPORT" in FilingType.__members__
        assert "CURRENT_REPORT" in FilingType.__members__
        assert "PROXY_STATEMENT" in FilingType.__members__
        assert "REGISTRATION_STATEMENT" in FilingType.__members__


class TestAPISchemaValidation:
    """Tests for the SEC API schema validation."""

    def test_schema_validation_valid_data(self):
        """Test schema validation with valid data."""
        valid_filing_data = [
            {
                "accessionNo": "0001193125-23-012345",
                "formType": "10-K",
                "cik": "0000320193",
                "companyName": "Apple Inc.",
                "filedAt": "2023-02-15",
                "ticker": "AAPL",
                "documentFormatFiles": [
                    {
                        "type": "10-K",
                        "documentUrl": "https://www.sec.gov/Archives/edgar/data/320193/000032019323000010/aapl-20221231.htm",
                    }
                ],
                "extraField": "should be ignored",
            }
        ]

        # Schema validation should succeed and return SECFiling object
        result = sec_api_query_response_schema.validate(valid_filing_data)

        assert len(result) == 1
        assert isinstance(result[0], SECFiling)
        assert result[0].accessionNo == "0001193125-23-012345"
        assert result[0].formType == "10-K"
        assert result[0].cik == "0000320193"
        assert result[0].company_name == "Apple Inc."
        assert result[0].ticker == "AAPL"

    def test_schema_validation_invalid_data(self):
        """Test schema validation with invalid data."""
        invalid_filing_data = [
            {
                "accessionNo": "0001193125-23-012345",
                "formType": "10-K",
                "cik": "0000320193",
                "companyName": "Apple Inc.",
                "filedAt": "2023-02-15T00:00:00.000Z",
                # missing ticker
                "documentFormatFiles": [
                    {
                        "type": "10-K",
                        "documentUrl": "https://www.sec.gov/Archives/edgar/data/320193/000032019323000010/aapl-20221231.htm",
                    }
                ],
            }
        ]

        # Schema validation should fail
        with pytest.raises(Exception):
            sec_api_query_response_schema.validate(invalid_filing_data)

    def test_schema_validation_missing_document_url(self):
        """Test schema validation with missing document URL."""
        # Missing documentFormatFiles
        missing_url_data = [
            {
                "accessionNo": "0001193125-23-012345",
                "formType": "10-K",
                "cik": "0000320193",
                "companyName": "Apple Inc.",
                "filedAt": "2023-02-15T00:00:00.000Z",
                "ticker": "AAPL",
                "documentFormatFiles": None,  # This should still validate, but URL will be empty
            }
        ]

        # Schema validation should succeed but documentURL will be empty
        result = sec_api_query_response_schema.validate(missing_url_data)

        assert len(result) == 1
        assert isinstance(result[0], SECFiling)
        assert result[0].documentURL == ""  # Should default to empty string


@pytest.mark.parametrize(
    ("mock_sqlalchemy_engine", "mock_cache", "mock_settings"),
    [
        (
            "infra.acquisition.sec_fetcher",
            "infra.acquisition.sec_fetcher",
            "infra.acquisition.sec_fetcher",
        )
    ],
    indirect=True,
)
class TestEDGARFetcher:
    """Tests for the EDGARFetcher class."""

    def test_init_with_api_key(self, mock_sqlalchemy_engine, mock_cache, mock_settings):
        """Test initializing with a provided API key."""
        fetcher = EDGARFetcher(api_key="provided_key")
        assert fetcher.api_key == "provided_key"
        assert fetcher.query_url == "https://api.sec-api.io"
        assert fetcher.session is None

    def test_init_with_settings_api_key(
        self, mock_sqlalchemy_engine, mock_cache, mock_settings
    ):
        """Test initializing with API key from settings."""
        fetcher = EDGARFetcher()
        assert fetcher.api_key == "test_api_key"

    def test_init_without_api_key(
        self, mock_sqlalchemy_engine, mock_cache, mock_settings
    ):
        """Test initializing without API key raises ValueError."""
        mock_settings.return_value.SEC_API_KEY = None
        with pytest.raises(ValueError, match="SEC API key is not set"):
            EDGARFetcher()

    def test_build_search_query_cik_only(
        self, mock_sqlalchemy_engine, mock_cache, mock_settings
    ):
        """Test building search query with CIK only."""
        request = FilingRequest(identifier=["0000320193"])
        fetcher = EDGARFetcher(api_key="test_key")

        query = fetcher._build_search_query(request)

        assert query["query"] == "cik:(320193)"
        assert query["from"] == "0"
        assert query["size"] == 1
        assert query["sort"] == [{"filedAt": {"order": "desc"}}]

    def test_build_search_query_ticker_only(
        self, mock_sqlalchemy_engine, mock_cache, mock_settings
    ):
        """Test building search query with ticker only."""
        request = FilingRequest(identifier=["AAPL"])
        fetcher = EDGARFetcher(api_key="test_key")

        query = fetcher._build_search_query(request)

        assert query["query"] == "ticker:(AAPL)"
        assert query["size"] == 1

    def test_build_search_query_mixed_identifiers(
        self, mock_sqlalchemy_engine, mock_cache, mock_settings
    ):
        """Test building search query with mixed CIK and ticker."""
        request = FilingRequest(identifier=["0000320193", "MSFT"])
        fetcher = EDGARFetcher(api_key="test_key")

        query = fetcher._build_search_query(request)

        assert "cik:(320193)" in query["query"]
        assert "ticker:(MSFT)" in query["query"]
        assert " OR " in query["query"]

    def test_build_search_query_with_filing_type(
        self, mock_sqlalchemy_engine, mock_cache, mock_settings
    ):
        """Test building search query with filing type."""
        request = FilingRequest(
            identifier=["AAPL"], filing_type=FilingType.ANNUAL_REPORT
        )
        fetcher = EDGARFetcher(api_key="test_key")

        query = fetcher._build_search_query(request)

        assert "ticker:(AAPL)" in query["query"]
        assert 'formType:"10-K"' in query["query"]
        assert " AND " in query["query"]

    def test_build_search_query_with_date_range(
        self, mock_sqlalchemy_engine, mock_cache, mock_settings
    ):
        """Test building search query with date range."""
        request = FilingRequest(
            identifier=["AAPL"],
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
        )
        fetcher = EDGARFetcher(api_key="test_key")

        query = fetcher._build_search_query(request)

        assert "ticker:(AAPL)" in query["query"]
        assert "filedAt:[2023-01-01 TO 2023-12-31]" in query["query"]
        assert " AND " in query["query"]

    def test_build_search_query_with_start_date_only(
        self, mock_sqlalchemy_engine, mock_cache, mock_settings
    ):
        """Test building search query with start date only."""
        request = FilingRequest(identifier=["AAPL"], start_date=date(2023, 1, 1))
        fetcher = EDGARFetcher(api_key="test_key")

        query = fetcher._build_search_query(request)

        assert "ticker:(AAPL)" in query["query"]
        assert "filedAt:[2023-01-01 TO *]" in query["query"]

    def test_build_search_query_with_end_date_only(
        self, mock_sqlalchemy_engine, mock_cache, mock_settings
    ):
        """Test building search query with end date only."""
        request = FilingRequest(identifier=["AAPL"], end_date=date(2023, 12, 31))
        fetcher = EDGARFetcher(api_key="test_key")

        query = fetcher._build_search_query(request)

        assert "ticker:(AAPL)" in query["query"]
        assert "filedAt:[* TO 2023-12-31]" in query["query"]

    def test_build_search_query_with_max_size(
        self, mock_sqlalchemy_engine, mock_cache, mock_settings
    ):
        """Test building search query with custom max size."""
        request = FilingRequest(identifier=["AAPL"], max_size=10)
        fetcher = EDGARFetcher(api_key="test_key")

        query = fetcher._build_search_query(request)

        assert query["size"] == 10

    @pytest.mark.asyncio
    async def test_fetch_filings_from_api_success(
        self, mock_sqlalchemy_engine, mock_cache, mock_settings
    ):
        """Test successful API fetch operation."""
        response_data = {
            "filings": [
                {
                    "accessionNo": "0001193125-23-012345",
                    "formType": "10-K",
                    "cik": "0000320193",
                    "companyName": "Apple Inc.",
                    "filedAt": "2023-02-15",
                    "ticker": "AAPL",
                    "documentFormatFiles": [
                        {
                            "type": "10-K",
                            "documentUrl": "https://www.sec.gov/Archives/edgar/data/320193/000032019323000010/aapl-20221231.htm",
                        }
                    ],
                }
            ]
        }

        # Create our response and session mocks
        mock_response = MockResponse(response_data)
        mock_session = MockClientSession(response=mock_response)

        # Patch the ClientSession to return our mock
        with patch("aiohttp.ClientSession", return_value=mock_session):
            fetcher = EDGARFetcher(api_key="test_key")
            search_query = {"query": "ticker:(AAPL)", "from": "0", "size": 1}

            filings = await fetcher._fetch_filings_from_api(search_query)

            # Verify the response
            assert len(filings) == 1
            assert isinstance(filings[0], SECFiling)
            assert filings[0].accessionNo == "0001193125-23-012345"
            assert filings[0].formType == "10-K"
            assert filings[0].cik == "0000320193"
            assert filings[0].company_name == "Apple Inc."
            assert filings[0].ticker == "AAPL"
            assert (
                filings[0].documentURL
                == "https://www.sec.gov/Archives/edgar/data/320193/000032019323000010/aapl-20221231.htm"
            )

            # Verify the post method was called correctly
            assert mock_session.post_called is True
            assert mock_session.post_args[0] == "https://api.sec-api.io"
            assert mock_session.post_kwargs["headers"] == {
                "Authorization": "test_key",
                "Content-Type": "application/json",
            }
            assert mock_session.post_kwargs["json"] == search_query

    @pytest.mark.asyncio
    async def test_fetch_filings_from_api_unauthorized(
        self, mock_sqlalchemy_engine, mock_cache, mock_settings
    ):
        """Test API unauthorized error."""
        # Create a mock response with 401 status
        mock_response = MockResponse({}, status=401)
        mock_session = MockClientSession(response=mock_response)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            fetcher = EDGARFetcher(api_key="invalid_key")
            search_query = {"query": "ticker:(AAPL)", "from": "0", "size": 1}

            with pytest.raises(
                DataFetchError, match="Invalid API key or authorization failed"
            ):
                await fetcher._fetch_filings_from_api(search_query)

    @pytest.mark.asyncio
    async def test_fetch_filings_from_api_rate_limit(
        self, mock_sqlalchemy_engine, mock_cache, mock_settings
    ):
        """Test API rate limit error."""
        # Create a mock response with 429 status
        mock_response = MockResponse({}, status=429)
        mock_session = MockClientSession(response=mock_response)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            fetcher = EDGARFetcher(api_key="test_key")
            search_query = {"query": "ticker:(AAPL)", "from": "0", "size": 1}

            with pytest.raises(DataFetchError, match="Rate limit exceeded"):
                await fetcher._fetch_filings_from_api(search_query)

    @pytest.mark.asyncio
    async def test_fetch_filings_from_api_other_error(
        self, mock_sqlalchemy_engine, mock_cache, mock_settings
    ):
        """Test other API error."""
        # Create a mock response with 500 status
        mock_response = MockResponse("Internal Server Error", status=500)
        mock_session = MockClientSession(response=mock_response)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            fetcher = EDGARFetcher(api_key="test_key")
            search_query = {"query": "ticker:(AAPL)", "from": "0", "size": 1}

            with pytest.raises(DataFetchError, match="Failed to fetch filings: 500"):
                await fetcher._fetch_filings_from_api(search_query)

    @pytest.mark.asyncio
    async def test_fetch_network_error(
        self, mock_sqlalchemy_engine, mock_cache, mock_settings
    ):
        """Test network error handling."""
        # Set up session mock to raise ClientError when post is called
        mock_session = MockClientSession(side_effect=ClientError())

        with patch("aiohttp.ClientSession", return_value=mock_session):
            fetcher = EDGARFetcher(api_key="test_key")
            search_query = {"query": "ticker:(AAPL)", "from": "0", "size": 1}

            with pytest.raises(DataFetchError, match="Network error:"):
                await fetcher._fetch_filings_from_api(search_query)

    @pytest.mark.asyncio
    async def test_fetch_json_decode_error(
        self, mock_sqlalchemy_engine, mock_cache, mock_settings
    ):
        """Test JSON decode error handling."""
        # Create a mock response that raises JSONDecodeError when json() is called
        mock_response = MockResponse({})
        mock_response.json = AsyncMock(
            side_effect=json.JSONDecodeError("Invalid JSON", "", 0)
        )
        mock_session = MockClientSession(response=mock_response)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            fetcher = EDGARFetcher(api_key="test_key")
            search_query = {"query": "ticker:(AAPL)", "from": "0", "size": 1}

            with pytest.raises(DataFetchError, match="Invalid response format:"):
                await fetcher._fetch_filings_from_api(search_query)

    @pytest.mark.asyncio
    async def test_fetch_cached_result(
        self, mock_sqlalchemy_engine, mock_cache, mock_settings
    ):
        """Test fetching from cache."""
        filing = SECFiling(
            accessionNo="0001193125-23-012345",
            formType="10-K",
            filing_date="2023-02-15",
            company_name="Apple Inc.",
            ticker="AAPL",
            cik="0000320193",
            documentURL="https://www.sec.gov/Archives/edgar/data/320193/000032019323000010/aapl-20221231.htm",
            chunk_type=ChunkType.TEXT,
        )
        mock_cache.get.return_value = {"value": pickle.dumps([filing])}

        fetcher = EDGARFetcher(api_key="test_key")
        result = await fetcher.fetch(identifier=["AAPL"])

        assert len(result) == 1
        assert result[0].ticker == "AAPL"
        assert result[0].formType == "10-K"
        # No API call should be made
        mock_cache.write.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_and_cache(
        self, mock_sqlalchemy_engine, mock_cache, mock_settings
    ):
        """Test fetching from API and storing in cache."""
        mock_cache.get.return_value = None

        response_data = {
            "filings": [
                {
                    "accessionNo": "0001193125-23-012345",
                    "formType": "10-K",
                    "cik": "0000320193",
                    "companyName": "Apple Inc.",
                    "filedAt": "2023-02-15",
                    "ticker": "AAPL",
                    "documentFormatFiles": [
                        {
                            "type": "10-K",
                            "documentUrl": "https://www.sec.gov/Archives/edgar/data/320193/000032019323000010/aapl-20221231.htm",
                        }
                    ],
                }
            ]
        }

        # Create our response and session mocks
        mock_response = MockResponse(response_data)
        mock_session = MockClientSession(response=mock_response)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            fetcher = EDGARFetcher(api_key="test_key")
            result = await fetcher.fetch(identifier=["AAPL"])

            assert len(result) == 1
            assert result[0].ticker == "AAPL"
            # Cache should be written
            mock_cache.write.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_validation_error(
        self, mock_sqlalchemy_engine, mock_cache, mock_settings
    ):
        """Test validation error in fetch params."""
        fetcher = EDGARFetcher(api_key="test_key")

        with pytest.raises(AcquisitionValidationError):
            await fetcher.fetch(identifier=[])


class TestSECFiling:
    """Tests for the SECFiling class."""

    def test_parsing_filing_date(self):
        """Test that filing_date is parsed correctly from string."""
        filing = SECFiling(
            accessionNo="0001193125-23-012345",
            formType="10-K",
            filedAt="2023-02-15",
            company_name="Apple Inc.",
            ticker="AAPL",
            cik="0000320193",
            documentURL="https://www.sec.gov/Archives/edgar/data/320193/000032019323000010/aapl-20221231.htm",
            chunk_type=ChunkType.TEXT,
        )

        assert isinstance(filing.filing_date, datetime)
        assert filing.filing_date.year == 2023
        assert filing.filing_date.month == 2
        assert filing.filing_date.day == 15

    def test_get_uris(self):
        """Test getting URIs from a filing."""
        filing = SECFiling(
            accessionNo="0001193125-23-012345",
            formType="10-K",
            filing_date="2023-02-15",
            company_name="Apple Inc.",
            ticker="AAPL",
            cik="0000320193",
            documentURL="https://www.sec.gov/Archives/edgar/data/320193/000032019323000010/aapl-20221231.htm",
            chunk_type=ChunkType.TEXT,
        )

        uris = filing.get_uris()
        assert len(uris) == 1
        assert (
            uris[0]
            == "https://www.sec.gov/Archives/edgar/data/320193/000032019323000010/aapl-20221231.htm"
        )

    def test_get_uris_empty(self):
        """Test getting URIs when documentURL is not provided."""
        filing = SECFiling(
            accessionNo="0001193125-23-012345",
            formType="10-K",
            filing_date="2023-02-15",
            company_name="Apple Inc.",
            ticker="AAPL",
            cik="0000320193",
            documentURL=None,
            chunk_type=ChunkType.TEXT,
        )

        uris = filing.get_uris()
        assert len(uris) == 0

    def test_get_metadata(self):
        """Test getting metadata from a filing."""
        filing = SECFiling(
            accessionNo="0001193125-23-012345",
            formType="10-K",
            filing_date="2023-02-15",
            company_name="Apple Inc.",
            ticker="AAPL",
            cik="0000320193",
            documentURL="https://www.sec.gov/Archives/edgar/data/320193/000032019323000010/aapl-20221231.htm",
            chunk_type=ChunkType.TEXT,
        )

        metadata = filing.get_metadata()
        assert metadata["accessionNo"] == "0001193125-23-012345"
        assert metadata["formType"] == "10-K"
        assert metadata["company_name"] == "Apple Inc."
        assert metadata["ticker"] == "AAPL"
        assert metadata["cik"] == "0000320193"
        assert (
            metadata["documentURL"]
            == "https://www.sec.gov/Archives/edgar/data/320193/000032019323000010/aapl-20221231.htm"
        )

    def test_convert_to_sec_gov_url_already_sec_gov(self):
        """Test converting an already SEC.gov URL."""
        filing = SECFiling(
            accessionNo="0001193125-23-012345",
            formType="10-K",
            filing_date="2023-02-15",
            company_name="Apple Inc.",
            ticker="AAPL",
            cik="0000320193",
            documentURL="https://www.sec.gov/Archives/edgar/data/320193/000032019323000010/aapl-20221231.htm",
            chunk_type=ChunkType.TEXT,
        )

        url = filing._convert_to_sec_gov_url(filing.documentURL)
        assert (
            url
            == "https://www.sec.gov/Archives/edgar/data/320193/000032019323000010/aapl-20221231.htm"
        )

    def test_convert_to_sec_gov_url_with_ix_param(self):
        """Test converting an SEC.gov URL with inline XBRL parameter."""
        filing = SECFiling(
            accessionNo="0001193125-23-012345",
            formType="10-K",
            filing_date="2023-02-15",
            company_name="Apple Inc.",
            ticker="AAPL",
            cik="0000320193",
            documentURL="https://www.sec.gov/ix?doc=/Archives/edgar/data/320193/000032019323000010/aapl-20221231.htm",
            chunk_type=ChunkType.TEXT,
        )

        url = filing._convert_to_sec_gov_url(filing.documentURL)
        assert (
            url
            == "https://www.sec.gov/Archives/edgar/data/320193/000032019323000010/aapl-20221231.htm"
        )

    def test_convert_to_sec_gov_url_from_sec_api(self):
        """Test converting a SEC-API URL to SEC.gov URL."""
        filing = SECFiling(
            accessionNo="0001193125-23-012345",
            formType="10-K",
            filing_date="2023-02-15",
            company_name="Apple Inc.",
            ticker="AAPL",
            cik="0000320193",
            documentURL="https://api.sec-api.io/Archives/edgar/data/320193/000032019323000010/aapl-20221231.htm",
            chunk_type=ChunkType.TEXT,
        )

        url = filing._convert_to_sec_gov_url(filing.documentURL)
        assert (
            url
            == "https://www.sec.gov/Archives/edgar/data/320193/000032019323000010/aapl-20221231.htm"
        )

    def test_convert_to_sec_gov_url_unknown_format(self):
        """Test converting an unknown URL format."""
        filing = SECFiling(
            accessionNo="0001193125-23-012345",
            formType="10-K",
            filing_date="2023-02-15",
            company_name="Apple Inc.",
            ticker="AAPL",
            cik="0000320193",
            documentURL="https://example.com/some/path",
            chunk_type=ChunkType.TEXT,
        )

        url = filing._convert_to_sec_gov_url(filing.documentURL)
        assert url == "https://example.com/some/path"  # Returns the original URL
