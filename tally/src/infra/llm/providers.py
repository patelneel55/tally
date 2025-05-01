import logging
import os
from typing import Any, ClassVar

from langchain_core.language_models import BaseLanguageModel
from langchain_openai import ChatOpenAI
import tiktoken

from infra.config.settings import get_settings
from infra.llm.models import ILLMProvider
from infra.llm.models import OpenAIModels


logger = logging.getLogger(__name__)


class OpenAIProvider(ChatOpenAI, ILLMProvider):
    _model: ClassVar[OpenAIModels] = OpenAIModels.GPT_O4_MINI
    _max_tokens: ClassVar[int] = 2048

    def __init__(
        self,
        api_key: str = None,
        model: OpenAIModels = OpenAIModels.GPT_4O,
        temperature: float = 1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ):
        self._model_enum = model
        self._api_key = api_key or get_settings().OPENAI_API_KEY
        if not self._api_key:
            raise ValueError(
                "OpenAI API Key not provided or found in environment variables."
            )
        self._temperature = temperature
        self._extra_kwargs = kwargs
        self._llm_instance = False  # Lazy initialization

        model_kwargs = {
            "model": model.value,
            "temperature": self._temperature,
            "max_completion_tokens": max_tokens,
            **self._extra_kwargs,
        }
        super().__init__(api_key=self._api_key, **model_kwargs)

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
            await self._model.rate_limiter.acquire(estimated_tokens)
        return await super().ainvoke(*args, **kwargs)
