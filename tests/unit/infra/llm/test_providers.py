from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.language_models import BaseLanguageModel
from langchain_openai import ChatOpenAI

from infra.llm.models import OpenAIModels, RateLimitType
from infra.llm.providers import OpenAIProvider


@pytest.mark.parametrize("mock_settings", ["infra.llm.providers"], indirect=True)
class TestOpenAIProvider:
    """Test suite for OpenAIProvider class."""

    @pytest.fixture
    def mock_chat_openai(self):
        """Fixture to mock ChatOpenAI class."""
        with patch("langchain_openai.ChatOpenAI") as mock:
            mock_instance = MagicMock(spec=BaseLanguageModel)
            mock.return_value = mock_instance
            yield mock

    @pytest.fixture
    def mock_tiktoken(self):
        """Fixture to mock tiktoken."""
        with patch("tiktoken.encoding_for_model") as mock_encoding:
            mock_encoder = MagicMock()
            mock_encoder.encode.return_value = [1, 2, 3]  # Simulating tokens
            mock_encoding.return_value = mock_encoder
            yield mock_encoding

    def test_initialization_with_defaults(self, mock_settings, mock_chat_openai):
        """Test initialization with default parameters."""
        provider = OpenAIProvider()

        assert provider._model == OpenAIModels.GPT_O4_MINI
        assert provider._max_tokens == 4096

    def test_initialization_with_custom_params(self, mock_settings, mock_chat_openai):
        """Test initialization with custom parameters."""
        custom_model = OpenAIModels.GPT_4O
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

        assert provider._model == custom_model
        assert provider._max_tokens == custom_tokens

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

    def test_initialize_model_error_handling(self, mock_settings):
        """Test error handling in model initialization."""
        with patch("langchain_openai.ChatOpenAI.__init__") as mock_init:
            mock_init.side_effect = Exception("Test error")

            with pytest.raises(Exception, match="Test error"):
                OpenAIProvider()

    def test_estimate_tokens(self, mock_settings, mock_chat_openai, mock_tiktoken):
        """Test the estimate_tokens method."""
        provider = OpenAIProvider(max_tokens=100)
        text = "This is a test"

        token_count = provider.estimate_tokens(text)

        # Should return the length of encoded tokens + max_tokens
        assert token_count == 3 + 100
        mock_tiktoken.assert_called_once_with(provider._model.value)

    def test_estimate_tokens_fallback(self, mock_settings, mock_chat_openai):
        """Test the estimate_tokens method fallback when model isn't recognized."""
        provider = OpenAIProvider(max_tokens=100)
        text = "This is a test"

        with patch("tiktoken.encoding_for_model") as mock_encoding_for_model:
            mock_encoding_for_model.side_effect = KeyError("Model not found")
            with patch("tiktoken.get_encoding") as mock_get_encoding:
                mock_encoder = MagicMock()
                mock_encoder.encode.return_value = [1, 2, 3, 4]
                mock_get_encoding.return_value = mock_encoder

                token_count = provider.estimate_tokens(text)

                assert token_count == 4 + 100
                mock_get_encoding.assert_called_once_with("cl100k_base")

    @pytest.mark.asyncio
    async def test_ainvoke_with_rate_limiting(
        self, mock_settings, mock_chat_openai, mock_tiktoken
    ):
        """Test the ainvoke method with rate limiting."""
        # Setup a mock rate limiter with async acquire method
        mock_rate_limiter = MagicMock()
        mock_rate_limiter.acquire = AsyncMock(return_value=None)

        # Create a mock model with rate_limiter
        mock_model = MagicMock()
        mock_model.rate_limiter = mock_rate_limiter
        mock_model.value = OpenAIModels.GPT_O4_MINI.value

        # Create a custom provider class with our mocked model
        class TestProvider(OpenAIProvider):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._model = mock_model

            def estimate_tokens(self, text):
                return 4099

        # Create an instance of our test provider
        provider = TestProvider()

        # Mock the parent ainvoke method
        with patch.object(ChatOpenAI, "ainvoke", AsyncMock(return_value="response")):
            # Call the method under test
            result = await provider.ainvoke("Test prompt")

            # Verify rate limiter was called correctly
            mock_rate_limiter.acquire.assert_awaited_once_with(
                [
                    (RateLimitType.REQUEST_LIMIT.value, 1),
                    (RateLimitType.TOKEN_LIMIT.value, 4099),
                ]
            )

            # Verify the result
            assert result == "response"

    @pytest.mark.asyncio
    async def test_ainvoke_without_rate_limiting(
        self, mock_settings, mock_chat_openai, mock_tiktoken
    ):
        """Test the ainvoke method without rate limiting."""
        # Create a mock model without rate_limiter
        mock_model = MagicMock()
        mock_model.rate_limiter = None
        mock_model.value = OpenAIModels.GPT_O4_MINI.value

        # Create a custom provider class with our mocked model
        class TestProvider(OpenAIProvider):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._model = mock_model

            def estimate_tokens(self, text):
                return 4099

        # Create an instance of our test provider
        provider = TestProvider()

        # Mock the parent ainvoke method
        with patch.object(
            ChatOpenAI, "ainvoke", AsyncMock(return_value="response")
        ) as mock_parent_ainvoke:
            # Call the method under test
            result = await provider.ainvoke("Test prompt")

            # Verify parent method was called without using rate limiting
            mock_parent_ainvoke.assert_awaited_once_with("Test prompt")
            assert result == "response"
