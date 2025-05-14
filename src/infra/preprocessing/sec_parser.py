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

from infra.acquisition.sec_fetcher import SECFiling
from infra.collections.models import ChunkType, HierarchyMetadata
from infra.databases.cache import Cache
from infra.databases.engine import get_sqlalchemy_engine
from infra.databases.registry import TABLE_SCHEMAS, TableNames
from infra.llm.models import ILLMProvider
from infra.pipelines.mem_walker import MemoryTreeNode
from infra.preprocessing.models import IParser
from infra.tools.summarizer import SummarizerInput, SummarizerTool
from infra.utils import ProgressTracker


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
You are an expert summarizer helping an AI system navigate a long SEC filing.
Each of the child nodes below contains a summary of a section in the filing. Your task is to produce a **concise, structured rollup** that enables another agent to decide:
- Whether to go deeper into this branch of the document
- Which child sections are most likely to contain query-relevant content
You are not summarizing the content yourself. You are creating an **index with intelligent signposting** that respects the hierarchical structure of the document.
--------------------
<output_format>
### Overview
Briefly describe what this parent node covers. Mention the filing section and topical scope.
Example:
> This node includes summaries related to JPMorgan’s capital disclosures and liquidity planning, drawn from Item 2 of the Q1 2025 10-Q.
### Child Summary Tree
Return an indented tree view of the children and their descendants. For each node:
- Include the **node ID or title**
- Provide a short pointer to what content it contains (e.g., disclosures, metrics, commentary)
- Indent child nodes under their immediate parents using bullet levels to reflect hierarchy
Format example:
- [Node ID]: [Top-level topic or summary label]
- [Child Node ID]: [Subtopic or detail]
- [Child Node ID]: [Subtopic or detail]
- [Sibling Node ID]: [Different topic]

Do not fabricate hierarchy — only reflect the actual parent-child relationships in {children_info}.
--------------------
<rules>
- Preserve all child nodes and their hierarchy. Do NOT omit any node.
- Do NOT paraphrase child summaries. Only describe what's in them.
- Do NOT filter based on perceived materiality or importance.
- If a child is routine or unchanged, say so explicitly (e.g., “Unchanged risk language from prior filing”).
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
            table_name=TableNames.SECFilingSummary.value,
            column_mapping=TABLE_SCHEMAS[TableNames.SECFilingSummary],
        )
        self.hierarchy_cache = Cache(
            engine=get_sqlalchemy_engine(),
            table_name=TableNames.SECFilingHierarchy.value,
            column_mapping=TABLE_SCHEMAS[TableNames.SECFilingHierarchy],
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
        async with ProgressTracker(len(list(tree.nodes))) as tracker:
            tasks = [
                self._create_document_structure(root_node, metadata, tracker)
                for root_node in tree
            ]
            results = await asyncio.gather(*tasks)
            for memory_tree, raw_content in results:
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
            self.hierarchy_cache.write(
                metadata_hash,
                ticker=metadata.ticker,
                filing_type=metadata.formType,
                filing_date=metadata.filing_date,
                status="in-progress",
            )
            root_tree_node = await self._index_hierarchy(tree, metadata)
            self.hierarchy_cache.write(
                metadata_hash,
                ticker=metadata.ticker,
                filing_type=metadata.formType,
                filing_date=metadata.filing_date,
                status="complete",
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
        self, node: sp.TreeNode, metadata: SECFiling, tracker: ProgressTracker
    ) -> Tuple[MemoryTreeNode, str]:
        if not node:
            return None, ""

        children_memories: List[MemoryTreeNode] = []
        total_content: List[str] = []

        # Create a list of coroutine objects and gather results
        tasks = [
            self._create_document_structure(child, metadata, tracker)
            for child in node.children
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
            await tracker.step()
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
        await tracker.step()
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
