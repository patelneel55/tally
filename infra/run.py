import asyncio
import sys
import logging
from infra.acquisition.sec_fetcher import EDGARFetcher, FilingType, DataFormat
from infra.parsers.pdf_parser import PDFParser
from infra.parsers.html_parser import HTMLParser
from infra.parsers.sec_parser import SECParser
from infra.ingestion.web_loader import WebLoader
from infra.preprocessing.markdown_splitter import MarkdownSplitter
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

def save_docs(docs, step, ticker, doc_type: FilingType, ext):
    """
    Save the documents to a specified location.
    """
    for i, doc in enumerate(docs):
        url_hash = hash(doc.metadata.get('source', 'unknown'))
        output_path = f"cache/saved_documents/{step}/{ticker}_{doc_type.value}_{url_hash}_{i}.{ext}"
        # Create directory if it doesn't exist
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Write all documents to the file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"{doc.page_content}\n\n")
        
        logger.info(f"Document {doc.metadata.get('source', 'unknown')}, index {i} written to {output_path}")

if __name__ == "__main__":
    async def infra_run():
        ticker = "GS"
        doc_type = FilingType.CURRENT_REPORT
        logger.info(f"Fetching {ticker} {doc_type.value} filings")
        
        try:
            fetcher = EDGARFetcher()
            loader = WebLoader(crawl_strategy="all", max_crawl_depth=1)
            parser = SECParser()
            
            # Fetch filings
            filings = await fetcher.fetch(
                identifier=ticker,
                filing_type=doc_type,
                data_format=DataFormat.HTML
            )
            logger.info(f"Found {len(filings)} {doc_type.value} filings for {ticker}")
            
            docs = await loader.load(filings)
            print(f"Number of documents: {len(docs)}")
            save_docs(docs, "load", ticker, doc_type, "html")


            documents = parser.parse(docs)
            print(f"Number of documents: {len(documents)}")
            save_docs(documents, "parse", ticker, doc_type, "md")

            return None
        except Exception as e:
            logger.error(f"Error fetching {ticker} {doc_type} filings: {e}")
            raise

    # Run
    sys.exit(asyncio.run(infra_run()))