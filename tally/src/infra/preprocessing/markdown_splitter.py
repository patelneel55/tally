from typing import Any
from typing import Dict
from typing import List
from typing import Literal
from typing import Optional
from typing import Union

from langchain.text_splitter import MarkdownTextSplitter
from langchain_core.documents import Document

from infra.preprocessing.models import ISplitter


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
        splitter = MarkdownTextSplitter()
        return splitter.split_documents(documents)
