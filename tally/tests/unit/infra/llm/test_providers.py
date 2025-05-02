from unittest.mock import MagicMock, patch

import pytest
from langchain_core.language_models import BaseLanguageModel

from infra.llm.models import OpenAIModels
from infra.llm.providers import OpenAIProvider


@pytest.mark.parametrize("mock_settings", ["infra.llm.providers"], indirect=True)
class TestOpenAIProvider:
    """Test suite for OpenAIProvider class."""

    @pytest.fixture
    def mock_chat_openai(self):
        """Fixture to mock ChatOpenAI class."""
        with patch("infra.llm.providers.ChatOpenAI") as mock:
            mock_instance = MagicMock(spec=BaseLanguageModel)
            mock.return_value = mock_instance
            yield mock

    def test_initialization_with_defaults(self, mock_settings, mock_chat_openai):
        """Test initialization with default parameters."""
        provider = OpenAIProvider()

        assert provider.model == OpenAIModels.GPT_4O
        assert provider.api_key == "test-api-key"
        assert provider.temperature == 0.7
        assert provider.max_tokens == 150
        assert provider.extra_kwargs == {}
        assert provider._llm_instance is None

    def test_initialization_with_custom_params(self, mock_settings, mock_chat_openai):
        """Test initialization with custom parameters."""
        custom_model = "custom-model"
        custom_api_key = "custom-api-key"
        custom_temp = 0.5
        custom_tokens = 200
        extra_kwargs = {"top_p": 0.9}

        provider = OpenAIProvider(
            model=custom_model,
            api_key=custom_api_key,
            temperature=custom_temp,
            max_tokens=custom_tokens,
            **extra_kwargs,
        )

        assert provider.model == custom_model
        assert provider.api_key == custom_api_key
        assert provider.temperature == custom_temp
        assert provider.max_tokens == custom_tokens
        assert provider.extra_kwargs == extra_kwargs

    def test_missing_api_key_raises_error(self, mock_settings):
        """Test that initialization fails when no API key is provided."""
        with patch("infra.llm.providers.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.OPENAI_API_KEY = None
            mock_get_settings.return_value = mock_settings

            with pytest.raises(
                ValueError,
                match="OpenAI API Key not provided or found in environment variables.",
            ):
                OpenAIProvider()

    def test_get_model_initializes_lazily(self, mock_settings, mock_chat_openai):
        """Test that get_model initializes the model lazily."""
        provider = OpenAIProvider()
        assert provider._llm_instance is None

        model = provider.get_model()
        assert model == mock_chat_openai.return_value
        mock_chat_openai.assert_called_once_with(
            api_key="test-api-key",
            model=OpenAIModels.GPT_4O,
            temperature=0.7,
        )

    def test_get_model_reuses_instance(self, mock_settings, mock_chat_openai):
        """Test that get_model reuses the initialized instance."""
        provider = OpenAIProvider()

        # First call initializes
        model1 = provider.get_model()
        # Second call should reuse
        model2 = provider.get_model()

        assert model1 == model2
        # ChatOpenAI should only be called once
        mock_chat_openai.assert_called_once()

    def test_initialize_model_error_handling(self, mock_settings, mock_chat_openai):
        """Test error handling in _initialize_model."""
        mock_chat_openai.side_effect = Exception("Test error")
        provider = OpenAIProvider()

        with pytest.raises(Exception, match="Test error"):
            provider.get_model()
