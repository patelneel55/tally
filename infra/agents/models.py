from pydantic import BaseModel, Field

class VectorSearchQuery(BaseModel):
    query: str = Field(..., description="Search query that is optimized for vector search")
    justification: str = Field(..., description="A reason for why this query is relevant to the user's request")