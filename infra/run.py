import asyncio
import sys
import logging
from infra.acquisition.sec_fetcher import EDGARFetcher, FilingType, DataFormat
from infra.parsers.pdf_parser import PDFParser
from infra.ingestion.html_loader import HTMLLoader
from infra.acquisition.sec_fetcher import SECFiling
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import Pool

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize the fetcher
fetcher = EDGARFetcher()
parser = PDFParser()

def parse_filing(filing):
    logger.info(f"Filing: {filing.formType} - {filing.filing_date} - {filing.accessionNo}")
    documents = parser.parse(filing.pdf_path)
    logger.info(f"Parsed {len(documents)} documents from {filing.pdf_path}")
    parser.write_file(documents, f"cache/parsed_documents/{ticker}_{doc_type}_{filing.accessionNo}.md")

if __name__ == "__main__":
    async def infra_run():
        ticker = "GS"
        doc_type = FilingType.ANNUAL_REPORT
        logger.info("Fetching {ticker} {doc_type} filings")

        "https://www.sec.gov/ix?doc=/Archives/edgar/data/886982/000119312525012226/d910407d8k.htm"

        source = SECF
        loader = HTMLLoader()
        
        # try:
            
        #     # Fetch 8-K filings for Apple
        #     filings = await fetcher.fetch(
        #         identifier=ticker,
        #         filing_type=FilingType.CURRENT_REPORT,
        #         data_format=DataFormat.PDF
        #     )

        #     logger.info(f"Found {len(filings)} {doc_type} filings for {ticker}: {filings}")
        #     # with Pool(processes=5) as pool:
        #     #     try:
        #     #         pool.map(parse_filing, filings)
        #     #     except Exception as e:
        #     #         logger.error(f"Error processing filing: {e}")

        #     return None
        # except Exception as e:
        #     logger.error(f"Error fetching {ticker} {doc_type} filings: {e}")
        #     raise

    # Run
    sys.exit(asyncio.run(infra_run()))