import logging
import re
import warnings
from typing import Any, Dict, List

import sec_parser as sp
from langchain_core.documents import Document
from langchain_core.language_models import BaseLanguageModel

from infra.core.interfaces import ILLMProvider, IParser, ISplitter
from infra.preprocessing.models import SemanticDocument
from infra.tools.table_summarizer import TableSummarizerInput, TableSummarizerTool

logger = logging.getLogger(__name__)


class SECParser(IParser):
    """
    Parser for SEC filings using the sec-parser library.
    """

    def __init__(self):
        """Initialize the SEC parser."""
        pass

    def parse(
        self,
        docs: List[Document],
        output_format: IParser.SUPPORTED_FORMATS = "markdown",
    ) -> List[Document]:
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

    def __init__(self, llm_provider: ILLMProvider = None):
        """Initialize the SEC splitter."""
        self.llm_provider = llm_provider
        self.table_summarizer = TableSummarizerTool(llm_provider) if llm_provider else None

    async def split_documents(self, documents: List[Document]) -> List[Document]:
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
                split_docs = await self._convert_tree_to_documents(
                    doc.as_tree(), doc.metadata
                )
                split_documents.extend(split_docs)
            else:
                raise TypeError(
                    f"Document must be of type SemanticDocument, but got {type(doc).__name__}"
                )
        return split_documents

    async def _convert_tree_to_documents(
        self, tree: sp.SemanticTree, metadata: dict
    ) -> List[Document]:
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
            chunks = await self._flatten_tree(root_node, metadata)
            documents.extend(chunks)
        return documents

    async def _table_formatting(self, markdown_lines: str) -> str:
        """
        Clean up table formatting in the text.

        Args:
            text: Text containing table formatting

        Returns:
            Cleaned text
        """
        # Add header separators for tables if doesn't exist
        markdown_lines = markdown_lines.split("\n")
        if len(markdown_lines) > 1 and not re.match(r"^\|[-| ]+\|$", markdown_lines[1]):
            num_cols = markdown_lines[0].count("|") - 1  # exclude outer bars
            separator_line = "|" + "|".join([" --- "] * num_cols) + "|"
            markdown_lines.insert(1, separator_line)
        markdown_table = "\n".join(markdown_lines)

        if self.table_summarizer is None:
            logger.warning(
                f"LLM Provider not specified, proceeding without LLM. Using raw table."
            )
            return markdown_table

        # TODO(neelp): Append table metadata which will be responsible for retrieving the actual table
        # content from the document
        summarizer_input = TableSummarizerInput(table=markdown_table)
        table_summary = await self.table_summarizer.run(**summarizer_input.model_dump())
        return table_summary

    async def _flatten_tree(
        self, node: sp.TreeNode, metadata, path=None, level=1
    ) -> List[Document]:
        is_leaf_node = len(node.children) == 0
        path = path or []

        chunks = []
        if is_leaf_node:
            if node.semantic_element.contains_words():
                # If it's a leaf node, create a Document object
                doc_metadata = metadata.copy()
                doc_metadata.update(
                    {
                        "type": node.semantic_element.__class__.__name__,
                        "level": level,
                        "path": " > ".join(path),
                        "parent": (
                            node.parent.semantic_element.text.strip()
                            if node.parent
                            else ""
                        ),
                    }
                )
                if isinstance(node.semantic_element, sp.TableElement):
                    content = await self._table_formatting(
                        node.semantic_element.table_to_markdown()
                    )
                else:
                    content = node.semantic_element.text.strip()

                chunk_text = f"You are in section: {' > '.join(path)}. This is a {node.semantic_element.__class__.__name__}.\n\n{content}"
                chunks.append(Document(page_content=chunk_text, metadata=doc_metadata))
        else:
            path = path + [node.semantic_element.text.strip()]

        for child in node.children:
            # Recursively flatten the child nodes
            chunks.extend(
                await self._flatten_tree(child, metadata, path=path, level=level + 1)
            )
        return chunks
