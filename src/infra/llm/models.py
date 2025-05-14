from abc import ABC, abstractmethod
from datetime import timedelta
from enum import Enum

from langchain_core.language_models import BaseLanguageModel

from infra.ratelimit.limiter import RateLimiter
from infra.ratelimit.models import AlgorithmType, RateLimitRule


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


class RateLimitType(str, Enum):
    REQUEST_LIMIT = "request_limit"
    TOKEN_LIMIT = "token_limit"


class OpenAIModels(str, Enum):
    """
    Enum for OpenAI models.
    """

    GPT_4O = (
        "gpt-4o",
        RateLimiter(
            rules={
                RateLimitType.REQUEST_LIMIT.value: RateLimitRule(
                    algorithm=AlgorithmType.LEAKY_BUCKET,
                    limit=5000,
                    period=timedelta(minutes=1),
                ),
                RateLimitType.TOKEN_LIMIT.value: RateLimitRule(
                    algorithm=AlgorithmType.TOKEN_BUCKET,
                    limit=450000,
                    period=timedelta(minutes=1),
                ),
            },
        ),
    )
    GPT_O4_MINI = (
        "o4-mini",
        RateLimiter(
            rules={
                RateLimitType.REQUEST_LIMIT.value: RateLimitRule(
                    algorithm=AlgorithmType.LEAKY_BUCKET,
                    limit=5000,
                    period=timedelta(minutes=1),
                ),
                RateLimitType.TOKEN_LIMIT.value: RateLimitRule(
                    algorithm=AlgorithmType.TOKEN_BUCKET,
                    limit=2000000,
                    period=timedelta(minutes=1),
                ),
            },
        ),
    )

    def __new__(cls, value: str, rate_limiter: RateLimiter = None):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.rate_limiter = rate_limiter
        return obj
