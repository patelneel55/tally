from typing import Any, Dict, List

from core.interfaces import IPromptStrategy
from langchain_core.documents import Document
from langchain_core.prompts import BasePromptTemplate, ChatPromptTemplate


def format_docs(docs: List[Document]) -> str:
    """Helper function to format retrieved documents for the prompt."""
    return "\n\n".join(doc.page_content for doc in docs)


class RolePromptingStrategy(IPromptStrategy):
    def create_prompt(
        self,
        context: Dict[str, Any],  # General context (can be empty for RAG)
        task_description: str,
        retrieved_docs: List[Document] = None,
    ) -> BasePromptTemplate:
        if not retrieved_docs:
            # Fallback or error? Or use a non-RAG template?
            # For now, let's assume retrieved_docs are required for this strategy
            raise ValueError(
                "Retrieved documents are required for RAGRolePromptingStrategy."
            )

        system_message = "You are a meticulous financial analyst. Use the provided context ONLY to answer the question."
        # Format retrieved docs into a single string
        retrieved_context = format_docs(retrieved_docs)

        # Template now expects 'retrieved_context' and 'question'
        human_template = (
            "Context:\n"
            "```\n"
            "{retrieved_context}\n"
            "```\n\n"
            "Question: {question}"  # Using 'question' aligns with common RAG chain patterns
        )

        return ChatPromptTemplate.from_messages(
            [
                ("system", system_message),
                ("human", human_template),
            ]
        )
