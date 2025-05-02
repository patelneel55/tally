from abc import ABC, abstractmethod
from typing import List

from langchain_core.documents import Document

from infra.acquisition.models import AcquisitionOutput


class IDocumentLoader(ABC):
    """
    Interface for loading data from a specific URI into LangChain
    Document objects.
    """

    @abstractmethod
    async def load(self, sources: List[AcquisitionOutput]) -> List[Document]:
        """
        Load documents from the given sources. This method should be
        implemented by subclasses to define how documents are loaded
        from the sources.

        Args:
            sources (List[AcquisitionOutput]): List of sources to load documents from.

        Returns:
            List[Document]: List of loaded documents.
        """
        pass
