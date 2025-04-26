import logging
import os
import warnings
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List

# from docling.document_converter import DocumentConverter
import sec_parser as sp
from infra.core.interfaces import IParser
from langchain_community.document_transformers import MarkdownifyTransformer
from langchain_core.documents import Document


logger = logging.getLogger(__name__)


class HTMLParser(IParser):
    """
    Parser for SEC filing HTML files.

    This class implements the IParser interface to convert SEC filing HTML files
    into LangChain Documents. It uses the sec-parser library to extract structured
    data from SEC filings for AI analysis.
    """

    def __init__(self):
        """Initialize the HTML parser."""
        pass

    def parse(self, docs: List[Document]) -> List[Document]:
        """
        Parse an SEC filing HTML file into LangChain Documents.

        Args:
            file_path: Path to the HTML file

        Returns:
            List of LangChain Documents with structured SEC filing data

        Raises:
            FileNotFoundError: If the file does not exist
            ParserError: If the file cannot be parsed
        """
        md = MarkdownifyTransformer()
        new_docs = md.transform_documents(docs)
        return new_docs
