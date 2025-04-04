from enum import Enum

class OpenAIEmbeddingModels(str, Enum):
    SMALL3 = "text-embedding-3-small"
    LARGE3 = "text-embedding-3-large"