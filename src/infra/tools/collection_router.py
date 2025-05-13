import json
import logging
from typing import ClassVar, List, Optional

from langchain_core.language_models import BaseLanguageModel
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from pydantic import BaseModel, Field

from infra.collections.registry import get_schema_registry
from infra.llm.models import ILLMProvider
from infra.tools.models import BaseTool


# Set up logging
logger = logging.getLogger(__name__)


class CollectionRouterInput(BaseModel):
    query: str = Field(
        ..., description="Search query that is optimized for vector search"
    )


class CollectionRouterOutput(BaseModel):
    collections: List[str] = Field(
        description="A list of collections pertaining to the query"
    )


class CollectionRouterTool(BaseTool):
    _TOOL_NAME: ClassVar[str] = "route_query_to_collections"
    _TOOL_DESCRIPTION: ClassVar[
        str
    ] = """
Use this tool to determine which document collections are relevant to a user's financial query.
It analyzes the query and selects one or more collections that contain the appropriate information.
For each selected collection, this tool also returns its expected metadata schema — a list of fields (like ticker, period, etc.) that must be extracted from the query to perform a vector search.

This tool must always be used first before calling any vector search or document retrieval tool.
It ensures the agent knows:
    Which collections to search
    What metadata filters are required to scope the results

Output includes:
    name: name of the relevant collection
    description: summary of what kind of documents it contains
    metadata_model: a JSON schema describing the required metadata fields and their meanings
"""

    _COLLECTION_ROUTER_PROMPT = """
You are an expert financial data analyst assistant. You are given:

1. A natural language query from the user
2. A list of available document collections (in JSON), where each collection contains:
    - `name`: the unique identifier for the collection
    - `description`: what kind of data this collection contains

Your job is to determine **which collections are relevant to answer the user's query**.

Only include collections that are likely to contain the required information based on their descriptions and metadata fields.

### Input Query:
{query}

### Available Collections:
{collections_json}

### Output Format:
Only return a JSON array of strings, each string being the `name` of a relevant collection.

Example:
["SECChunk", "EarningsCallChunk"]
"""

    def __init__(self, llm_provider: ILLMProvider):
        super().__init__(
            name=self._TOOL_NAME,
            description=self._TOOL_DESCRIPTION,
            args_schema=CollectionRouterInput,
        )

        self._llm_provider = llm_provider
        self._llm_instance: Optional[BaseLanguageModel] = None  # Lazy load the model

        self._prompt_template = ChatPromptTemplate.from_messages(
            [
                HumanMessagePromptTemplate.from_template(
                    self._COLLECTION_ROUTER_PROMPT
                ),
            ]
        )
        self._schema_registry = get_schema_registry()

    def _llm(self) -> BaseLanguageModel:
        """
        Lazy load the language model instance.

        This method ensures that the language model is only loaded when needed.
        """
        if self._llm_instance is None:
            self._llm_instance = self._llm_provider.get_model()
        return self._llm_instance

    async def execute(self, **kwargs) -> str:
        logger.info(f"📌 TOOL EXECUTION: {self.name}")
        llm = self._llm()

        router_input = CollectionRouterInput(**kwargs)
        prompt = self._prompt_template.format_prompt(
            query=router_input.query,
            collections_json=self._schema_registry.json_schema(),
        )

        response: CollectionRouterOutput = await llm.with_structured_output(
            CollectionRouterOutput
        ).ainvoke(prompt)
        relevant_schemas = [
            json.loads(self._schema_registry.get_collection(col).json_schema())
            for col in response.collections
        ]
        logger.info(f"✅ TOOL COMPLETED: {self.name} successfully")
        return json.dumps(relevant_schemas)
