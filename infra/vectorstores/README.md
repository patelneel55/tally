# Vector Stores

This directory contains implementations of the `IVectorStore` interface for different vector database backends.

## WeaviateVectorStore

`WeaviateVectorStore` is an implementation of the `IVectorStore` interface that uses [Weaviate](https://weaviate.io/) as the backend vector database.

### Installation

To use this vector store, you need to install the Weaviate client:

```bash
pip install weaviate-client
```

### Usage

```python
from infra.vectorstores.weaviate_store import WeaviateVectorStore, WeaviateConfig
from langchain_openai import OpenAIEmbeddings

# Initialize configuration
config = WeaviateConfig(
    url="http://localhost:8080",  # Weaviate server URL
    api_key="your-weaviate-api-key",  # Optional API key
    class_name="Document",  # Weaviate class name
)

# Initialize the vector store
vector_store = WeaviateVectorStore(config)

# Initialize embeddings model
embeddings = OpenAIEmbeddings()

# Add documents
from langchain_core.documents import Document

documents = [
    Document(page_content="This is a sample document", metadata={"source": "example.txt"}),
    Document(page_content="Another example document", metadata={"source": "sample.txt"}),
]

vector_store.add_documents(documents, embeddings)

# Or add texts directly
texts = ["Text 1", "Text 2"]
metadatas = [{"source": "file1.txt"}, {"source": "file2.txt"}]
ids = vector_store.add_texts(texts, metadatas, embeddings)

# Search for similar documents
results = vector_store.similarity_search("sample query", k=2, embeddings=embeddings)

# Get a retriever
retriever = vector_store.as_retriever(embeddings, search_kwargs={"k": 4})

# Delete documents
vector_store.delete(ids)
```

### Configuration Options

The `WeaviateConfig` dataclass supports the following options:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| url | str | required | URL of the Weaviate server |
| api_key | Optional[str] | None | API key for authentication |
| additional_headers | Optional[Dict[str, str]] | None | Additional HTTP headers |
| class_name | str | "Document" | Name of the Weaviate class to use |
| batch_size | int | 100 | Number of objects per batch when adding documents |
| text_field | str | "text" | Name of the field to store document text |
| metadata_field | str | "metadata" | Name of the field to store document metadata |

### Error Handling

The implementation raises the following exceptions:

- `ConnectionError`: If connection to Weaviate fails
- `RuntimeError`: For most operational errors (schema creation, adding documents, etc.)
- `ValueError`: For invalid input parameters 

## ChromaVectorStore

`ChromaVectorStore` is an implementation of the `IVectorStore` interface that uses [Chroma](https://www.trychroma.com/) as the backend vector database. Chroma is a lightweight, in-memory or persisted vector database that can be used for semantic search operations.

### Installation

To use this vector store, you need to install the Chroma client:

```bash
pip install chromadb
```

### Usage

```python
from infra.vector_stores.chromdb import ChromaVectorStore
from langchain_openai import OpenAIEmbeddings

# Initialize the vector store
vector_store = ChromaVectorStore(
    persist_directory="./my_chroma_db",  # Directory to persist the database
    collection_name="my_documents"  # Name of the collection in Chroma
)

# Initialize embeddings model
embeddings = OpenAIEmbeddings()

# Add documents
from langchain_core.documents import Document

documents = [
    Document(page_content="This is a sample document", metadata={"source": "example.txt"}),
    Document(page_content="Another example document", metadata={"source": "sample.txt"}),
]

vector_store.add_documents(documents, embeddings)

# Or add texts directly
texts = ["Text 1", "Text 2"]
metadatas = [{"source": "file1.txt"}, {"source": "file2.txt"}]
ids = vector_store.add_texts(texts, metadatas, embeddings)

# Search for similar documents
results = vector_store.similarity_search("sample query", k=2, embeddings=embeddings)

# Get a retriever
retriever = vector_store.as_retriever(embeddings, search_kwargs={"k": 4})

# Delete documents
vector_store.delete(ids)

# Retrieve document by ID
document = vector_store.get_document_by_id(ids[0])
```

### Configuration Options

The `ChromaVectorStore` constructor supports the following options:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| persist_directory | str | "./chroma_db" | Directory to persist the Chroma database |
| collection_name | str | "langchain" | Name of the collection in Chroma |

### Features

- **Local Storage**: Chroma can store embeddings locally on disk, making it a good choice for development or when privacy is a concern.
- **Simple Setup**: No external database needed - Chroma can run embedded in your application.
- **Performance**: Optimized for small to medium-sized document collections.
- **Persistence**: Automatically persists changes to disk when a persist_directory is provided.

### Error Handling

The implementation raises the following exceptions:

- `ValueError`: If required parameters are missing or invalid
- `RuntimeError`: For most operational errors (adding documents, searching, etc.) 