#!/usr/bin/env python
"""
PDF Parser Demo Script

This script demonstrates how to use the PDF parser to parse a PDF file.
It takes a PDF file path as input and outputs the parsed content.

Usage:
    python run_pdf_parser.py <pdf_file_path>

Example:
    python run_pdf_parser.py test/resources/sample.pdf
"""

import sys
import os
from pathlib import Path
import logging

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from infra.parsers.pdf_parser import PDFParser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def main():
    """Run the PDF parser on a sample PDF file."""
    if len(sys.argv) < 2:
        print("Please provide a PDF file path")
        print(f"Usage: python {sys.argv[0]} <pdf_file_path>")
        sys.exit(1)

    pdf_file_path = sys.argv[1]
    
    if not os.path.exists(pdf_file_path):
        print(f"Error: File not found: {pdf_file_path}")
        sys.exit(1)
        
    logger.info(f"Parsing PDF file: {pdf_file_path}")
    
    try:
        # Create the PDF parser
        parser = PDFParser()
        
        # Parse the PDF file
        documents = parser.parse(pdf_file_path)
        
        # Print information about the parsed documents
        logger.info(f"Successfully parsed PDF into {len(documents)} documents")
        
        # Print a summary of each document
        for i, doc in enumerate(documents):
            print(f"\n--- Document {i+1} ---")
            print(f"Page content length: {len(doc.page_content)} characters")
            print(f"Metadata: {', '.join(f'{k}: {v}' for k, v in doc.metadata.items() if k != 'text')}")
            
            # Print a preview of the content (first 200 characters)
            preview = doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
            print(f"\nContent preview:\n{preview}")
            
        logger.info(f"PDF parsing complete for file: {pdf_file_path}")
        
    except Exception as e:
        logger.error(f"Error parsing PDF file: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 