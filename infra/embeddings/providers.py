from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings # Example
from core.interfaces import IEmbeddingProvider
from langchain_core.embeddings import Embeddings
import os

class OpenAIEmbeddingProvider(IEmbeddingProvider):
    def __init__(self, model: str = "text-embedding-3-small", api_key: str = None):
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API Key not provided or found in environment variables.")
        self._embedding_model = OpenAIEmbeddings(model=self.model, api_key=self.api_key)

    def get_embedding_model(self) -> Embeddings:
        return self._embedding_model