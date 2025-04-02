import asyncio
import sys
import logging
from infra.acquisition.sec_fetcher import EDGARFetcher, FilingType, DataFormat
from infra.parsers.pdf_parser import PDFParser
from infra.parsers.html_parser import HTMLParser
from infra.ingestion.web_loader import WebLoader
from infra.acquisition.sec_fetcher import SECFiling
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import Pool
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize the fetcher
fetcher = EDGARFetcher()
parser = HTMLParser()
loader = WebLoader()

def parse_filing(filing):
    logger.info(f"Filing: {filing.formType} - {filing.filing_date} - {filing.accessionNo}")
    documents = parser.parse(filing.pdf_path)
    logger.info(f"Parsed {len(documents)} documents from {filing.pdf_path}")
    parser.write_file(documents, f"cache/parsed_documents/{ticker}_{doc_type}_{filing.accessionNo}.md")

if __name__ == "__main__":
    async def infra_run():
        ticker = "GS"
        doc_type = FilingType.ANNUAL_REPORT
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


            # Write HTML to files
            for doc in docs:
                url_hash = hash(doc.metadata.get('source', 'unknown'))
                output_path = f"cache/parsed_documents/{ticker}_{doc_type.value}_{url_hash}.html"
                # Create directory if it doesn't exist
                output_dir = os.path.dirname(output_path)
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
                
                # Write all documents to the file
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(f"{doc.page_content}\n\n")
                
                logger.info(f"Document {doc.metadata.get('source', "unknown")} written to {output_path}")


            documents = parser.parse(docs)
            # Write markdown to files
            for doc in documents:
                url_hash = hash(doc.metadata.get('source', 'unknown'))
                output_path = f"cache/parsed_documents/{ticker}_{doc_type.value}_{url_hash}.md"
                # Create directory if it doesn't exist
                output_dir = os.path.dirname(output_path)
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
                
                # Write all documents to the file
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(f"{doc.page_content}\n\n")
                logger.info(f"Document {doc.metadata.get('source', "unknown")} written to {output_path}")

            return None
        except Exception as e:
            logger.error(f"Error fetching {ticker} {doc_type} filings: {e}")
            raise

    # Run
    sys.exit(asyncio.run(infra_run()))