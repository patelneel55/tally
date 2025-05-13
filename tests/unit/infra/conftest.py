"""Common fixtures for all unit tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class MockCache:
    """Mock for the Cache class."""

    def __init__(self, *args, **kwargs):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def write(self, key, **kwargs):
        self.store[key] = kwargs


@pytest.fixture
def mock_sqlalchemy_engine(request):
    """Mock for the get_sqlalchemy_engine function.

    This fixture can be used across any test that needs to mock database access.
    """
    target = getattr(request, "param", "infra.databases.engine")
    with patch(f"{target}.get_sqlalchemy_engine") as mock:
        mock.return_value = MagicMock()
        yield mock


@pytest.fixture
def mock_cache(request):
    """Mock Cache implementation for testing.

    This fixture can be used across any test that uses the Cache class.
    """
    target = getattr(request, "param", "infra.databases.cache")
    with patch(f"{target}.Cache") as mock:
        mock_cache_instance = MagicMock()
        mock.return_value = mock_cache_instance
        yield mock_cache_instance


@pytest.fixture
def mock_settings(request):
    target = getattr(request, "param", "infra.config.settings")
    with patch(f"{target}.get_settings") as mock:
        settings = MagicMock()
        settings.SEC_API_KEY = "test_api_key"
        settings.SEC_API_CACHE_EXPIRATION = 3600
        settings.OPENAI_API_KEY = "test-api-key"
        mock.return_value = settings
        yield mock


@pytest.fixture
def mock_aiohttp_session():
    mock_response = MagicMock()
    mock_response.status = 404
    mock_response.text = AsyncMock(return_value="Not Found")

    # Create a fake context manager for session.get()
    mock_context_manager = MagicMock()
    mock_context_manager.__aenter__.return_value = mock_response
    mock_context_manager.__aexit__.return_value = AsyncMock()

    # Create a fake session
    mock_session = MagicMock()
    mock_session.get.return_value = mock_context_manager  # <- Important: NOT AsyncMock!

    # Patch ClientSession
    with patch(
        "infra.ingestion.sec_pdf_loader.aiohttp.ClientSession",
        return_value=mock_session,
    ):
        yield mock_session, mock_response
