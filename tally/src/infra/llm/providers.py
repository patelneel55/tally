import logging
import os
from typing import Any

from langchain_core.language_models import BaseLanguageModel
from langchain_openai import ChatOpenAI

from infra.config.settings import get_settings
from infra.llm.models import ILLMProvider
from infra.llm.models import OpenAIModels


logger = logging.getLogger(__name__)


class OpenAIProvider(ILLMProvider):
    def __init__(
        self,
        api_key: str = None,
        model: str = OpenAIModels.GPT_4O,
        temperature: float = 0.7,
        max_tokens: int = 150,
        **kwargs: Any,
    ):
        self.model = model
        self.api_key = api_key or get_settings().OPENAI_API_KEY
        if not self.api_key:
            raise ValueError(
                "OpenAI API Key not provided or found in environment variables."
            )
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.extra_kwargs = kwargs
        self._llm_instance = None  # Lazy initialization

    def _initialize_model(self) -> BaseLanguageModel:
        """
        Initialize the OpenAI model with the provided parameters.
        """
        logger.debug(f"Initialzing ChatOpenAI instance (model={self.model})...")
        try:
            model_kwargs = {
                "model": self.model,
                "temperature": self.temperature,
                **self.extra_kwargs,
            }
            model = ChatOpenAI(api_key=self.api_key, **model_kwargs)
        except Exception as e:
            logger.error(f"Error initializing OpenAI model: {e}")
            raise e
        return model

    def get_model(self) -> BaseLanguageModel:
        if self._llm_instance is None:
            self._llm_instance = self._initialize_model()
        return self._llm_instance
