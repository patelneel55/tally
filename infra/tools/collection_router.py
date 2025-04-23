import json
import logging
import re
from typing import ClassVar, Optional

from langchain_core.language_models import BaseLanguageModel
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from pydantic import BaseModel, Field
from pydantic.json import pydantic_encoder

from infra.acquisition.registry import schema_registry
from infra.core.interfaces import ILLMProvider
from infra.tools.base import BaseTool

# Set up logging
logger = logging.getLogger(__name__)


class CollectionRouterInput(BaseModel):
    query: str = Field(
        ..., description="Search query that is optimized for vector search"
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
        self._schema_registry = schema_registry

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
        response = await llm.ainvoke(prompt)
        # Chat models (like ChatOpenAI) return a message object (e.g., AIMessage)
        # Older LLM models might return just a string
        if hasattr(response, "content"):
            schemas = response.content
        elif isinstance(response, str):
            schemas = response
        if schemas.startswith("```"):
            # Match ```json\n or ```\n at the start and ``` at the end
            schemas = re.sub(r"^```(?:json)?\n?", "", schemas.strip())
            schemas = re.sub(r"\n?```$", "", schemas)
        logger.info(f"LLM Response: {schemas}")

        try:
            collection_names = json.loads(schemas)
        except json.JSONDecodeError as e:
            logger.error(
                f"Error during parsing LLM output into JSON schema: {e}", exc_info=True
            )
            collection_names = [
                collection.name
                for collection in self._schema_registry.all_collections()
            ]

        relevant_schemas = [
            json.loads(self._schema_registry.get_collection(col).json_schema())
            for col in collection_names
        ]
        logger.info(f"✅ TOOL COMPLETED: {self.name} successfully")
        return json.dumps(relevant_schemas)
