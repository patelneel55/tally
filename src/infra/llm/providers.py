import logging
from typing import Any

import tiktoken
from langchain_core.language_models import BaseLanguageModel
from langchain_openai import ChatOpenAI

from infra.config.settings import get_settings
from infra.llm.models import ILLMProvider, OpenAIModels, RateLimitType


logger = logging.getLogger(__name__)


class OpenAIProvider(ChatOpenAI, ILLMProvider):
    def __init__(
        self,
        api_key: str = None,
        model: OpenAIModels = OpenAIModels.GPT_O4_MINI,
        temperature: float = 1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ):
        self._api_key = api_key or get_settings().OPENAI_API_KEY
        if not self._api_key:
            raise ValueError(
                "OpenAI API Key not provided or found in environment variables."
            )
        model_kwargs = {
            "model": model.value,
            "temperature": temperature,
            "max_completion_tokens": max_tokens,
            **kwargs,
        }
        super().__init__(api_key=self._api_key, **model_kwargs)

        # These must come after super().__init__ because parent Pydantic will
        # overwrite them
        self._model = model
        self._max_tokens = max_tokens

    def get_model(self) -> BaseLanguageModel:
        return self

    def estimate_tokens(self, text: str) -> int:
        try:
            enc = tiktoken.encoding_for_model(self._model.value)
        except KeyError:
            # Fallback if model isn't recognized by tiktoken
            enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text)) + self._max_tokens

    async def ainvoke(self, *args, **kwargs) -> Any:
        estimated_tokens = self.estimate_tokens(str(args[0]))
        if self._model.rate_limiter:
            await self._model.rate_limiter.acquire(
                [
                    (RateLimitType.REQUEST_LIMIT.value, 1),
                    (RateLimitType.TOKEN_LIMIT.value, estimated_tokens),
                ]
            )
        return await super().ainvoke(*args, **kwargs)
