"""
SEC Filing Preprocessor

This module provides tools for preprocessing SEC filings, including converting PDFs to text,
cleaning up text formatting, and extracting structured information.

What this file does:
1. Extracts text from PDF files
2. Provides page-by-page text extraction with page numbers
3. Helps prepare SEC filing content for further analysis
"""

from PyPDF2 import PdfReader
from typing import List, Dict


def extract_text_from_pdf(pdf_path: str) -> List[Dict]:
    """
    Extracts text from each page of a PDF using PyPDF2.

    Args:
        pdf_path (str): Path to the PDF file

    Returns:
        List[Dict]: List of dicts with keys 'page' and 'text'
    """
    reader = PdfReader(pdf_path)
    pages = []

    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            pages.append({
                "page": i + 1,
                "text": text.strip()
            })

    return pages 