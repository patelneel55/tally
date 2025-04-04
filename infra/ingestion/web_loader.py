from infra.core.interfaces import IDocumentLoader
from infra.acquisition.models import AcquisitionOutput
from pydantic import BaseModel
from langchain_core.documents import Document
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
from crawlee import ConcurrencySettings
from enum import Enum
import logging
from typing import List, Callable, Optional, Dict, Any
import os
import json
import hashlib
from pathlib import Path
import time

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
    def __init__(self, crawl_strategy: CrawlStrategy = CrawlStrategy.SAME_DOMAIN, max_requests_per_crawl: int = 200, max_crawl_depth: int = 1):
        """
        Initializes the WebLoader with the specified crawl strategy and maximum requests per crawl.
        """
        self._config = CrawlConfig(
            crawl_strategy=crawl_strategy,
            max_requests_per_crawl=max_requests_per_crawl,
            max_crawl_depth=max_crawl_depth
        )
        self.cache_dir = Path("cache/web_loader")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        

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
            await self._crawl_url(source.get_uris(), self._config, process_urls(source))

        return documents
    
    def _generate_cache_key(self, url: str, config: CrawlConfig) -> str:
        """
        Generate a unique cache key based on URLs and crawl configuration.
        
        Args:
            urls: List of URLs to crawl
            config: Crawl configuration
            
        Returns:
            A unique cache key
        """
        # Create a string representation of the URLs and config
        config_str = f"{config.crawl_strategy}_{config.max_requests_per_crawl}_{config.max_crawl_depth}"
        
        # Create a hash of the combined string
        key_str = f"{url}_{config_str}"
        return hashlib.md5(key_str.encode("utf-8")).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> str:
        """
        Get the path to the cache file for a given cache key.
        
        Args:
            cache_key: Cache key
            
        Returns:
            Path to cache file
        """
        return os.path.join(self.cache_dir, f"{cache_key}.json")
    
    def _save_to_cache(self, cache_key: str, crawled_data: Dict[str, str]) -> None:
        """
        Save crawled data to cache.
        
        Args:
            cache_key: Cache key
            crawled_data: Dictionary mapping URLs to page content
        """
        if not self.use_cache:
            return
            
        cache_path = self._get_cache_path(cache_key)
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(crawled_data, f)
            logger.info(f"Saved crawled data to cache: {cache_path}")
        except Exception as e:
            logger.error(f"Error saving to cache file {cache_path}: {str(e)}")
    
    def _load_from_cache(self, cache_key: str) -> Optional[Dict[str, str]]:
        """
        Load crawled data from cache.
        
        Args:
            cache_key: Cache key
            
        Returns:
            Dictionary mapping URLs to page content, or None if cache is invalid
        """
        if not self.use_cache:
            return None
            
        cache_path = self._get_cache_path(cache_key)
        if not self._is_cache_valid(cache_path):
            return None
            
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"Loaded crawled data from cache: {cache_path}")
            return data
        except Exception as e:
            logger.error(f"Error loading cache file {cache_path}: {str(e)}")
            return None

    async def _crawl_url(self, urls: List[str], config: CrawlConfig, handlePage: Callable[[str, str], None]) -> None:
        """
        Crawls the URL and calls the handlePage function with the URL and content.
        """
        # cache_key = self._generate_cache_key(urls, config)
        
        # # Try to load from cache first
        # cached_data = self._load_from_cache(cache_key)
        # if cached_data:
        #     logger.info(f"Using cached data for URLs: {urls}")
        #     for url, content in cached_data.items():
        #         handlePage(url, content)
        #     return
            
        # # If not in cache, perform the crawl
        # logger.info(f"Cache miss for URLs: {urls}, performing crawl")
        # crawled_data = {}
        
        crawler = PlaywrightCrawler(
            max_requests_per_crawl=config.max_requests_per_crawl,
            max_crawl_depth=config.max_crawl_depth,
            concurrency_settings=ConcurrencySettings(
                # min_concurrency=1,
                # max_concurrency=10,
                 # Set the maximum number of tasks per minute
                 # to avoid overloading the server
                 #  100 tasks per minute
                 #  100 tasks per minute
                 #  100 tasks per minute
                max_tasks_per_minute=600,
            ),
        )

        @crawler.router.default_handler
        async def request_handler(context: PlaywrightCrawlingContext) -> None:
            logging.debug(f'Processing {context.request.url}...')
            await context.page.wait_for_load_state('networkidle')
            await context.enqueue_links(
                base_url=context.request.loaded_url,
                strategy=config.crawl_strategy,
            )
            url = context.request.loaded_url or ""
            content = await context.page.content()
            
            # Call the handler
            handlePage(url, content)
            
            # Save to our crawled data dictionary for caching
            # crawled_data[url] = content

        await crawler.run(urls)
        logging.debug(f'Finished crawling {urls}.')
        
        # # Save the crawled data to cache
        # self._save_to_cache(cache_key, crawled_data)