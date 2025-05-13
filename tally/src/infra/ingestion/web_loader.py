import logging
import pickle
from enum import Enum
from typing import Callable, List

from crawlee import ConcurrencySettings
from crawlee.crawlers import (
    PlaywrightCrawler,
    PlaywrightCrawlingContext,
    PlaywrightPreNavCrawlingContext,
)
from langchain_core.documents import Document
from pydantic import BaseModel
from sqlalchemy import Integer, PickleType, UnicodeText
from sqlalchemy.orm import mapped_column

from infra.acquisition.models import AcquisitionOutput
from infra.databases.cache import Cache
from infra.databases.engine import get_sqlalchemy_engine
from infra.ingestion.models import IDocumentLoader


# Set up logging
logger = logging.getLogger(__name__)


class CrawlStrategy(str, Enum):
    SAME_HOSTNAME = "same-hostname"
    SAME_DOMAIN = "same-domain"
    SAME_ORIGIN = "same-origin"
    DIRECT_LINKS = "direct-links"
    ALL = "all"


class CrawlConfig(BaseModel):
    crawl_strategy: CrawlStrategy = CrawlStrategy.SAME_DOMAIN
    max_requests_per_crawl: int = 200
    max_crawl_depth: int = 1


class WebLoader(IDocumentLoader):
    """
    A simple HTML loader that loads HTML documents from a given path (URL or local path)
    and scrapes all HTML information from the target including recursively following HTML
    links.

    """

    _CACHE_COLUMNS = {
        "headers": mapped_column(PickleType, nullable=False),
        "status_code": mapped_column(Integer, nullable=False),
        "body": mapped_column(UnicodeText, nullable=True),
    }

    def __init__(
        self,
        crawl_strategy: CrawlStrategy = CrawlStrategy.SAME_DOMAIN,
        max_requests_per_crawl: int = 200,
        max_crawl_depth: int = 1,
    ):
        """
        Initializes the WebLoader with the specified crawl strategy and maximum requests per crawl.
        """
        self._config = CrawlConfig(
            crawl_strategy=crawl_strategy,
            max_requests_per_crawl=max_requests_per_crawl,
            max_crawl_depth=max_crawl_depth,
        )
        self._cache = Cache(
            engine=get_sqlalchemy_engine(),
            table_name="web_loader",
            column_mapping=self._CACHE_COLUMNS,
        )

    async def load(self, sources: List[AcquisitionOutput]) -> List[Document]:
        """
        Loads the HTML document from the specified sources and returns a list of
        Document objects.
        """
        documents = []

        def process_urls(src: AcquisitionOutput) -> Callable[[str, str], None]:
            """
            Processes the URLs and returns a function to handle the page content.
            """

            def handle_page(url: str, content: str) -> None:
                # Process the page content here
                metadata = src.get_metadata()
                # metadata.source = url
                documents.append(Document(page_content=content, metadata=metadata))

            return handle_page

        for source in sources:
            await self._crawl_url(source.get_uris(), self._config, process_urls(source))

        return documents

    def _cache_hook(self):
        async def _prenav_cache_hook(context: PlaywrightPreNavCrawlingContext) -> None:
            url = context.request.url
            cache_entry = self._cache.get(url)
            if cache_entry:
                context.request.user_data["cached"] = True

                # Create a route handler function that will intercept the request
                async def route_handler(route, request):
                    logger.debug(f"Intercepting {url} and returning cached response")
                    await route.fulfill(
                        status=cache_entry["status_code"],
                        headers=pickle.loads(cache_entry["headers"]),
                        body=cache_entry["body"],
                    )

                # Register a route for the exact URL to intercept the navigation
                await context.page.route(url, route_handler)
                return

        return _prenav_cache_hook

    async def _crawl_url(
        self,
        urls: List[str],
        config: CrawlConfig,
        handlePage: Callable[[str, str], None],
    ) -> None:
        """
        Crawls the URL and calls the handlePage function with the URL and content.
        """
        crawler = PlaywrightCrawler(
            max_requests_per_crawl=config.max_requests_per_crawl,
            max_crawl_depth=config.max_crawl_depth,
            concurrency_settings=ConcurrencySettings(
                max_tasks_per_minute=600,
            ),
        )
        # Add prenavigation hook to check for cache, if exists
        # it should return the cached value instead
        crawler.pre_navigation_hook(self._cache_hook())

        @crawler.router.default_handler
        async def request_handler(context: PlaywrightCrawlingContext) -> None:
            logging.debug(f"Processing {context.request.url}...")
            await context.page.wait_for_load_state("networkidle")
            await context.enqueue_links(
                base_url=context.request.loaded_url,
                strategy=config.crawl_strategy,
            )
            url = context.request.loaded_url
            content = await context.page.content()

            # Call the handler
            handlePage(url, content)

            if not context.request.user_data.get("cached", False):
                self._cache.write(
                    url,
                    ttl=60 * 60 * 24,
                    status_code=context.response.status,
                    headers=pickle.dumps(await context.response.all_headers()),
                    body=content,
                )

        await crawler.run(urls)
        logging.debug(f"Finished crawling {urls}.")
