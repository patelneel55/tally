"""
HTML Parser
----------

This module provides functionality to parse HTML files into LangChain Documents
for processing in AI workflows. It leverages the sec-parser library to extract
structured data from SEC filings and converts them into a format suitable for
AI-powered analysis.

The parser handles SEC filings in HTML format and converts them to a
standardized document format with appropriate metadata.
"""

import os
import logging
from typing import List, Dict, Any
from pathlib import Path
from langchain_core.documents import Document
from infra.core.interfaces import IParser
from infra.parsers.html_to_md.converter import convert_html_to_markdown
from langchain_community.document_transformers import MarkdownifyTransformer

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
    
    def parse(self, docs: List[Document], output_format: IParser.SUPPORTED_FORMATS = "markdown") -> List[Document]:
        """
        Parse an SEC filing HTML file into LangChain Documents.
        
        Args:
            file_path: Path to the HTML file
            output_format: Format to output the parsed data in
            
        Returns:
            List of LangChain Documents with structured SEC filing data
            
        Raises:
            FileNotFoundError: If the file does not exist
            ParserError: If the file cannot be parsed
        """
        md = MarkdownifyTransformer()
        new_docs = md.transform_documents(docs)
        return new_docs

    def write_file(self, documents: List[Document], output_path: str) -> None:
        """
        Write the page content of all documents to a file.
        
        Args:
            documents: List of Document objects to write
            output_path: Path to the output file
            
        Returns:
            None
        """
        try:
            logger.info(f"Writing {len(documents)} documents to {output_path}")
            
            # Create directory if it doesn't exist
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            
            # Write all documents to the file
            with open(output_path, "w", encoding="utf-8") as f:
                for doc in documents:
                    f.write(f"{doc.page_content}\n\n")
            
            logger.info(f"Successfully wrote {len(documents)} documents to {output_path}")
        except Exception as e:
            logger.error(f"Error writing documents to file: {e}")
            raise
#         if not os.path.exists(file_path):
#             raise FileNotFoundError(f"HTML file not found: {file_path}")
        
#         try:
#             # Use sec_parser to parse the HTML filing
#             filing = sp.Filing.from_html_file(file_path)
            
#             # Extract metadata from the filing
#             metadata = self._extract_filing_metadata(filing, file_path)
            
#             # Process the SEC filing based on requested format
#             if output_format == "markdown":
#                 documents = self._convert_to_markdown_documents(filing, metadata)
#             else:  # json
#                 documents = self._convert_to_json_documents(filing, metadata)
            
#             return documents
        
#         except Exception as e:
#             logger.error(f"Error parsing HTML file {file_path}: {str(e)}")
#             raise Exception(f"Failed to parse HTML file: {str(e)}")
    
#     def _extract_filing_metadata(self, filing: sp.Filing, file_path: str) -> Dict[str, Any]:
#         """
#         Extract metadata from sec-parser Filing object.
        
#         Args:
#             filing: The sec-parser Filing object
#             file_path: Path to the HTML file
            
#         Returns:
#             Dictionary containing metadata from the filing
#         """
#         path_obj = Path(file_path)
        
#         # Get basic filing information
#         metadata = {
#             "source": file_path,
#             "file_name": path_obj.name,
#             "file_type": "html",
#             "file_path": str(path_obj.absolute()),
#             "file_size": path_obj.stat().st_size,
#             "last_modified": path_obj.stat().st_mtime,
#         }
        
#         # Add SEC filing specific metadata
#         try:
#             if hasattr(filing, 'company_info') and filing.company_info:
#                 metadata.update({
#                     "company_name": filing.company_info.get('company_name', ''),
#                     "ticker": filing.company_info.get('ticker', ''),
#                     "cik": filing.company_info.get('cik', ''),
#                 })
            
#             if hasattr(filing, 'filing_info') and filing.filing_info:
#                 metadata.update({
#                     "filing_type": filing.filing_info.get('form_type', ''),
#                     "filing_date": filing.filing_info.get('filing_date', ''),
#                     "period_end_date": filing.filing_info.get('period_of_report', ''),
#                 })
#         except Exception as e:
#             logger.warning(f"Error extracting detailed metadata: {e}")
        
#         return metadata
    
#     def _convert_to_markdown_documents(self, filing: sp.Filing, metadata: Dict[str, Any]) -> List[Document]:
#         """
#         Convert SEC filing to markdown documents.
        
#         Args:
#             filing: The sec-parser Filing object
#             metadata: Dictionary containing metadata
            
#         Returns:
#             List of LangChain Documents with markdown content
#         """
#         documents = []
        
#         # Create a document for each section in the filing
#         try:
#             # Get the text content based on filing type
#             if hasattr(filing, 'get_markdown') and callable(filing.get_markdown):
#                 # If there's a method to get markdown directly
#                 content = filing.get_markdown()
#                 documents.append(Document(page_content=content, metadata=metadata))
#             elif hasattr(filing, 'get_items'):
#                 # For filings organized by items (like 10-K, 10-Q)
#                 items = filing.get_items()
                
#                 for key, text in items.items():
#                     if text:
#                         section_metadata = metadata.copy()
#                         section_metadata["section"] = key
                        
#                         # Format as markdown with clear section headers
#                         markdown_content = f"# {key}\n\n{text}"
#                         documents.append(Document(page_content=markdown_content, metadata=section_metadata))
#             elif hasattr(filing, 'to_dict'):
#                 # Generic approach - convert to dict and format as markdown
#                 filing_dict = filing.to_dict()
                
#                 for section, content in filing_dict.items():
#                     if content and isinstance(content, str):
#                         section_metadata = metadata.copy()
#                         section_metadata["section"] = section
                        
#                         # Format as markdown
#                         markdown_content = f"# {section}\n\n{content}"
#                         documents.append(Document(page_content=markdown_content, metadata=section_metadata))
#             else:
#                 # Fallback - use string representation of filing
#                 content = str(filing)
#                 documents.append(Document(page_content=content, metadata=metadata))
        
#         except Exception as e:
#             logger.warning(f"Error converting to markdown: {e}, using string representation")
#             # Fallback - use string representation
#             content = str(filing)
#             documents.append(Document(page_content=content, metadata=metadata))
        
#         return documents
    
#     def _convert_to_json_documents(self, filing: sp.Filing, metadata: Dict[str, Any]) -> List[Document]:
#         """
#         Convert SEC filing to JSON structured documents.
        
#         Args:
#             filing: The sec-parser Filing object
#             metadata: Dictionary containing metadata
            
#         Returns:
#             List of LangChain Documents with JSON structured content
#         """
#         try:
#             # Convert filing to dictionary format
#             if hasattr(filing, 'to_dict') and callable(filing.to_dict):
#                 filing_dict = filing.to_dict()
#             else:
#                 # Fallback: construct a simple dict with available attributes
#                 filing_dict = {
#                     "text": str(filing),
#                     "metadata": metadata
#                 }
            
#             # Create a document with the structured content
#             content = str(filing_dict)  # Convert dict to string for storage
#             return [Document(page_content=content, metadata=metadata)]
            
#         except Exception as e:
#             logger.warning(f"Error converting to JSON: {e}, using string representation")
#             # Fallback - use string representation
#             content = str(filing)
#             return [Document(page_content=content, metadata=metadata)]
