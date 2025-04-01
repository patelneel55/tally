"""
Parser Implementations
---------------------

This module exports all available parser implementations for converting
different file formats into LangChain Documents.
"""

# from infra.parsers.html_parser import HTMLParser
# from infra.parsers.sec_parser import SECParser
from infra.parsers.pdf_parser import PDFParser

__all__ = [ "PDFParser"]
