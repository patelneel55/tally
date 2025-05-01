from typing import Any, List, Type

from langchain.text_splitter import TextSplitter
from langchain_core.documents import Document

from infra.preprocessing.models import ISplitter


class LangChainTextSplitter(ISplitter):
    """
    Splits a document into smaller chunks based on the specified chunk size and overlap.
    """

    def __init__(self, splitter: Type[TextSplitter], **kwargs: Any):
        """
        Initialize the splitter with the specified chunk size and overlap.
        Args:
            splitter (Type[TextSplitter]): The text splitter class to use.
            **kwargs: Additional arguments for the text splitter.
        """
        self.splitter = splitter
        self.splitter_kwargs = kwargs

    async def split_documents(self, documents: List[Document]) -> List[Document]:
        """
        Splits the documents into smaller chunks based on the specified chunk size and overlap.
        Args:
            documents (List[Document]): List of documents to split.
        Returns:
            List[Document]: List of split documents.
        """
        splitter_instance = self.splitter(**self.splitter_kwargs)
        return splitter_instance.split_documents(documents)
