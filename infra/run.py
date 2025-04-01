import asyncio
import sys
import logging
from infra.acquisition.sec_fetcher import EDGARFetcher, FilingType, DataFormat
from infra.parsers.pdf_parser import PDFParser
from concurrent.futures import ThreadPoolExecutor, as_completed

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    async def infra_run():
        ticker = "GS"
        doc_type = FilingType.ANNUAL_REPORT
        logger.info("Fetching {ticker} {doc_type} filings")
        
        try:
            # Initialize the fetcher
            fetcher = EDGARFetcher()
            parser = PDFParser()
            
            # Fetch 8-K filings for Apple
            filings = await fetcher.fetch(
                identifier=ticker,
                filing_type=FilingType.ANNUAL_REPORT,
                data_format=DataFormat.PDF
            )
            
            # Print the results
            def parse_filing(filing):
                logger.info(f"Filing: {filing.formType} - {filing.filing_date} - {filing.accessionNo}")
                documents = parser.parse(filing.pdf_path)
                logger.info(f"Parsed {len(documents)} documents from {filing.pdf_path}")
                parser.write_file(documents, f"cache/parsed_documents/{ticker}_{doc_type}_{filing.accessionNo}.md")

            logger.info(f"Found {len(filings)} {doc_type} filings for {ticker}")
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(parse_filing, filing) for filing in filings]
                for future in as_completed(futures):
                    try:
                        future.result()  # Propagate any exceptions
                    except Exception as e:
                        logger.error(f"Error processing filing: {e}")

            return None
        except Exception as e:
            logger.error(f"Error fetching {ticker} {doc_type} filings: {e}")
            raise

    # Run
    sys.exit(asyncio.run(infra_run()))