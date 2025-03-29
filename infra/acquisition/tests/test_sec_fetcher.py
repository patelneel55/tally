"""
Unit tests for the SEC Filing Fetcher module.

These tests verify the functionality of the SEC fetcher,
including file caching, API interactions, and data processing.
"""
import unittest
import os
import json
import logging
import shutil
from datetime import date, datetime
from unittest import mock
from pathlib import Path
import asyncio

# Configure logging for test visibility
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('acquisition_sec_fetcher_tests.log', mode='w')
    ]
)
logger = logging.getLogger(__name__)

# Import the module to test
from infra.acquisition.sec_fetcher import (
    EDGARFetcher, 
    SECFiling, 
    FilingRequest, 
    FilingType, 
    DataFormat,
    DataFetchError,
    ValidationError
)


class TestSECFetcher(unittest.TestCase):
    """Test suite for the SEC Filing Fetcher."""
    
    @classmethod
    def setUpClass(cls):
        """Set up the test environment once before all tests."""
        logger.info("Setting up test environment")
        # Set test API key
        # Read the API key from .env file
        from dotenv import load_dotenv
        load_dotenv()
        os.environ["SEC_API_KEY"] = os.getenv("SEC_API_KEY", "test_api_key")
        
        # Create test cache directory
        cls.test_cache_dir = Path("test_cache/sec_filings")
        cls.test_cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Create test fixtures
        cls.sample_filing_data = {
            "accessionNo": "0001437749-20-002201",
            "formType": "10-Q",
            "filedAt": "2020-02-10T19:28:05-05:00",
            "companyName": "Genasys Inc.",
            "ticker": "GNSS",
            "cik": "924383",
            "documentFormatFiles": [
                {
                    "sequence": "1",
                    "description": "FORM 10-Q",
                    "documentUrl": "https://www.sec.gov/Archives/edgar/data/924383/000143774920002201/lrad20191231_10q.htm",
                    "type": "10-Q",
                    "size": "938119"
                },
                {
                    "sequence": "2",
                    "description": "EXHIBIT 31.1",
                    "documentUrl": "https://www.sec.gov/Archives/edgar/data/924383/000143774920002201/ex_171266.htm",
                    "type": "EX-31.1",
                    "size": "13563"
                },
            ],
            "linkToTxt": "https://www.sec.gov/Archives/edgar/data/924383/0001437749-20-002201.txt"
        }
        
    @classmethod
    def tearDownClass(cls):
        """Clean up the test environment after all tests."""
        logger.info("Cleaning up test environment")
        # Remove test cache directory
        if cls.test_cache_dir.exists():
            shutil.rmtree(cls.test_cache_dir.parent)
    
    def setUp(self):
        """Set up resources before each test."""
        logger.info("Setting up test case")
        # Create a mock fetcher with test cache directory
        self.fetcher = EDGARFetcher()
        self.fetcher.cache_dir = self.test_cache_dir
        
        # Mock the API key
        self.fetcher.api_key = "test_api_key"
        
    def tearDown(self):
        """Clean up resources after each test."""
        logger.info("Tearing down test case")
        # Clean up the cache directory after each test
        for item in self.test_cache_dir.glob("**/*"):
            if item.is_file():
                item.unlink()
    
    def test_init(self):
        """Test the initialization of the EDGARFetcher."""
        logger.info("Testing fetcher initialization")
        
        # Test with explicit API key
        fetcher = EDGARFetcher(api_key="explicit_key")
        self.assertEqual(fetcher.api_key, "explicit_key")
        
        # Test with environment variable
        os.environ["SEC_API_KEY"] = "env_key"
        fetcher = EDGARFetcher()
        self.assertEqual(fetcher.api_key, "env_key")
        
        # Test cache directory creation
        self.assertTrue(fetcher.cache_dir.exists())
    
    def test_filing_request_validation(self):
        """Test validation of filing requests."""
        logger.info("Testing FilingRequest validation")
        
        # Valid CIK
        request = FilingRequest(identifier="1234567")
        self.assertEqual(request.identifier, "1234567")
        
        # Valid ticker
        request = FilingRequest(identifier="AAPL")
        self.assertEqual(request.identifier, "AAPL")
        
        # Invalid CIK (too long)
        with self.assertRaises(ValueError):
            FilingRequest(identifier="12345678901")
        
        # Invalid ticker (too long)
        with self.assertRaises(ValueError):
            FilingRequest(identifier="TOOLONG")
    
    def test_build_search_query(self):
        """Test building the search query for the SEC API."""
        logger.info("Testing search query builder")
        
        # Test with CIK
        request = FilingRequest(
            identifier="1234567",
            filing_type=FilingType.ANNUAL_REPORT,
            date=date(2021, 12, 31)
        )
        query = self.fetcher._build_search_query(request)
        
        self.assertIn("cik:1234567", query["query"])
        self.assertIn('formType:"10-K"', query["query"])
        self.assertIn('filedAt:[2021-12-31 TO 2021-12-31T23:59:59]', query["query"])
        
        # Test with ticker
        request = FilingRequest(
            identifier="AAPL",
            filing_type=FilingType.QUARTERLY_REPORT
        )
        query = self.fetcher._build_search_query(request)
        
        self.assertIn("ticker:AAPL", query["query"])
        self.assertIn('formType:"10-Q"', query["query"])
        
    def test_convert_api_results_to_filings(self):
        """Test converting API results to SECFiling objects."""
        logger.info("Testing API result conversion")
        
        filings_data = [self.sample_filing_data]
        filings = self.fetcher._convert_api_results_to_filings(filings_data)
        
        self.assertEqual(len(filings), 1)
        self.assertEqual(filings[0].accessionNo, "0001437749-20-002201")
        self.assertEqual(filings[0].formType, "10-Q")
        self.assertEqual(filings[0].ticker, "GNSS")
        self.assertEqual(filings[0].documentURL, "https://www.sec.gov/Archives/edgar/data/924383/000143774920002201/lrad20191231_10q.htm")
    
    def test_convert_to_sec_gov_url(self):
        """Test converting API URLs to SEC.gov format."""
        logger.info("Testing URL conversion")
        
        # Test with SEC.gov URL
        url = "https://www.sec.gov/Archives/edgar/data/1234567/000119312521123456/d123456d10k.htm"
        result = self.fetcher._convert_to_sec_gov_url(url)
        self.assertEqual(result, url)
        
        # Test with SEC API URL
        url = "https://sec-api.io/Archives/edgar/data/1234567/000119312521123456/d123456d10k.htm"
        expected = "https://www.sec.gov/Archives/edgar/data/1234567/000119312521123456/d123456d10k.htm"
        result = self.fetcher._convert_to_sec_gov_url(url)
        self.assertEqual(result, expected)
        
        # Test with invalid URL
        url = "https://example.com/some/path"
        result = self.fetcher._convert_to_sec_gov_url(url)
        self.assertIsNone(result)
    
    def test_get_cache_path(self):
        """Test generating cache file paths."""
        logger.info("Testing cache path generation")
        
        filing = SECFiling(
            accessionNo="0001193125-21-123456",
            formType="10-K",
            filedAt="2021-12-31T00:00:00Z",
            company_name="Test Company Inc.",
            ticker="TEST",
            cik="0001234567"
        )
        
        cache_path = self.fetcher._get_cache_path(filing)
        
        self.assertEqual(cache_path.name, "TEST_10-K_0001193125-21-123456.pdf")
        self.assertTrue("TEST" in str(cache_path))
    
    def test_get_html_cache_path(self):
        """Test generating HTML cache file paths."""
        logger.info("Testing HTML cache path generation")
        
        filing = SECFiling(
            accessionNo="0001193125-21-123456",
            formType="10-K",
            filedAt="2021-12-31T00:00:00Z",
            company_name="Test Company Inc.",
            ticker="TEST",
            cik="0001234567"
        )
        
        cache_path = self.fetcher._get_html_cache_path(filing)
        
        self.assertEqual(cache_path.name, "TEST_10-K_0001193125-21-123456.html")
        self.assertTrue("html" in str(cache_path))
    
    def test_filter_filings_by_date(self):
        """Test filtering filings by date."""
        logger.info("Testing filing date filtering")
        
        filings = [
            SECFiling(
                accessionNo="0001193125-21-123456",
                formType="10-K",
                filedAt="2021-12-31T00:00:00Z",
                company_name="Test Company Inc.",
                ticker="TEST",
                cik="0001234567"
            ),
            SECFiling(
                accessionNo="0001193125-21-654321",
                formType="10-Q",
                filedAt="2021-09-30T00:00:00Z",
                company_name="Test Company Inc.",
                ticker="TEST",
                cik="0001234567"
            )
        ]
        
        # Test filtering for the first filing
        filtered = self.fetcher._filter_filings_by_date(filings, date(2021, 12, 31))
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].formType, "10-K")
        
        # Test filtering for the second filing
        filtered = self.fetcher._filter_filings_by_date(filings, date(2021, 9, 30))
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].formType, "10-Q")
        
        # Test filtering for a date with no filings
        filtered = self.fetcher._filter_filings_by_date(filings, date(2021, 10, 1))
        self.assertEqual(len(filtered), 0)
    
    @mock.patch('aiohttp.ClientSession.post')
    async def test_fetch_filings_from_api(self, mock_post):
        """Test fetching filings from the SEC API."""
        logger.info("Testing API fetching")
        
        # Create mock response
        mock_response = mock.AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {"filings": [self.sample_filing_data]}
        mock_post.return_value.__aenter__.return_value = mock_response
        
        # Create search query
        search_query = {
            "query": "ticker:TEST AND formType:\"10-K\"",
            "from": "0",
            "size": "100",
            "sort": [{"filedAt": {"order": "desc"}}]
        }
        
        # Fetch filings
        filings = await self.fetcher._fetch_filings_from_api(search_query)
        
        # Check results
        self.assertEqual(len(filings), 1)
        self.assertEqual(filings[0].ticker, "TEST")
        self.assertEqual(filings[0].formType, "10-K")
        
        # Verify API call
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"], search_query)
    
    @mock.patch('infra.acquisition.sec_fetcher.EDGARFetcher._make_http_request')
    async def test_download_filing_as_pdf(self, mock_request):
        """Test downloading a filing as PDF."""
        logger.info("Testing PDF downloading")
        
        # Create mock response
        mock_request.return_value = b"PDF data"
        
        # Download PDF
        pdf_data = await self.fetcher._download_filing_as_pdf("https://www.sec.gov/test.htm")
        
        # Check results
        self.assertEqual(pdf_data, b"PDF data")
        
        # Verify API call
        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        self.assertEqual(kwargs["url"], self.fetcher.pdf_generator_url)
        self.assertEqual(kwargs["binary"], True)
        self.assertEqual(kwargs["params"]["url"], "https://www.sec.gov/test.htm")
    
    @mock.patch('infra.acquisition.sec_fetcher.EDGARFetcher._make_http_request')
    async def test_fetch_filing_html(self, mock_request):
        """Test fetching a filing's HTML content."""
        logger.info("Testing HTML fetching")
        
        # Create mock response
        mock_request.return_value = "<html>HTML content</html>"
        
        # Fetch HTML
        html_data = await self.fetcher._fetch_filing_html("https://sec-api.io/test.txt")
        
        # Check results
        self.assertEqual(html_data, "<html>HTML content</html>")
        
        # Verify API call
        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        self.assertEqual(kwargs["url"], "https://sec-api.io/test.txt")
        self.assertEqual(kwargs["binary"], False)
    
    @mock.patch('pathlib.Path.exists')
    @mock.patch('infra.acquisition.sec_fetcher.EDGARFetcher._download_filing_as_pdf')
    @mock.patch('infra.acquisition.sec_fetcher.EDGARFetcher._convert_to_sec_gov_url')
    async def test_process_pdf_filings(self, mock_convert, mock_download, mock_exists):
        """Test processing PDF filings."""
        logger.info("Testing PDF filing processing")
        
        # Set up mocks
        mock_exists.return_value = False
        mock_convert.return_value = "https://www.sec.gov/test.htm"
        mock_download.return_value = b"PDF data"
        
        # Create test filings
        filings = [
            SECFiling(
                accessionNo="0001193125-21-123456",
                formType="10-K",
                filedAt="2021-12-31T00:00:00Z",
                company_name="Test Company Inc.",
                ticker="TEST",
                cik="0001234567",
                documentURL="https://sec-api.io/test.htm"
            )
        ]
        
        # Mock open and write to avoid actual file creation
        mock_open = mock.mock_open()
        with mock.patch('builtins.open', mock_open):
            # Process filings
            processed = await self.fetcher._process_pdf_filings(filings)
        
        # Check results
        self.assertEqual(len(processed), 1)
        
        # Verify API calls
        mock_convert.assert_called_once()
        mock_download.assert_called_once()
        mock_open.assert_called()  # Verify file was opened for writing
    
    @mock.patch('pathlib.Path.exists')
    @mock.patch('infra.acquisition.sec_fetcher.EDGARFetcher._fetch_filing_html')
    async def test_process_html_filings(self, mock_fetch, mock_exists):
        """Test processing HTML filings."""
        logger.info("Testing HTML filing processing")
        
        # Set up mocks
        mock_exists.return_value = False
        mock_fetch.return_value = "<html>HTML content</html>"
        
        # Create test filings
        filings = [
            SECFiling(
                accessionNo="0001193125-21-123456",
                formType="10-K",
                filedAt="2021-12-31T00:00:00Z",
                company_name="Test Company Inc.",
                ticker="TEST",
                cik="0001234567",
                textURL="https://sec-api.io/test.txt"
            )
        ]
        
        # Mock open and write to avoid actual file creation
        mock_open = mock.mock_open()
        with mock.patch('builtins.open', mock_open):
            # Process filings
            processed = await self.fetcher._process_html_filings(filings)
        
        # Check results
        self.assertEqual(len(processed), 1)
        
        # Verify API calls
        mock_fetch.assert_called_once()
        mock_open.assert_called()  # Verify file was opened for writing
    
    @mock.patch('infra.acquisition.sec_fetcher.EDGARFetcher._fetch_filings_from_api')
    @mock.patch('infra.acquisition.sec_fetcher.EDGARFetcher._process_pdf_filings')
    async def test_fetch_pdf(self, mock_process, mock_fetch_api):
        """Test fetching filings with PDF format."""
        logger.info("Testing fetch with PDF format")
        
        # Set up mocks
        mock_fetch_api.return_value = [
            SECFiling(
                accessionNo="0001193125-21-123456",
                formType="10-K",
                filedAt="2021-12-31T00:00:00Z",
                company_name="Test Company Inc.",
                ticker="TEST",
                cik="0001234567",
                documentURL="https://sec-api.io/test.htm"
            )
        ]
        mock_process.return_value = [
            SECFiling(
                accessionNo="0001193125-21-123456",
                formType="10-K",
                filedAt="2021-12-31T00:00:00Z",
                company_name="Test Company Inc.",
                ticker="TEST",
                cik="0001234567",
                documentURL="https://sec-api.io/test.htm",
                pdf_path="/path/to/pdf"
            )
        ]
        
        # Fetch filings
        filings = await self.fetcher.fetch("TEST", filing_type=FilingType.ANNUAL_REPORT, data_format=DataFormat.PDF)
        
        # Check results
        self.assertEqual(len(filings), 1)
        self.assertEqual(filings[0].pdf_path, "/path/to/pdf")
        
        # Verify API calls
        mock_fetch_api.assert_called_once()
        mock_process.assert_called_once()
    
    @mock.patch('infra.acquisition.sec_fetcher.EDGARFetcher._fetch_filings_from_api')
    @mock.patch('infra.acquisition.sec_fetcher.EDGARFetcher._process_html_filings')
    async def test_fetch_html(self, mock_process, mock_fetch_api):
        """Test fetching filings with HTML format."""
        logger.info("Testing fetch with HTML format")
        
        # Set up mocks
        mock_fetch_api.return_value = [
            SECFiling(
                accessionNo="0001193125-21-123456",
                formType="10-K",
                filedAt="2021-12-31T00:00:00Z",
                company_name="Test Company Inc.",
                ticker="TEST",
                cik="0001234567",
                textURL="https://sec-api.io/test.txt"
            )
        ]
        mock_process.return_value = [
            SECFiling(
                accessionNo="0001193125-21-123456",
                formType="10-K",
                filedAt="2021-12-31T00:00:00Z",
                company_name="Test Company Inc.",
                ticker="TEST",
                cik="0001234567",
                textURL="https://sec-api.io/test.txt",
                html_path="/path/to/html"
            )
        ]
        
        # Fetch filings
        filings = await self.fetcher.fetch("TEST", filing_type=FilingType.ANNUAL_REPORT, data_format=DataFormat.HTML)
        
        # Check results
        self.assertEqual(len(filings), 1)
        self.assertEqual(filings[0].html_path, "/path/to/html")
        
        # Verify API calls
        mock_fetch_api.assert_called_once()
        mock_process.assert_called_once()
    
    def test_save_filing_metadata(self):
        """Test saving filing metadata."""
        logger.info("Testing metadata saving")
        
        # Create test filing
        filing = SECFiling(
            accessionNo="0001193125-21-123456",
            formType="10-K",
            filedAt="2021-12-31T00:00:00Z",
            company_name="Test Company Inc.",
            ticker="TEST",
            cik="0001234567",
            documentURL="https://sec-api.io/test.htm",
            textURL="https://sec-api.io/test.txt"
        )
        
        # Create test file path
        file_path = Path("/path/to/file.pdf")
        
        # Mock JSON dump to avoid actual file creation
        with mock.patch('json.dump') as mock_dump:
            # Save metadata
            self.fetcher._save_filing_metadata(filing, file_path, 'pdf')
            
            # Verify JSON dump was called
            mock_dump.assert_called_once()
            
            # Verify metadata
            metadata = mock_dump.call_args[0][0]
            self.assertEqual(metadata["ticker"], "TEST")
            self.assertEqual(metadata["filing_type"], "10-K")
            self.assertEqual(metadata["pdf_path"], str(file_path))
            self.assertEqual(metadata["metadata_type"], "pdf")


# Run the tests if this script is run directly
if __name__ == '__main__':
    unittest.main() 