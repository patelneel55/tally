"""
Test the PDF Parser implementation.

This module tests the PDF parser functionality to ensure it correctly parses
PDF files into LangChain Documents.
"""

import os
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from langchain_core.documents import Document

from infra.parsers.pdf_parser import PDFParser

# Sample test data
SAMPLE_PDF_PATH = "test/resources/sample.pdf"
NON_EXISTENT_PDF_PATH = "test/resources/non_existent.pdf"


class TestPDFParser(unittest.TestCase):
    """Test cases for the PDFParser class."""

    def setUp(self):
        """Set up test cases."""
        self.parser = PDFParser()

    def test_init(self):
        """Test PDFParser initialization."""
        self.assertEqual(self.parser.chunk_size, 1000)
        self.assertEqual(self.parser.chunk_overlap, 200)

        # Test custom chunk size and overlap
        custom_parser = PDFParser(chunk_size=500, chunk_overlap=100)
        self.assertEqual(custom_parser.chunk_size, 500)
        self.assertEqual(custom_parser.chunk_overlap, 100)

    def test_extract_file_metadata(self):
        """Test file metadata extraction."""
        # Create a mock file path
        with patch("os.path.exists", return_value=True):
            with patch("pathlib.Path") as mock_path:
                # Configure the mock
                mock_path_instance = MagicMock()
                mock_path_instance.name = "test.pdf"
                mock_path_instance.absolute.return_value = "/absolute/path/test.pdf"
                mock_path_instance.stat.return_value.st_size = 1024
                mock_path_instance.stat.return_value.st_mtime = 1646092800  # 2022-03-01
                mock_path.return_value = mock_path_instance

                # Test the method
                metadata = self.parser._extract_file_metadata("data/test.pdf")

                # Verify the results
                self.assertEqual(metadata["file_name"], "data/test.pdf")
                self.assertEqual(metadata["file_type"], "pdf")
                self.assertEqual(metadata["file_path"], "data/test.pdf")
                self.assertEqual(metadata["file_size"], 1024)
                self.assertEqual(metadata["last_modified"], 1646092800)

    @patch("pymupdf4llm.to_markdown")
    def test_parse_as_markdown(self, mock_to_markdown):
        """Test parsing PDF to markdown."""
        # Set up mock return value
        mock_to_markdown.return_value = [
            {
                "metadata": {
                    "page_number": 1,
                    "page_count": 2,
                    "file_path": "data/test.pdf"
                },
                "text": "# Page 1\n\nSample text content",
                "tables": [{"bbox": (0, 0, 100, 100), "row_count": 3, "col_count": 4}],
                "images": [{"name": "image1", "bbox": (0, 0, 50, 50)}],
                "graphics": [{"bbox": (0, 0, 30, 30)}]
            },
            {
                "metadata": {
                    "page_number": 2,
                    "page_count": 2,
                    "file_path": "data/test.pdf"
                },
                "text": "# Page 2\n\nMore sample content",
                "tables": [],
                "images": [],
                "graphics": []
            }
        ]

        # Run the method
        file_metadata = {"source": "data/test.pdf", "file_name": "test.pdf"}
        documents = self.parser._parse_as_markdown("data/test.pdf", file_metadata)

        # Verify results
        self.assertEqual(len(documents), 2)
        self.assertEqual(documents[0].page_content, "# Page 1\n\nSample text content")
        self.assertEqual(documents[0].metadata["source"], "data/test.pdf")
        self.assertEqual(documents[0].metadata["tables"], 1)
        self.assertEqual(documents[0].metadata["images"], 1)
        self.assertEqual(documents[0].metadata["graphics"], 1)
        self.assertEqual(documents[1].page_content, "# Page 2\n\nMore sample content")

    @patch("os.path.exists", return_value=False)
    def test_parse_file_not_found(self, mock_exists):
        """Test parsing a non-existent file raises FileNotFoundError."""
        with self.assertRaises(FileNotFoundError) as context:
            self.parser.parse(NON_EXISTENT_PDF_PATH)
        self.assertIn("PDF file not found", str(context.exception))

    @patch("os.path.exists", return_value=True)
    @patch("pymupdf4llm.to_markdown")
    def test_parse_exception_handling(self, mock_to_markdown, mock_exists):
        """Test exception handling during parsing."""
        # Configure the mock to raise an exception
        mock_to_markdown.side_effect = Exception("Test exception")

        # Test the method
        with self.assertRaises(Exception) as context:
            self.parser.parse("test.pdf")
        self.assertIn("Failed to parse PDF file", str(context.exception))

    @patch("os.path.exists", return_value=True)
    @patch.object(PDFParser, "_parse_as_markdown")
    @patch.object(PDFParser, "_extract_file_metadata")
    def test_parse_full_flow(self, mock_extract_metadata, mock_parse_as_markdown, mock_exists):
        """Test the full parsing flow."""
        # Configure the mocks
        mock_extract_metadata.return_value = {"source": "test.pdf", "file_name": "test.pdf"}
        mock_parse_as_markdown.return_value = [
            Document(page_content="Test content 1", metadata={"page": 1}),
            Document(page_content="Test content 2", metadata={"page": 2})
        ]

        # Run the parse method
        result = self.parser.parse("test.pdf")

        # Verify the results
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].page_content, "Test content 1")
        self.assertEqual(result[1].page_content, "Test content 2")
        
        # Verify the methods were called with the right arguments
        mock_extract_metadata.assert_called_once_with("test.pdf")
        mock_parse_as_markdown.assert_called_once_with("test.pdf", {"source": "test.pdf", "file_name": "test.pdf"})


if __name__ == "__main__":
    unittest.main() 