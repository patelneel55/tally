import infra.core as core
from infra.acquisition.models import AcquisitionOutput
from pydantic import List, BaseModel
from langchain_core.documents import Document
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
from enum import Enum
import logging

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
    globs: List[str]

class HTMLLoader(core.IDocumentLoader):
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

        def handle_page(url: str, content: str) -> None:
            metadata = {
                "source": url,
                "content_type": "text/html"
            }
            documents.append(Document(
                page_content=content,
                metadata={
                    "source": url,
                    "content_type": "text/html"
                }
            ))

        for source in sources:
            config = CrawlConfig(
                crawl_strategy=crawl_strategy,
                max_requests_per_crawl=200,
                globs=[source.path]
            )
            await self._crawl_url(source.get_uris(), config, handle_page)

        return documents
        

    async def _crawl_url(self, urls: List[str], config: CrawlConfig, handlePage: callable[[str, str], None]) -> None:
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
            context.enqueue_links(
                base_url=context.request.loadedUrl,
                strategy=config.crawl_strategy,
                globs=config.globs
            )
            await handlePage(context.request.loadedUrl or "", await context.page.content())

        await crawler.run(urls)
        logging.debug(f'Finished crawling {urls}.')