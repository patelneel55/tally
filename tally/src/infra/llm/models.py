from abc import ABC
from abc import abstractmethod
from enum import Enum

from langchain_core.language_models import BaseLanguageModel


class ILLMProvider(ABC):
    """Interface for providing configured LLM instances."""

    @abstractmethod
    def get_model(self) -> BaseLanguageModel:
        """
        Returns a configured LangChain BaseLanguageModel instance
        (e.g., ChatOpenAI, ChatAnthropic).

        Returns:
            A LangChain BaseLanguageModel object.

        Raises:
            ConfigurationError: If the LLM cannot be configured/loaded.
            LLMError: If there's an issue communicating with the LLM API during setup.
        """
        pass


class OpenAIModels(str, Enum):
    """
    Enum for OpenAI models.
    """

    GPT_4O = "gpt-4o"
    GPT_O3_MINI = "gpt-4-turbo"
