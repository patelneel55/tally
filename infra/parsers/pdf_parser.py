"""
PDF Parser
----------

This module provides functionality to parse PDF files into LangChain Documents
for processing in AI workflows. It leverages the pymupdf4llm library to extract
text and metadata from PDF files and converts them into a format suitable for
AI-powered analysis.

The parser handles PDF files and converts them to a standardized document format
with appropriate metadata.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from langchain_core.documents import Document
import pymupdf4llm
from infra.core.interfaces import IParser
# from docling.document_converter import DocumentConverter 

logger = logging.getLogger(__name__)

class PDFParser(IParser):
    """
    Parser for PDF files.
    
    This class implements the IParser interface to convert PDF files
    into LangChain Documents. It uses the pymupdf4llm library to extract
    text and metadata from PDF files for AI analysis.
    """
    
    def __init__(self, chunk_size: Optional[int] = 1000, chunk_overlap: Optional[int] = 200):
        pass
    
    def parse(self, file_path: str, output_format: IParser.SUPPORTED_FORMATS = "markdown") -> List[Document]:
        """
        Parse a PDF file into LangChain Documents.
        
        Args:
            file_path: Path to the PDF file
            output_format: Format to output the parsed data in (only markdown supported)
            
        Returns:
            List of LangChain Documents with structured PDF data
            
        Raises:
            FileNotFoundError: If the file does not exist
            Exception: If the file cannot be parsed
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        
        try:
            # Extract metadata from the file path
            metadata = self._extract_file_metadata(file_path)
            
            # Use pymupdf4llm to parse the PDF as markdown (only format supported for now)
            documents = self._parse_as_markdown(file_path, metadata)
            
            return documents
        
        except Exception as e:
            logger.error(f"Error parsing PDF file {file_path}: {str(e)}")
            raise Exception(f"Failed to parse PDF file: {str(e)}")
    
    def _extract_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Extract basic metadata from the file.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Dictionary containing basic file metadata
        """
        path_obj = Path(file_path)
        
        metadata = {
            "source": file_path,
            "file_name": path_obj.name,
            "file_type": "pdf",
            "file_path": str(path_obj.absolute()),
            "file_size": path_obj.stat().st_size,
            "last_modified": path_obj.stat().st_mtime,
        }
        
        return metadata

    # def _parse_as_markdown_docling(self, file_path: str, metadata: Dict[str, Any]) -> List[Document]:
    #     """
    #     Parse PDF to markdown-formatted
    #     documents using DocLing.
    #     """
    #     converter = DocumentConverter()
    #     result = converter.convert(file_path)
    #     doc = Document(
    #         page_content=result.document.export_to_markdown(),
    #         metadata={
    #             "source": file_path,
    #             "file_name": os.path.basename(file_path),
    #             "file_type": "pdf",
    #             "file_path": str(Path(file_path).absolute()),
    #             "file_size": os.path.getsize(file_path),
    #             "last_modified": os.path.getmtime(file_path),
    #         },
    #     )
    #     return [doc]
    
    def _parse_as_markdown(self, file_path: str, metadata: Dict[str, Any]) -> List[Document]:
        """
        Parse PDF to markdown-formatted documents.
        
        Args:
            file_path: Path to the PDF file
            metadata: Dictionary containing file metadata
            
        Returns:
            List of LangChain Documents with markdown content
        """
        # Use pymupdf4llm.to_markdown to convert PDF to markdown with page chunking
        # This returns a list of dictionaries, one per page
        output = pymupdf4llm.to_markdown(
            file_path, 
            page_chunks=True,             # Return a list of dictionaries, one per page
            write_images=False,            # Extract and save images
            table_strategy="lines_strict",       # Use line detection for tables
            show_progress=False            # Show progress during processing
        )
        
        # Create a Document for each page
        documents = []
        for page in output:
            # Get page content and metadata
            page_content = page.get("text", "")
            page_metadata = page.get("metadata", {})
            
            # Merge with our file metadata
            page_metadata.update(metadata)
            
            # Update page_metadata with additional information using dictionary comprehension
            page_metadata.update({
                key: (len(page.get(key)) if isinstance(page.get(key), list) else page.get(key))
                for key in ["tables", "images", "graphics", "toc_items"]
                if page.get(key)
            })
            
            # Create Document object and add to results
            documents.append(Document(
                page_content=page_content,
                metadata=page_metadata
            ))
        
        return documents
    
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