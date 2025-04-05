from typing import List, Dict, Any
import warnings
from langchain_core.documents import Document
import sec_parser as sp
from infra.core.interfaces import IParser, ISplitter
from infra.preprocessing.models import SemanticDocument
import re

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
            # Convert the parsed tree into a list of SemanticDocument
            parsed_docs.append(SemanticDocument(tree, doc.metadata))
        return parsed_docs


class SECSplitter(ISplitter):
    """
    Splitter for SEC filings using the sec-parser library.
    """
    def __init__(self):
        """Initialize the SEC splitter."""
        pass

    def split_documents(self, documents: List[Document]) -> List[Document]:
        """
        Splits the documents into sections based on the SemanticTree structure.
        Args:
            documents (List[Document]): List of documents to split (type SemanticTree).
        Returns:
            List[Document]: List of split documents.
        """

        split_documents = []
        for doc in documents:
            if isinstance(doc, SemanticDocument):
                # Convert SemanticDocument to Document
                split_docs = self._convert_tree_to_documents(doc.as_tree(), doc.metadata)
                split_documents.extend(split_docs)
            else:
                raise TypeError(f"Document must be of type SemanticDocument, but got {type(doc).__name__}")
        return split_documents

    def _convert_tree_to_documents(self, tree: sp.SemanticTree, metadata: dict) -> List[Document]:
        """
        Convert the parsed tree into a list of Document objects.
        
        Args:
            tree: Parsed tree from sec-parser
            metadata: Metadata to be included in the Document objects
            
        Returns:
            List of Document objects with structured SEC filing data
        """
        # tree.nodes
        # Implement the conversion logic here
        documents = []
        for root_node in tree:
            # Process each root node and its children
            chunks = self._flatten_tree(root_node, metadata)
            documents.extend(chunks)
        return documents

    def _cleanup_table_formatting(self, markdown_lines: str) -> str:
        """
        Clean up table formatting in the text.
        
        Args:
            text: Text containing table formatting
            
        Returns:
            Cleaned text
        """
        # Implement the cleanup logic here
        markdown_lines = markdown_lines.split("\n")
        if len(markdown_lines) > 1 and not re.match(r"^\|[-| ]+\|$", markdown_lines[1]):
            num_cols = markdown_lines[0].count("|") - 1  # exclude outer bars
            separator_line = "|" + "|".join([" --- "]*num_cols) + "|"
            markdown_lines.insert(1, separator_line)
        return "\n".join(markdown_lines)

    def _flatten_tree(self, node: sp.TreeNode, metadata, path=None, level=1) -> List[Document]:
        is_leaf_node = len(node.children) == 0
        path = path or []

        chunks = []
        if is_leaf_node:
            if node.semantic_element.contains_words():
                # If it's a leaf node, create a Document object
                doc_metadata = metadata.copy()
                doc_metadata.update({ 
                    "type": node.semantic_element.__class__.__name__,
                    "level": level,
                    "path": ' > '.join(path),
                    "parent": node.parent.semantic_element.text.strip() if node.parent else "",
                })
                if isinstance(node.semantic_element, sp.TableElement):
                    content = self._cleanup_table_formatting(node.semantic_element.table_to_markdown())
                else:
                    content = node.semantic_element.text.strip()
                
                chunk_text = f"You are in section: {' > '.join(path)}. This is a {node.semantic_element.__class__.__name__}.\n\n{content}"
                chunks.append(Document(page_content=chunk_text, metadata=doc_metadata))
        else:
            path = path + [node.semantic_element.text.strip()]

        for child in node.children:
            # Recursively flatten the child nodes
            chunks.extend(self._flatten_tree(child, metadata, path=path, level=level + 1))
        return chunks