import asyncio
import logging
import re
import time
import warnings
from typing import Any, Dict, List, Tuple

import sec_parser as sp
from langchain_core.documents import Document
from sqlalchemy import UnicodeText
from sqlalchemy.orm import mapped_column

from infra.core.interfaces import ILLMProvider, IParser, ISplitter
from infra.databases.cache import Cache
from infra.databases.engine import sqlalchemy_engine
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

    _TABLE_SUMMARY_TABLE_NAME = "markdown_tables_summary"

    def __init__(self, llm_provider: ILLMProvider = None):
        """Initialize the SEC splitter."""
        self.llm_provider = llm_provider
        self.table_summarizer = (
            TableSummarizerTool(llm_provider) if llm_provider else None
        )

        self._md_table_cache = Cache(
            engine=sqlalchemy_engine,
            table_name=self._TABLE_SUMMARY_TABLE_NAME,
            column_mapping={
                "markdown": mapped_column(UnicodeText, nullable=False),
                "summary": mapped_column(UnicodeText, nullable=True),
            },
        )

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
        table_tasks = await self._collect_table_tasks(tree)
        if table_tasks:
            logger.debug(f"Processing {len(table_tasks)} tables in parallel")
            start_time = time.time()
            await asyncio.gather(*table_tasks)
            end_time = time.time()
            logger.debug(
                f"Processed {len(table_tasks)} tables in {end_time - start_time:.2f} seconds"
            )

        documents = []
        for root_node in tree:
            # Process each root node and its children
            chunks = await self._flatten_tree(root_node, metadata)
            documents.extend(chunks)
        return documents

    async def _collect_table_tasks(self, tree: sp.SemanticTree):
        """
        Collect all tables in the tree to parse as asyncio tasks.
        """
        table_tasks = []
        for node in tree.nodes:
            if isinstance(node.semantic_element, sp.TableElement):
                table_tasks.append(
                    asyncio.create_task(
                        self._process_table(node.semantic_element.table_to_markdown())
                    )
                )
        return table_tasks

    def _cleanup_table_format(self, markdown_lines: str) -> str:
        """
        Clean up table formatting in the text.
        """
        # Add header separators for tables if doesn't exist
        markdown_lines = markdown_lines.split("\n")
        if len(markdown_lines) > 1 and not re.match(r"^\|[-| ]+\|$", markdown_lines[1]):
            num_cols = markdown_lines[0].count("|") - 1  # exclude outer bars
            separator_line = "|" + "|".join([" --- "] * num_cols) + "|"
            markdown_lines.insert(1, separator_line)
        return "\n".join(markdown_lines).strip()

    async def _process_table(self, markdown_lines: str) -> None:
        """
        Clean up table formatting in the text.

        Args:
            text: Text containing table formatting
        """
        markdown_table = self._cleanup_table_format(markdown_lines)
        table_hash = self._md_table_cache.generate_id(markdown_table)

        cache_entry = self._md_table_cache.get(table_hash)
        if cache_entry and cache_entry["summary"]:
            return

        if self.table_summarizer is None:
            logger.warning(
                f"LLM Provider not specified, proceeding without LLM. Using raw table."
            )
            self._md_table_cache.write(table_hash, markdown=markdown_table)
            return

        summarizer_input = TableSummarizerInput(table=markdown_table)
        table_summary = await self.table_summarizer.run(**summarizer_input.model_dump())
        self._md_table_cache.write(
            table_hash, markdown=markdown_table, summary=table_summary
        )
        return

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
                    markdown_table = self._cleanup_table_format(
                        node.semantic_element.table_to_markdown()
                    )

                    # Retrieve either the table or the summary from the cache
                    table_hash = self._md_table_cache.generate_id(markdown_table)
                    cache_entry = self._md_table_cache.get(table_hash)
                    if cache_entry and cache_entry["summary"]:
                        content = cache_entry["summary"]
                    else:
                        content = markdown_table
                    doc_metadata.update(
                        {
                            "db_table_key": table_hash,
                            "db_table_name": self._TABLE_SUMMARY_TABLE_NAME,
                        }
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
