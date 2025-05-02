from unittest.mock import MagicMock, patch

import pytest
from langchain_core.embeddings import Embeddings

from infra.embeddings.models import OpenAIEmbeddingModels
from infra.embeddings.providers import OpenAIEmbeddingProvider


@pytest.mark.parametrize("mock_settings", ["infra.embeddings.providers"], indirect=True)
class TestOpenAIEmbeddingProvider:
    """Test suite for OpenAIEmbeddingProvider class."""

    @pytest.fixture
    def mock_openai_embeddings(self):
        """Fixture to mock OpenAIEmbeddings class."""
        with patch("infra.embeddings.providers.OpenAIEmbeddings") as mock:
            mock_instance = MagicMock(spec=Embeddings)
            mock.return_value = mock_instance
            yield mock

    def test_initialization_with_defaults(self, mock_settings, mock_openai_embeddings):
        """Test initialization with default parameters."""
        provider = OpenAIEmbeddingProvider()

        assert provider.model == OpenAIEmbeddingModels.SMALL3
        assert provider.api_key == "test-api-key"
        mock_openai_embeddings.assert_called_once_with(
            model=OpenAIEmbeddingModels.SMALL3, api_key="test-api-key"
        )

    def test_initialization_with_custom_params(
        self, mock_settings, mock_openai_embeddings
    ):
        """Test initialization with custom parameters."""
        custom_model = "custom-model"
        custom_api_key = "custom-api-key"

        provider = OpenAIEmbeddingProvider(model=custom_model, api_key=custom_api_key)

        assert provider.model == custom_model
        assert provider.api_key == custom_api_key
        mock_openai_embeddings.assert_called_once_with(
            model=custom_model, api_key=custom_api_key
        )

    def test_missing_api_key_raises_error(self, mock_settings):
        """Test that initialization fails when no API key is provided."""
        with patch("infra.embeddings.providers.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.OPENAI_API_KEY = None
            mock_get_settings.return_value = mock_settings

            with pytest.raises(
                ValueError,
                match="OpenAI API Key not provided or found in environment variables.",
            ):
                OpenAIEmbeddingProvider()

    def test_get_embedding_model(self, mock_settings, mock_openai_embeddings):
        """Test that get_embedding_model returns the correct embedding model instance."""
        provider = OpenAIEmbeddingProvider()
        embedding_model = provider.get_embedding_model()

        assert embedding_model == mock_openai_embeddings()
