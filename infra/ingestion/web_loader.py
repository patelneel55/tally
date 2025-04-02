from infra.core.interfaces import IDocumentLoader
from infra.acquisition.models import AcquisitionOutput
from pydantic import BaseModel
from langchain_core.documents import Document
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
from enum import Enum
import logging
from typing import List, Callable, Optional

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

class WebLoader(IDocumentLoader):
    """
    A simple HTML loader that loads HTML documents from a given path (URL or local path)
    and scrapes all HTML information from the target including recursively following HTML
    links.

    """
    def __init__(self):
        pass

    async def load(self, sources: List[AcquisitionOutput], crawl_strategy = CrawlStrategy.SAME_DOMAIN) -> List[Document]:
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
                metadata = {
                    "source": url,
                }
                metadata.update(src.get_metadata())
                documents.append(Document(
                    page_content=content,
                    metadata=metadata
                ))

            return handle_page

        for source in sources:
            config = CrawlConfig(
                crawl_strategy=crawl_strategy,
                max_requests_per_crawl=200,
            )
            await self._crawl_url(source.get_uris(), config, process_urls(source))

        return documents
        

    async def _crawl_url(self, urls: List[str], config: CrawlConfig, handlePage: Callable[[str, str], None]) -> None:
        """
        Crawls the URL and calls the handlePage function with the URL and content.
        """
        crawler = PlaywrightCrawler(
            max_requests_per_crawl=config.max_requests_per_crawl,
        )

        @crawler.router.default_handler
        async def request_handler(context: PlaywrightCrawlingContext) -> None:
            logging.debug(f'Processing {context.request.url}...')
            await context.page.wait_for_load_state('networkidle')
            await context.enqueue_links(
                base_url=context.request.loaded_url,
                strategy=config.crawl_strategy,
            )
            handlePage(context.request.loaded_url or "", await context.page.content())

        await crawler.run(urls)
        logging.debug(f'Finished crawling {urls}.')