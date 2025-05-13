"""
Core Interfaces
--------------

This module defines the core interfaces used throughout the infrastructure
layer. These interfaces establish the contract that all concrete implementations
must follow.
"""

import abc
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional, Union

# Import base types from LangChain for interoperability
from langchain_core.documents import Document
from langchain_core.output_parsers import BaseOutputParser
from langchain_core.prompts import BasePromptTemplate


class IPromptStrategy(abc.ABC):
    """Interface for creating LLM prompts based on different strategies."""

    @abc.abstractmethod
    def create_prompt(
        self,
        context: Dict[str, Any],
        task_description: str,
        retrieved_docs: Optional[List[Document]] = None,
    ) -> BasePromptTemplate:
        """
        Creates a LangChain prompt template based on the specific strategy.
        For RAG strategies, it should incorporate the retrieved_docs.

        Args:
            context: A dictionary containing general context information
                     (might include specific document chunks if not RAG).
            task_description: A description of the task for the LLM.
            retrieved_docs: Optional list of relevant documents retrieved
                             from the vector store for RAG pipelines.

        Returns:
            A configured LangChain BasePromptTemplate instance.
        """
        pass


class IOutputFormatter(abc.ABC):
    """Interface for formatting the final output of the analysis."""

    @abc.abstractmethod
    def get_parser(self) -> BaseOutputParser:
        """
        Returns a LangChain BaseOutputParser instance configured to parse
        the expected LLM response format (e.g., JsonOutputParser, StrOutputParser).

        Returns:
            A LangChain BaseOutputParser instance.
        """
        pass

    @abc.abstractmethod
    def format(self, parsed_data: Any) -> str:
        """
        Formats the data parsed by the output parser into the final desired
        string representation (e.g., a JSON string, CSV row, Markdown text).

        Args:
            parsed_data: The data structure returned by this formatter's associated parser.

        Returns:
            A string containing the final formatted output.

        Raises:
            OutputFormattingError: If formatting fails.
        """
        pass
