import asyncio
import sys
import logging
from infra.parsers.pdf_parser import PDFParser
# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    import os
    from pathlib import Path

    async def run_sec_parser():
        """Run the SECParser on a cached HTML file."""
        logger.info("Running SECParser on cached HTML file")
        
        try:
            # Initialize the parser
            parser = PDFParser()
            # Use the first HTML file foundcache/sec_filings/GOOG/GOOG_8-K_0001193125-24-157498.pdf
            html_file = "cache/sec_filings/GOOG/GOOG_10-K_0001652044-17-000008.pdf"
            logger.info(f"Using PDF file: {html_file}")
            
            # Parse the HTML file
            documents = parser.parse(html_file)

            # Write documents to a file in the cache directory
            if documents:
                logger.info(f"Successfully parsed {len(documents)} documents from {html_file}")
                # Create a cache directory for parsed documents if it doesn't exist
                cache_dir = Path("cache/parsed_documents")
                cache_dir.mkdir(parents=True, exist_ok=True)
                
                # Generate output filename based on the input file
                input_file = Path(html_file)
                output_filename = f"{input_file.stem}_parsed.md"
                output_path = cache_dir / output_filename
                
                logger.info(f"Writing parsed documents to {output_path}")
                
                # Write all documents to the file
                with open(output_path, "w", encoding="utf-8") as f:
                    for i, doc in enumerate(documents):
                        # f.write(f"--- DOCUMENT {i+1} ---\n")
                        # f.write(f"METADATA: {doc.metadata}\n\n")
                        f.write(f"{doc.page_content}\n\n")
                        # f.write("-" * 80 + "\n\n")
                
                logger.info(f"Successfully wrote {len(documents)} documents to {output_path}")
            
            
            return 0
        except Exception as e:
            logger.error(f"Error running SECParser: {e}")
            return 1
    
    # Run the parser
    sys.exit(asyncio.run(run_sec_parser()))