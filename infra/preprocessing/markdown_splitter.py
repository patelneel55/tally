from typing import Any, Dict, List, Literal, Optional, Union

from langchain.text_splitter import MarkdownTextSplitter
from langchain_core.documents import Document

from infra.core.interfaces import ISplitter

# from docling.document_converter import DocumentConverter


class MarkdownSplitter(ISplitter):
    """
    Splits a markdown file into sections based on the headings.
    """

    def __init__(self):
        pass

    def split_documents(self, documents: List[Document]) -> List[Document]:
        """
        Splits the documents into sections based on the headings.
        Args:
            documents (List[Document]): List of documents to split.
        Returns:
            List[Document]: List of split documents.
        """
        # converter = DocumentConverter()
        # result = converter.convert(file_path)
        # splitter = MarkdownTextSplitter()
        # return splitter.split_documents(documents)
        pass
