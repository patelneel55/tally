from core.interfaces import (
    IDataFetcher,
    IEmbeddingProvider,
    IParser,
    ISplitter,
    IVectorStore,
)


class IndexingPipeline:
    def __init__(
        self,
        loader: IDataFetcher,
        parser: IParser,
        splitter: ISplitter,
        embedding_provider: IEmbeddingProvider,
        vector_store: IVectorStore,
    ):
        self.loader = loader
        self.parser = parser
        self.splitter = splitter
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store

    def run(self, source_uri: str):
        print(f"Starting indexing pipeline for source: {source_uri}")
        # 1. Load
        raw_docs = self.loader.load(source_uri)
        # 2. Parse
        parsed_docs = [self.parser.parse(doc) for doc in raw_docs]
        # 3. Split
        split_docs = self.splitter.split_documents(parsed_docs)
        print(f"Split into {len(split_docs)} chunks.")
        # 4. Get Embeddings & Add to Vector Store
        embeddings = self.embedding_provider.get_embedding_model()
        self.vector_store.add_documents(split_docs, embeddings)
        print("Indexing pipeline finished.")
