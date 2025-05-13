from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from infra.config.settings import get_settings
from infra.embeddings.models import IEmbeddingProvider, OpenAIEmbeddingModels


class OpenAIEmbeddingProvider(IEmbeddingProvider):
    def __init__(self, model: str = OpenAIEmbeddingModels.SMALL3, api_key: str = None):
        self.model = model
        self.api_key = api_key or get_settings().OPENAI_API_KEY
        if not self.api_key:
            raise ValueError(
                "OpenAI API Key not provided or found in environment variables."
            )
        self._embedding_model = OpenAIEmbeddings(model=self.model, api_key=self.api_key)

    def get_embedding_model(self) -> Embeddings:
        return self._embedding_model
