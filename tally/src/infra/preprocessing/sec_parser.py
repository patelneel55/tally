import asyncio
import json
import logging
import re
import uuid
import warnings
from pathlib import Path
from typing import List

import sec_parser as sp
from langchain_core.documents import Document
from sec_parser.processing_steps import SupplementaryTextClassifier
from sqlalchemy import JSON, DateTime, UnicodeText
from sqlalchemy.orm import mapped_column

from infra.acquisition.sec_fetcher import SECFiling
from infra.collections.models import BaseMetadata, ChunkType, HierarchyMetadata
from infra.databases.cache import Cache
from infra.databases.engine import get_sqlalchemy_engine
from infra.llm.models import ILLMProvider
from infra.pipelines.mem_walker import MemoryTreeNode
from infra.preprocessing.models import IParser
from infra.tools.summarizer import SummarizerInput, SummarizerTool


logger = logging.getLogger(__name__)


def write_content_to_file(content: str, filename: str) -> None:
    """
    Write the content to a file.

    Args:
        content (str): The content to write.
        filename (str): The name of the file to write to.
    """
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(filename, "w", encoding="utf-8") as file:
        file.write(content)


class SECParser(IParser):
    """
    Parser for SEC filings using the sec-parser library.
    """

    def __init__(self, llm_provider: ILLMProvider):
        """Initialize the SEC parser."""
        self.llm_provider = llm_provider
        self.summarizer = SummarizerTool(llm_provider)

        self.summary_cache = Cache(
            engine=get_sqlalchemy_engine(),
            table_name="sec_filing_summary",
            column_mapping={
                "ticker": mapped_column(UnicodeText, nullable=False),
                "filing_type": mapped_column(UnicodeText, nullable=False),
                "filing_date": mapped_column(DateTime(timezone=True), nullable=False),
                "original_text": mapped_column(UnicodeText, nullable=False),
                "summary": mapped_column(UnicodeText, nullable=False),
            },
        )
        self.hierarchy_cache = Cache(
            engine=get_sqlalchemy_engine(),
            table_name="sec_filing_hierarchy",
            column_mapping={
                "ticker": mapped_column(UnicodeText, nullable=False),
                "filing_type": mapped_column(UnicodeText, nullable=False),
                "filing_date": mapped_column(DateTime(timezone=True), nullable=False),
                "document_structure": mapped_column(JSON, nullable=False),
            },
        )

    def get_classifer_steps(self) -> list:
        steps = sp.Edgar10QParser().get_default_steps()
        return [
            step for step in steps if not isinstance(step, SupplementaryTextClassifier)
        ]

    async def _convert_tree_to_documents(
        self, tree: sp.SemanticTree, metadata: BaseMetadata
    ) -> List[Document]:
        """
        Convert the parsed tree into a list of Document objects.

        Args:
            tree: Parsed tree from sec-parser
            metadata: Metadata to be included in the Document objects

        Returns:
            List of Document objects with structured SEC filing data
        """
        metadata = SECFiling(**metadata.model_dump())
        metadata_hash = self.hierarchy_cache.generate_id(metadata.flatten_dict())
        hierarchy_entry = self.hierarchy_cache.get(metadata_hash)
        if not hierarchy_entry or not hierarchy_entry["document_structure"]:
            children_memories: List[MemoryTreeNode] = []
            for root_node in tree:
                # Process each root node and its children
                memory_tree = await self._create_document_structure(root_node, metadata)
                if memory_tree:
                    children_memories.append(memory_tree)

            if len(children_memories) == 1:
                root_tree_node = children_memories[0]
            else:
                mega_summaries = self._construct_summaries(children_memories, "")
                content_hash = self.summary_cache.generate_id(mega_summaries)
                cache_entry = self.summary_cache.get(content_hash)
                if not cache_entry or not cache_entry["summary"]:
                    summarizer_input = SummarizerInput(input=mega_summaries)
                    summary = await self.summarizer.execute(
                        **summarizer_input.model_dump()
                    )
                    self.summary_cache.write(
                        content_hash,
                        ticker=metadata.ticker,
                        filing_type=metadata.formType,
                        filing_date=metadata.filing_date,
                        original_text=mega_summaries,
                        summary=summary,
                    )
                else:
                    summary = cache_entry["summary"]

                node_id = str(uuid.uuid4())
                root_tree_node = MemoryTreeNode(
                    id=node_id,
                    summary=summary,
                    content="",
                    node_type=ChunkType.TEXT,
                    children=children_memories,
                )
            self.hierarchy_cache.write(
                metadata_hash,
                ticker=metadata.ticker,
                filing_type=metadata.formType,
                filing_date=metadata.filing_date,
                document_structure=root_tree_node.model_dump(),
            )
        else:
            root_tree_node = MemoryTreeNode.model_validate(
                hierarchy_entry["document_structure"]
            )
        write_content_to_file(
            json.dumps(root_tree_node.model_dump()), "cache/AAPL.json"
        )
        docs = self._create_docs_from_memory_tree(root_tree_node)
        return docs

    def _create_docs_from_memory_tree(
        self, memory_tree: MemoryTreeNode
    ) -> List[Document]:
        if not memory_tree:
            return []

        if len(memory_tree.children) == 0:
            # If it's a leaf node, create a Document object
            return [
                Document(
                    page_content=memory_tree.content,
                    metadata=memory_tree.metadata.flatten_dict(),
                )
            ]

        docs = []
        for child in memory_tree.children:
            child_docs = self._create_docs_from_memory_tree(child)
            docs.extend(child_docs)
        return docs

    async def _create_document_structure(
        self, node: sp.TreeNode, metadata: SECFiling
    ) -> MemoryTreeNode:
        if not node:
            return None

        child_tasks = [
            asyncio.create_task(self._create_document_structure(child, metadata))
            for child in node.children
        ]
        children_memories: List[MemoryTreeNode] = await asyncio.gather(*child_tasks)

        # If there's only one child, we can merge it with the parent node
        # to avoid unnecessary nesting in the memory tree
        # This is a simple heuristic and may need to be adjusted based on the actual structure
        # of the SEC filings.
        if len(node.children) == 1:
            child_memory = children_memories[0]
            child_memory.content = (
                node.semantic_element.text.strip() + "\n\n" + child_memory.content
            )
            return child_memory

        if isinstance(node.semantic_element, sp.TableElement):
            node_content = self._cleanup_table_format(
                node.semantic_element.table_to_markdown()
            ).strip()
            node_type = ChunkType.TABLE
        elif isinstance(
            node.semantic_element, sp.ImageElement
        ):  # TODO(neelp): Handle images when parsing SEC filings
            node_content = "[IMAGE]"
            node_type = ChunkType.IMAGE
        else:
            node_content = node.semantic_element.text.strip()
            node_type = ChunkType.TEXT

        # If it's a leaf node, generate summary of the text
        if len(node.children) == 0 and node.semantic_element.contains_words():
            content_hash = self.summary_cache.generate_id(node_content)
            cache_entry = self.summary_cache.get(content_hash)
            if not cache_entry or not cache_entry["summary"]:
                summarizer_input = SummarizerInput(
                    input=node_content,
                    custom_instructions="""
You are a precision-driven AI summarizer designed to process a single atomic section from an SEC filing.

Your task is to:
- Compress the content without losing factual detail
- Retain names, dollar amounts, and disclosed entities
- Preserve the tone (e.g., confident, hedged, vague)
- Reflect structure if the text is organized with bullets, lists, or subheaders
- Avoid interpreting meaning beyond what is stated

<rules>
- DO NOT omit financial figures, dates, named parties, or regulatory references
- DO NOT generalize (“some policies,” “various risks”) unless that language exists in the source
- If content is boilerplate or non-informative, note this explicitly
- If a table is embedded, hand off processing to a specialized table summarizer (see: <table_instructions> tag)
</rules>

<format>
Your output should be in bullet-point format. Each bullet should preserve a single fact, clause, or line of disclosure. Use nested bullets only when needed to reflect structure in the original text.
</format>
""",
                )
                summary = await self.summarizer.execute(**summarizer_input.model_dump())
                self.summary_cache.write(
                    content_hash,
                    ticker=metadata.ticker,
                    filing_type=metadata.formType,
                    filing_date=metadata.filing_date,
                    original_text=node_content,
                    summary=summary,
                )
            else:
                summary = cache_entry["summary"]
            node_id = str(uuid.uuid4())
            # metadata = metadata.model_copy()
            metadata.chunk_type = node_type
            metadata.hierarchy = HierarchyMetadata(
                node_id=node_id,
            )
            current_node = MemoryTreeNode(
                id=node_id,
                summary=summary,
                content=node_content,
                node_type=node_type,
                metadata=metadata,
            )
            return current_node

        mega_summaries = self._construct_summaries(children_memories, node_content)
        content_hash = self.summary_cache.generate_id(mega_summaries)
        cache_entry = self.summary_cache.get(content_hash)
        if not cache_entry or not cache_entry["summary"]:
            summarizer_input = SummarizerInput(
                input=mega_summaries,
            )
            summary = await self.summarizer.execute(**summarizer_input.model_dump())
            self.summary_cache.write(
                content_hash,
                original_text=mega_summaries,
                summary=summary,
                ticker=metadata.ticker,
                filing_type=metadata.formType,
                filing_date=metadata.filing_date,
            )
        else:
            summary = cache_entry["summary"]

        node_id = str(uuid.uuid4())
        current_node = MemoryTreeNode(
            id=node_id,
            summary=summary,
            content=node_content,
            node_type=node_type,
            metadata=metadata,
            children=children_memories,
        )
        return current_node

    def _construct_summaries(
        self, children_memories: List[MemoryTreeNode], node_content: str
    ) -> str:
        """
        Construct summaries for the children nodes and combine them with the parent node content.
        """
        mega_summaries = []
        for child in children_memories:
            if child.summary:
                mega_summaries.append(child.summary)
            else:
                mega_summaries.append(child.content)
        return node_content + "\n\n" + "\n---------------\n".join(mega_summaries)

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

    async def parse(self, docs: List[Document]) -> List[Document]:
        parser = sp.Edgar10QParser(self.get_classifer_steps)
        parsed_docs = []
        for doc in docs:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="Invalid section type for")
                elements: list = parser.parse(doc.page_content)
            bldr = sp.TreeBuilder()
            tree = bldr.build(elements)
            parsed_docs.extend(
                await self._convert_tree_to_documents(tree, SECFiling(**doc.metadata))
            )
        return parsed_docs
