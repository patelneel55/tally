from typing import Iterator

from langchain_core.documents import Document
from pydantic import PrivateAttr
from sec_parser import SemanticTree, TreeNode


class SemanticDocument(SemanticTree, Document):
    _root_nodes: list[TreeNode] = PrivateAttr()

    """
    Represents a semantic document that combines the functionality of a SemanticTree
    and a vector-based Document. This class is designed to store and manage a
    semantic tree structure while leveraging the capabilities of a vector document.
    """

    def __init__(self, tree: SemanticTree, metadata):
        """
        Initialize the SemanticDocument with page content and optional metadata.

        Args:
            page_content (str): The content of the document.
            metadata (dict, optional): Metadata associated with the document.
        """
        Document.__init__(
            self,
            page_content=tree.render(verbose=True, pretty=False),
            metadata=metadata,
        )
        SemanticTree.__init__(self, tree._root_nodes)
        self._root_nodes = tree._root_nodes

    def __iter__(self) -> Iterator[TreeNode]:
        """
        Iterate over the root nodes of the semantic tree.

        Returns:
            Iterator[TreeNode]: An iterator over the root nodes of the tree.
        """
        return super().__iter__(self)

    def as_tree(self) -> SemanticTree:
        """
        Return the semantic document as a SemanticTree.

        Returns:
            SemanticTree: The semantic tree representation of the document.
        """
        return SemanticTree(self._root_nodes)
