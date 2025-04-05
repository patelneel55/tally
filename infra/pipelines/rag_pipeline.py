from typing import Any, Dict, List

from core.interfaces import (
    IEmbeddingProvider,
    ILLMProvider,
    IOutputFormatter,
    IPromptStrategy,
    IVectorStore,
)
from langchain_core.documents import Document
from langchain_core.runnables import RunnableParallel, RunnablePassthrough


class RAGFinancialAnalysisPipeline:
    def __init__(
        self,
        prompt_strategy: IPromptStrategy,  # Assumes a RAG-compatible strategy
        llm_provider: ILLMProvider,
        output_formatter: IOutputFormatter,
        vector_store: IVectorStore,
        embedding_provider: IEmbeddingProvider,
        retriever_search_type: str = "similarity",
        retriever_search_kwargs: Dict[str, Any] = None,
    ):

        self.prompt_strategy = prompt_strategy
        self.llm = llm_provider.get_model()
        self.output_parser = output_formatter.get_parser()
        self.formatter = output_formatter
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.retriever_search_type = retriever_search_type
        self.retriever_search_kwargs = retriever_search_kwargs or {"k": 4}  # Default k

    def run(self, task_description: str, prompt_context: Dict[str, Any] = None) -> str:
        print(f"Starting RAG pipeline for task: {task_description}")
        prompt_context = prompt_context or {}

        # 1. Get Retriever
        embeddings = self.embedding_provider.get_embedding_model()
        retriever = self.vector_store.as_retriever(
            embeddings=embeddings,
            search_type=self.retriever_search_type,
            search_kwargs=self.retriever_search_kwargs,
        )

        # 2. Create Prompt Template (expects 'retrieved_context' and 'question')
        # The prompt strategy needs to be aware it's for RAG
        # We pass None for retrieved_docs here because the RAG chain will fetch them
        prompt_template = self.prompt_strategy.create_prompt(
            context=prompt_context,
            task_description=task_description,  # Used by strategy if needed
            retrieved_docs=None,  # RAG chain handles retrieval
        )

        # 3. Define RAG Chain using LCEL
        #    Inputs: 'question' (which is our task_description)
        #    Outputs: Formatted final string
        rag_chain = (
            # Parallel Runnable: gets context via retriever, passes question through
            RunnableParallel(
                {
                    "retrieved_context": retriever | format_docs,
                    "question": RunnablePassthrough(),
                }
            )
            | prompt_template  # Fills template with context and question
            | self.llm  # Sends filled prompt to LLM
            | self.output_parser  # Parses LLM response
            | self.formatter.format  # Formats the parsed data (custom method) - needs slight adjustment if parser returns non-dict
        )

        # If formatter.format expects the direct parsed output:
        # rag_chain_final = rag_chain | self.formatter.format

        print("Invoking RAG chain...")
        # 4. Invoke Chain
        # The input to the chain is simply the original question/task description
        final_result = rag_chain.invoke(task_description)

        print("RAG pipeline finished.")
        return final_result


# --- Helper function for formatting docs ---
def format_docs(docs: List[Document]) -> str:
    """Helper function to format retrieved documents for the prompt context."""
    return "\n\n".join(doc.page_content for doc in docs)


# In main.py or elsewhere:
# ... (initialize components as before, plus EmbeddingProvider, VectorStore)
# vector_store = ChromaVectorStore(persist_directory="./financial_db")
# embedding_provider = OpenAIEmbeddingProvider()
# prompt_strategy = RAGRolePromptingStrategy() # Use a RAG-specific strategy
#
# # --- Indexing (Run separately or first time) ---
# index_pipeline = IndexingPipeline(loader, parser, splitter, embedding_provider, vector_store)
# index_pipeline.run('path/to/report.pdf')
#
# # --- Running RAG ---
# rag_pipeline = RAGFinancialAnalysisPipeline(
#     prompt_strategy, llm_provider, output_formatter, vector_store, embedding_provider
# )
# result = rag_pipeline.run("What were the main risks discussed in the report?")
# print(result)
