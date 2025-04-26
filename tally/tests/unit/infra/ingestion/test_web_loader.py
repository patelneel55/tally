import pytest

from infra.ingestion.web_loader import CrawlConfig
from infra.ingestion.web_loader import CrawlStrategy
from infra.ingestion.web_loader import WebLoader


@pytest.mark.parametrize(
    ("mock_sqlalchemy_engine", "mock_cache"),
    [("infra.ingestion.web_loader", "infra.ingestion.web_loader")],
    indirect=True,
)
class TestWebLoader:
    """Tests for the WebLoader class."""

    def test_init_default_values(self, mock_sqlalchemy_engine, mock_cache):
        """Test initialization with default values."""
        loader = WebLoader()

        assert loader._config.crawl_strategy == CrawlStrategy.SAME_DOMAIN
        assert loader._config.max_requests_per_crawl == 200
        assert loader._config.max_crawl_depth == 1

    def test_init_custom_values(self, mock_sqlalchemy_engine, mock_cache):
        """Test initialization with custom values."""
        loader = WebLoader(
            crawl_strategy=CrawlStrategy.SAME_HOSTNAME,
            max_requests_per_crawl=50,
            max_crawl_depth=2,
        )

        assert loader._config.crawl_strategy == CrawlStrategy.SAME_HOSTNAME
        assert loader._config.max_requests_per_crawl == 50
        assert loader._config.max_crawl_depth == 2

    def test_crawl_config_model(self, mock_sqlalchemy_engine, mock_cache):
        """Test the CrawlConfig model."""
        config = CrawlConfig()
        assert config.crawl_strategy == CrawlStrategy.SAME_DOMAIN
        assert config.max_requests_per_crawl == 200
        assert config.max_crawl_depth == 1

        custom_config = CrawlConfig(
            crawl_strategy=CrawlStrategy.ALL,
            max_requests_per_crawl=100,
            max_crawl_depth=3,
        )
        assert custom_config.crawl_strategy == CrawlStrategy.ALL
        assert custom_config.max_requests_per_crawl == 100
        assert custom_config.max_crawl_depth == 3
