import asyncio
import sys
import logging
from infra.acquisition.sec_fetcher import EDGARFetcher, FilingType, DataFormat
from infra.parsers.pdf_parser import PDFParser
from infra.ingestion.web_loader import WebLoader
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
loader = WebLoader()

def parse_filing(filing):
    logger.info(f"Filing: {filing.formType} - {filing.filing_date} - {filing.accessionNo}")
    documents = parser.parse(filing.pdf_path)
    logger.info(f"Parsed {len(documents)} documents from {filing.pdf_path}")
    parser.write_file(documents, f"cache/parsed_documents/{ticker}_{doc_type}_{filing.accessionNo}.md")

if __name__ == "__main__":
    async def infra_run():
        ticker = "GS"
        doc_type = FilingType.CURRENT_REPORT
        logger.info(f"Fetching {ticker} {doc_type.value} filings")
        
        try:
            
            # Fetch 8-K filings for Apple
            filings = await fetcher.fetch(
                identifier=ticker,
                filing_type=doc_type,
                data_format=DataFormat.HTML
            )
            logger.info(f"Found {len(filings)} {doc_type.value} filings for {ticker}")
            
            docs = await loader.load(filings, crawl_strategy="all")
            print(f"Number of documents: {len(docs)}")
            for doc in docs:
                print(f"Metadata: {doc.metadata}\nSize: {len(doc.page_content)}\n\n")
            # with Pool(processes=5) as pool:
            #     try:
            #         pool.map(parse_filing, filings)
            #     except Exception as e:
            #         logger.error(f"Error processing filing: {e}")

            return None
        except Exception as e:
            logger.error(f"Error fetching {ticker} {doc_type} filings: {e}")
            raise

    # Run
    sys.exit(asyncio.run(infra_run()))