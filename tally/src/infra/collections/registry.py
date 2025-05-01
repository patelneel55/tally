import json
from typing import Dict
from typing import List
from typing import Optional
from typing import Type

from pydantic import BaseModel
from pydantic import ConfigDict
from langchain_text_splitters import MarkdownTextSplitter

from infra.acquisition.models import BaseMetadata
from infra.acquisition.sec_fetcher import EDGARFetcher
from infra.acquisition.sec_fetcher import FilingRequest
from infra.acquisition.sec_fetcher import SECFiling
from infra.ingestion.web_loader import WebLoader
from infra.llm.providers import OpenAIProvider
from infra.pipelines.indexing_pipeline import IndexingPipeline
from infra.preprocessing.sec_parser import SECParser
from infra.preprocessing.simple_splitters import LangChainTextSplitter


class CollectionSchema(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    metadata_model: Type[BaseMetadata]
    example_queries: Optional[List[str]]
    indexer: IndexingPipeline
    indexer_schema: Type[BaseModel]

    def json_schema(self) -> str:
        base = self.model_dump(exclude={"metadata_model", "indexer", "indexer_schema"})
        base["metadata_schema"] = self.metadata_model.model_json_schema()
        return json.dumps(base, indent=2)


class MetadataSchemaRegistry(BaseModel):
    registry: Dict[str, CollectionSchema]

    def get_collection(self, collection: str) -> CollectionSchema:
        if collection not in self.registry:
            raise ValueError(
                f"invalid collection name provided, '{collection}' is not a registered collection"
            )
        return self.registry[collection]

    def all_collections(self) -> List[CollectionSchema]:
        return list(self.registry.values())

    def json_schema(self) -> str:
        collections = []
        for col in self.all_collections():
            collections.append(json.loads(col.json_schema()))
        return json.dumps(collections, indent=2)


_schema_registry: MetadataSchemaRegistry | None = None


def get_schema_registry() -> MetadataSchemaRegistry:
    global _schema_registry
    if _schema_registry is None:
        _schema_registry = MetadataSchemaRegistry(
            registry={
                "SECFilings": CollectionSchema(
                    name="SECFilings",
                    description="Vector chunks from SEC filings like 10-K, 10-Q, 8-K etc.",
                    metadata_model=SECFiling,
                    example_queries=[],
                    indexer=IndexingPipeline(
                        fetcher=EDGARFetcher(),
                        loader=WebLoader(crawl_strategy="all", max_crawl_depth=0),
                        parser=SECParser(llm_provider=OpenAIProvider()),
                        splitter=LangChainTextSplitter(splitter=MarkdownTextSplitter),
                    ),
                    indexer_schema=FilingRequest,
                ),
            }
        )
    return _schema_registry
