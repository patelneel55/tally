import logging
from typing import Any

import tiktoken
from langchain_core.language_models import BaseLanguageModel, LanguageModelInput
from langchain_openai import ChatOpenAI

from infra.config.settings import get_settings
from infra.databases.cache import SQLAlchemyCache
from infra.databases.engine import get_sqlalchemy_engine
from infra.databases.llm_cache import LLMCache
from infra.databases.registry import TABLE_SCHEMAS, TableNames
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
        self._llm_kwargs = model_kwargs
        self._model = model
        self._max_tokens = max_tokens

        self._cache = SQLAlchemyCache(
            get_sqlalchemy_engine(),
            table_name=TableNames.OpenAILLM.value,
            column_mapping=TABLE_SCHEMAS[TableNames.OpenAILLM],
        )
        self._llm_cache = LLMCache(self._cache, llm_name=self.get_name())

    def get_model(self) -> BaseLanguageModel:
        return self

    def estimate_tokens(self, text: str) -> int:
        try:
            enc = tiktoken.encoding_for_model(self._model.value)
        except KeyError:
            # Fallback if model isn't recognized by tiktoken
            enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text)) + self._max_tokens

    async def ainvoke(self, input: LanguageModelInput, *args, **kwargs) -> Any:
        estimated_tokens = self.estimate_tokens(str(args[0]))
        hash = self._llm_cache.generate_id(input.to_string())
        with self._llm_cache.check(hash, llm_kwargs=self._llm_kwargs) as ctx:
            if ctx.is_hit:
                return ctx.cache_value

            if self._model.rate_limiter:
                await self._model.rate_limiter.acquire(
                    [
                        (RateLimitType.REQUEST_LIMIT.value, 1),
                        (RateLimitType.TOKEN_LIMIT.value, estimated_tokens),
                    ]
                )

            response = await super().ainvoke(input, *args, **kwargs)
            ctx.set_value(content=response, llm_kwargs=self._llm_kwargs)
            return response
