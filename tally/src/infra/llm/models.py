from abc import ABC
from abc import abstractmethod
from enum import Enum
from typing import List

from aiolimiter import AsyncLimiter

from langchain_core.language_models import BaseLanguageModel

from infra.config.rate_limiter import RateLimiter


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

    @abstractmethod
    def estimate_tokens(self, prompt: str) -> int:
        """
        Estimate the number of tokens in a given prompt.

        Args:
            prompt (str): The input prompt.

        Returns:
            int: Estimated number of tokens.
        """
        pass


class OpenAIModels(str, Enum):
    """
    Enum for OpenAI models.
    """

    GPT_4O = (
        "gpt-4o",
        RateLimiter(
            request_limiters=[
                AsyncLimiter(10, 1),  # 10 requests per second
                AsyncLimiter(500, 60),  # 500 requests per minute
            ],
            token_limiters=[
                AsyncLimiter(30000, 60),  # 30k tokens per minute
            ],
        ),
    )
    GPT_O4_MINI = (
        "o4-mini",
        RateLimiter(
            request_limiters=[
                AsyncLimiter(10, 1),  # 10 requests per second
                AsyncLimiter(500, 60),  # 500 requests per minute
            ],
            token_limiters=[
                AsyncLimiter(200000, 60),  # 200k tokens per minute
            ],
        ),
    )

    def __new__(cls, value: str, rate_limiter: RateLimiter = None):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.rate_limiter = rate_limiter
        return obj
