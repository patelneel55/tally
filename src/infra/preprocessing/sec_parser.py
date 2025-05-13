import asyncio
import json
import logging
import re
import uuid
import warnings
from pathlib import Path
from typing import List, Tuple

import sec_parser as sp
from langchain_core.documents import Document
from sec_parser.processing_steps import SupplementaryTextClassifier
from sqlalchemy import JSON, DateTime, UnicodeText
from sqlalchemy.orm import mapped_column

from infra.acquisition.sec_fetcher import SECFiling
from infra.collections.models import ChunkType, HierarchyMetadata
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

    _INT_NODE_INSTRUCTIONS = """
You are a financial analyst creating a higher-level summary from multiple section summaries of an SEC filing.

Each child section has already been summarized. Your task is to **build a sparse but high-fidelity overview** by:
- Identifying **common themes or trends across children**
- Extracting **material or standout disclosures**
- Referring to child nodes for detailed points, rather than repeating them

### Guidelines:
- Do not summarize every child
- Do not merge or paraphrase summaries without attribution
- **If a child has no standout content, skip it**
- Use section names or IDs to trace insight origin (e.g., "See Section 1B for forward-looking commentary")

### Format:
- Group findings under thematic headings
- Include 1-3 bullets from relevant children
- Use pointers instead of repeating full content (e.g., “See Child: 1B for litigation details”)

Do not add new information. Do not speculate.
Only return a structured summary.

<children_info>
{children_info}
</children_info>
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
                # "status": mapped_column(UnicodeText, nullable=False),
                "document_structure": mapped_column(JSON, nullable=True),
            },
        )

    def get_classifer_steps(self) -> list:
        steps = sp.Edgar10QParser().get_default_steps()
        return [
            step for step in steps if not isinstance(step, SupplementaryTextClassifier)
        ]

    async def _get_summary_from_cache(
        self, content: str, metadata: SECFiling, custom_instructions: str = ""
    ) -> str:
        content_hash = self.summary_cache.generate_id(content)
        cache_entry = self.summary_cache.get(content_hash)
        if not cache_entry or not cache_entry["summary"]:
            summarizer_input = SummarizerInput(
                input=content, custom_instructions=custom_instructions
            )
            summary = await self.summarizer.execute(**summarizer_input.model_dump())
            self.summary_cache.write(
                content_hash,
                ticker=metadata.ticker,
                filing_type=metadata.formType,
                filing_date=metadata.filing_date,
                original_text=content,
                summary=summary,
            )
            return summary
        return cache_entry["summary"]

    async def _index_hierarchy(
        self, tree: sp.SemanticTree, metadata: SECFiling
    ) -> MemoryTreeNode:
        children_memories: List[MemoryTreeNode] = []
        total_content: List[str] = []
        for root_node in tree:
            # Process each root node and its children
            memory_tree, raw_content = await self._create_document_structure(
                root_node, metadata
            )
            children_memories.append(memory_tree)
            total_content.append(raw_content)

        if len(children_memories) == 1:
            return children_memories[0]

        document_summaries = self._construct_summaries(children_memories, "")
        summary = await self._get_summary_from_cache(
            document_summaries,
            metadata,
            custom_instructions=self._INT_NODE_INSTRUCTIONS.format(
                children_info=document_summaries
            ),
        )

        return MemoryTreeNode(
            id=str(uuid.uuid4()),
            summary=summary,
            content="",
            node_type=ChunkType.TEXT,
            children=children_memories,
        )

    async def _convert_tree_to_documents(
        self, tree: sp.SemanticTree, metadata: SECFiling
    ) -> List[Document]:
        """
        Convert the parsed tree into a list of Document objects.

        Args:
            tree: Parsed tree from sec-parser
            metadata: Metadata to be included in the Document objects

        Returns:
            List of Document objects with structured SEC filing data
        """
        metadata_hash = self.hierarchy_cache.generate_id(metadata.flatten_dict())
        hierarchy_entry = self.hierarchy_cache.get(metadata_hash)

        # If the hierarchy cache exists, retrieve cache instead of re-indexing
        # the document hierarchy
        if not hierarchy_entry or not hierarchy_entry["document_structure"]:
            # self.hierarchy_cache.write(
            #     metadata_hash,
            #     ticker=metadata.ticker,
            #     filing_type=metadata.formType,
            #     filing_date=metadata.filing_date,
            #     # status="in-progress",
            # )
            root_tree_node = await self._index_hierarchy(tree, metadata)
            self.hierarchy_cache.write(
                metadata_hash,
                ticker=metadata.ticker,
                filing_type=metadata.formType,
                filing_date=metadata.filing_date,
                # status="complete",
                document_structure=root_tree_node.model_dump(),
            )
        else:
            root_tree_node = MemoryTreeNode.model_validate(
                hierarchy_entry["document_structure"]
            )
        write_content_to_file(
            json.dumps(root_tree_node.model_dump()), f"cache/{metadata.ticker}.json"
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
    ) -> Tuple[MemoryTreeNode, str]:
        if not node:
            return None, ""

        children_memories: List[MemoryTreeNode] = []
        total_content: List[str] = []

        # Create a list of coroutine objects and gather results
        tasks = [
            self._create_document_structure(child, metadata) for child in node.children
        ]
        results = await asyncio.gather(*tasks)
        for child_mem, child_content in results:
            children_memories.append(child_mem)
            total_content.append(child_content)

        # If there's only one child, we can merge it with the parent node
        # to avoid unnecessary nesting in the memory tree
        # This is a simple heuristic and may need to be adjusted based on the actual structure
        # of the SEC filings.
        if len(node.children) == 1:
            child_memory = children_memories[0]
            child_memory.content = (
                node.semantic_element.text.strip() + "\n\n" + child_memory.content
            )
            return child_memory, child_memory.content

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

        node_metadata = metadata.model_copy(deep=True)
        node_id = str(uuid.uuid4())
        node_metadata.hierarchy = HierarchyMetadata(node_id=node_id)
        node_metadata.chunk_type = node_type

        # If it's a leaf node, generate summary of the text
        if len(node.children) == 0 and node.semantic_element.contains_words():
            summary = await self._get_summary_from_cache(node_content, node_metadata)
            current_node = MemoryTreeNode(
                id=node_id,
                summary=summary,
                content=node_content,
                node_type=node_type,
                metadata=node_metadata,
            )
            return current_node, node_content

        mega_summaries = self._construct_summaries(children_memories, node_content)
        summary = await self._get_summary_from_cache(
            mega_summaries,
            node_metadata,
            custom_instructions=self._INT_NODE_INSTRUCTIONS.format(
                children_info=mega_summaries
            ),
        )
        current_node = MemoryTreeNode(
            id=node_id,
            summary=summary,
            content=node_content,
            node_type=node_type,
            metadata=node_metadata,
            children=children_memories,
        )
        return current_node, mega_summaries

    def _construct_summaries(
        self, children_memories: List[MemoryTreeNode], node_content: str
    ) -> str:
        """
        Construct summaries for the children nodes and combine them with the parent node content.
        """
        mega_summaries = f"""
## Parent Section: {node_content}

## Child Summaries:
"""

        for child_node in children_memories:
            mega_summaries += f"""
### Child ID: {child_node.id}

{child_node.summary}

"""
        return mega_summaries

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
