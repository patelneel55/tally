from typing import Any, Dict, List

from infra.core.interfaces import (
    IEmbeddingProvider,
    ILLMProvider,
    IOutputFormatter,
    IPromptStrategy,
    IVectorStore,
)
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_core.language_models import BaseLanguageModel



class RAGFinancialAnalysisPipeline:
    def __init__(
        self,
        llm_provider: ILLMProvider,
        output_formatter: IOutputFormatter,
        vector_store: IVectorStore,
        embedding_provider: IEmbeddingProvider,
        prompt_strategy: IPromptStrategy = None,  # Optional now since we'll create prompt directly
    ):

        self.prompt_strategy = prompt_strategy
        self.llm_provider = llm_provider
        self._llm_instance = None  # Lazy initialization
        self.output_parser = output_formatter.get_parser()
        self.formatter = output_formatter
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider

    def _llm(self) -> BaseLanguageModel:
        """
        Lazy initialization of the LLM instance.
        """
        if self._llm_instance is None:
            self._llm_instance = self.llm_provider.get_model()
        return self._llm_instance

    async def run(self, task_description: str, prompt_context: Dict[str, Any] = None, filters: Dict[str, Any] = None, retriever_search_type: str = "similarity", retriever_search_kwargs: Dict[str, Any] = None) -> str:
        print(f"Starting RAG pipeline for task: {task_description}")
        prompt_context = prompt_context or {}

        # 1. Get Retriever with filters if provided
        embeddings = self.embedding_provider.get_embedding_model()

        # Deep copy the default search kwargs so we don't modify the instance variable
        search_kwargs = dict(retriever_search_kwargs or {"k": 4})

        # Add filters to search_kwargs if provided via the filters parameter
        if filters:
            print(f"Applying filters to retrieval: {filters}")
            search_kwargs["filter"] = filters

        print(f"Using search type: {retriever_search_type}, search parameters: {search_kwargs}")

        retriever = self.vector_store.as_retriever(
            embeddings=embeddings,
            search_type=retriever_search_type,
            search_kwargs=search_kwargs,
        )

        # 2. Create Prompt Template directly
        # Create a system and human message template
        system_template = (
            """
You are a financial analysis assistant tasked with answering user questions using only the context provided below.
This context has been retrieved from official SEC filings (10-K, 10-Q, or 8-K) for the specified company.

Your job is to:

1. Read and understand the user's question.
2. Review the full set of retrieved filing excerpts provided in the context section.
3. Generate a clear, detailed, and accurate answer based only on that context.
4. Avoid making up information or inferring anything that is not directly supported by the context.
5. If applicable, cite the most relevant source chunk(s) to support your answer using a format like: [source #1], [source #2].

Important Guidelines:
- Do NOT hallucinate or fabricate financial information.
- If the context does not contain a direct answer, clearly say so and do not speculate.
- Assume the user may be using this output to make financial decisions — your answer must be reliable and grounded in the source material.

Answer as a professional equity research analyst would: clear, precise, and factually grounded.
        """
        )

        human_template = """Context information is below.
---------------------
{retrieved_context}
---------------------

Given the context information and no prior knowledge, answer the following question:
{question}
"""

        # Create prompt template from messages
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", system_template),
            ("human", human_template),
        ])

        # Retrieve LLM
        llm = self._llm()

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
            | llm  # Sends filled prompt to LLM
            | self.output_parser  # Parses LLM response
            | self.formatter.format  # Formats the parsed data (custom method) - needs slight adjustment if parser returns non-dict
        )

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
