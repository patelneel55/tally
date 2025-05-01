from enum import Enum
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class ChunkType(str, Enum):
    TEXT = "text"
    TABLE = "table"
    IMAGE = "image"


class HierarchyMetadata(BaseModel):
    # node_type: str = Field(
    #     ..., description="Type of node this entry represents in the hierarchy tree"
    # )
    # level: int = Field(
    #     ...,
    #     description="The level of the tree of the corresponding chunk associated in source the document",
    # )
    # path: str = Field(
    #     ...,
    #     description="The path from the root of the tree to the current node. Represented as titles of each of the nodes. Example: 'ROOT' > 'NODE_1' ",
    # )
    # parent: str = Field(
    #     ...,
    #     description="The title/value of the direct parent node in the tree hierarchy",
    # )
    node_id: str = Field(
        ...,
        description="The unique identifier of the node in the hierarchy tree. This is used to identify the chunk in the original document",
    )


class BaseMetadata(BaseModel):
    source: Optional[str] = Field(
        default=None, description="Source information for the metadata chunk"
    )
    hierarchy: Optional[HierarchyMetadata] = Field(
        default=None,
        description="Flattened metadata from a hierarchy tree representing the associated chunk in the original document",
    )
    chunk_type: ChunkType = Field(
        ..., description="The type of chunk this metadata is associated with"
    )

    def flatten_dict(self):
        base_dict = self.model_dump(exclude={"hierarchy"})
        if self.hierarchy:
            hierarchy_dict = self.hierarchy.model_dump()
            base_dict.update(hierarchy_dict)
        return base_dict
