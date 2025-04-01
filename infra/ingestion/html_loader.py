import infra.core as core
import infra.acquisition as acquisition
from pydantic import List
from langchain_core.documents import Document

class HTMLLoader(core.IDocumentLoader):
    """
    A simple HTML loader that loads HTML documents from a given path (URL or local path)
    and scrapes all HTML information from the target including recursively following HTML
    links.

    """
    def __init__(self):
        pass

    def load(self, sources: List[acquisition.AcquisitionOutput]) -> List[Document]:
        """
        Loads the HTML document from the specified sources and returns a list of
        Document objects.
        """
        with open(self.path, 'r', encoding='utf-8') as file:
            content = file.read()
        return [content]