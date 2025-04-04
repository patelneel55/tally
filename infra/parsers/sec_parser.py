from typing import List, Dict, Any
import warnings
from langchain_core.documents import Document
import sec_parser as sp
from infra.core.interfaces import IParser


class SECParser(IParser):
    """
    Parser for SEC filings using the sec-parser library.
    """

    def __init__(self):
        """Initialize the SEC parser."""
        pass

    def parse(self, docs: List[Document], output_format: IParser.SUPPORTED_FORMATS = "markdown") -> List[Document]:
        parser = sp.Edgar10QParser()
        parsed_docs = []
        for doc in docs:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="Invalid section type for")
                elements: list = parser.parse(doc.page_content)
            bldr = sp.TreeBuilder()
            tree = bldr.build(elements)
            converted_docs = self._convert_tree_to_documents(tree, doc.metadata)
            parsed_docs.extend(converted_docs)
        return parsed_docs
    
    def _convert_tree_to_documents(self, tree: sp.SemanticTree, metadata: dict) -> List[Document]:
        """
        Convert the parsed tree into a list of Document objects.
        
        Args:
            tree: Parsed tree from sec-parser
            metadata: Metadata to be included in the Document objects
            
        Returns:
            List of Document objects with structured SEC filing data
        """
        # Implement the conversion logic here
        return [Document(page_content=sp.render(tree), metadata=metadata)]
