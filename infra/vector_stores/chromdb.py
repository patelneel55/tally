from langchain_community.vectorstores import Chroma
from langchain_core.vectorstores import VectorStore
from langchain_core.embeddings import Embeddings
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from core.interfaces import IVectorStore
from typing import List, Dict, Any
import os

class ChromaVectorStore(IVectorStore):
    def __init__(self, persist_directory: str = "./chroma_db", collection_name: str = "langchain"):
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self._vectorstore = None # Lazy initialization

    def _initialize(self, embeddings: Embeddings) -> VectorStore:
         # Initialize Chroma only when needed, requires embedding function
         if not self._vectorstore:
             print(f"Initializing Chroma DB at: {self.persist_directory}")
             self._vectorstore = Chroma(
                 collection_name=self.collection_name,
                 embedding_function=embeddings,
                 persist_directory=self.persist_directory
             )
         return self._vectorstore

    def get_vectorstore(self, embeddings: Embeddings) -> VectorStore:
         return self._initialize(embeddings)

    def add_documents(self, documents: List[Document], embeddings: Embeddings):
        vs = self.get_vectorstore(embeddings)
        print(f"Adding {len(documents)} documents to Chroma collection '{self.collection_name}'...")
        vs.add_documents(documents)
        # Chroma automatically persists changes if persist_directory is set
        print("Documents added.")

    def as_retriever(self, embeddings: Embeddings, search_type: str = "similarity", search_kwargs: Dict[str, Any] = None) -> BaseRetriever:
        vs = self.get_vectorstore(embeddings)
        search_kwargs = search_kwargs or {"k": 4} # Default to retrieve top 4
        return vs.as_retriever(search_type=search_type, search_kwargs=search_kwargs)