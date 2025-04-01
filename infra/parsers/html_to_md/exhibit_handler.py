import os
import re
import logging
import requests
from typing import List, Tuple, Dict, Callable, Optional
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup

from html_to_md.config import get_sec_api_key
from html_to_md.http_utils import get_with_retries

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# SEC API constants
SEC_API_BASE_URL = "https://api.sec-api.io/filing-doc"


def extract_exhibit_links(html: str, base_url: str) -> List[Tuple[str, str]]:
    """
    Extract links to exhibits from HTML content.
    
    Args:
        html: HTML content to parse
        base_url: Base URL to resolve relative URLs
        
    Returns:
        List of tuples containing (title, url) for each exhibit link
    """
    soup = BeautifulSoup(html, 'html.parser')
    exhibit_links = []
    
    for a_tag in soup.find_all('a', href=True):
        href = a_tag.get('href', '')
        if (
            'exhibit' in href.lower() or 
            href.lower().endswith(('.htm', '.html', '.txt'))
        ):
            # Construct full URL if relative
            full_url = urljoin(base_url, href)
            # Extract link text
            link_text = a_tag.get_text(strip=True)
            if link_text:
                exhibit_links.append((link_text, full_url))
                
    return exhibit_links


def parse_exhibit_links(html: str, base_url: str) -> List[Dict[str, str]]:
    """
    Parse exhibit links from HTML content and return structured data.
    
    Args:
        html: HTML content to parse
        base_url: Base URL to resolve relative URLs
        
    Returns:
        List of dictionaries with 'title' and 'url' for each exhibit link
    """
    exhibits = []
    
    # Get raw links
    raw_links = extract_exhibit_links(html, base_url)
    
    # Convert to dictionary format
    for title, url in raw_links:
        exhibits.append({
            'title': title,
            'url': url
        })
    
    logger.info(f"Found {len(exhibits)} exhibit links in document")
    return exhibits


def _parse_sec_url(url: str) -> Optional[Dict[str, str]]:
    """
    Parse an SEC URL to extract accession number and document name.
    
    Args:
        url: Original SEC URL to parse
        
    Returns:
        Dictionary with 'accessionNo' and 'document' if parsing successful, None otherwise
    """
    try:
        # Parse the URL
        parsed_url = urlparse(url)
        
        # Different patterns based on URL format
        if '/Archives/' in url:
            # Format: https://www.sec.gov/Archives/edgar/data/1318605/000156459022027165/tsla-ex991_254.htm
            path_parts = parsed_url.path.split('/')
            if len(path_parts) >= 5:
                accession_index = -2
                document_index = -1
                
                # The accession number is in the path
                accession_no = path_parts[accession_index]
                # The document name is the last part
                document = path_parts[document_index]
                
                return {
                    'accessionNo': accession_no,
                    'document': document
                }
        
        # Check for query parameters (some SEC URLs use query params)
        if parsed_url.query:
            query_params = parse_qs(parsed_url.query)
            
            # Try to get accessionNo and document from query params
            accession_no = query_params.get('accessionNumber', [None])[0]
            document = query_params.get('doc', [None])[0] or query_params.get('document', [None])[0]
            
            if accession_no and document:
                return {
                    'accessionNo': accession_no,
                    'document': document
                }
        
        # Failed to parse with the above patterns
        logger.warning(f"Could not extract accessionNo and document from URL: {url}")
        return None
        
    except Exception as e:
        logger.error(f"Error parsing SEC URL {url}: {str(e)}")
        return None


def fetch_exhibits(exhibit_links: List[Dict[str, str]], 
                   output_dir: str = None) -> List[Dict]:
    """
    Fetch exhibits from SEC using the provided links.
    
    Args:
        exhibit_links: List of dictionaries with 'title' and 'url' for each exhibit
        output_dir: Directory to save raw exhibits (optional)
        
    Returns:
        List of dictionaries with exhibit information including HTML content
    """
    results = []
    
    # Create output directory if provided
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # Get SEC API key for API requests
    try:
        sec_api_key = get_sec_api_key()
    except ValueError as e:
        logger.error(f"SEC API key not available: {str(e)}")
        # Return basic info without content if we can't authenticate
        return [
            {
                "title": link["title"], 
                "url": link["url"], 
                "html": "", 
                "error": "SEC API key not configured"
            } 
            for link in exhibit_links
        ]
    
    # Set up headers for SEC API
    headers = {
        "Authorization": f"Bearer {sec_api_key}",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    
    for link in exhibit_links:
        title = link["title"]
        url = link["url"]
        
        try:
            # Parse the SEC URL to get accession number and document
            sec_params = _parse_sec_url(url)
            
            if sec_params:
                # Use SEC API with parsed parameters
                logger.info(f"Fetching exhibit from SEC API: {title} ({url})")
                
                # Make the API request using get_with_retries for resilience
                response = get_with_retries(
                    url=SEC_API_BASE_URL,
                    headers=headers,
                    params={
                        'accessionNo': sec_params['accessionNo'],
                        'document': sec_params['document']
                    },
                    timeout=30,  # Increased timeout for potentially large documents
                    retries=3,
                    backoff_factor=1.0
                )
                
                content = response.text
                
                # Save raw file if output_dir provided
                if output_dir:
                    # Generate safe filename based on title
                    safe_title = re.sub(r'[^\w\-\.]', '_', title)
                    
                    # Determine file extension based on content type
                    content_type = response.headers.get('Content-Type', '').lower()
                    if 'text/html' in content_type or sec_params['document'].lower().endswith(('.htm', '.html')):
                        ext = ".html"
                    elif 'text/plain' in content_type or sec_params['document'].lower().endswith('.txt'):
                        ext = ".txt"
                    else:
                        ext = ""
                    
                    # Save raw file
                    raw_path = os.path.join(output_dir, f"{safe_title}{ext}")
                    with open(raw_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                
                results.append({
                    "title": title,
                    "url": url,
                    "html": content
                })
            else:
                # Couldn't parse the URL, fall back to direct request
                logger.warning(f"Using direct request (not SEC API) for: {title} ({url})")
                
                # Use get_with_retries for direct request too
                response = get_with_retries(
                    url=url,
                    timeout=30,
                    retries=2,
                    backoff_factor=0.5
                )
                
                content = response.text
                
                # Save raw file if output_dir provided
                if output_dir:
                    # Generate safe filename based on title
                    safe_title = re.sub(r'[^\w\-\.]', '_', title)
                    
                    # Determine file extension based on content type
                    content_type = response.headers.get('Content-Type', '').lower()
                    if 'text/html' in content_type or url.lower().endswith(('.htm', '.html')):
                        ext = ".html"
                    elif 'text/plain' in content_type or url.lower().endswith('.txt'):
                        ext = ".txt"
                    else:
                        ext = ""
                    
                    # Save raw file
                    raw_path = os.path.join(output_dir, f"{safe_title}{ext}")
                    with open(raw_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                
                results.append({
                    "title": title,
                    "url": url,
                    "html": content
                })
            
        except Exception as e:
            # Log the error and continue with next exhibit
            error_msg = f"Error processing {url}: {str(e)}"
            logger.error(error_msg)
            results.append({
                "title": title,
                "url": url,
                "html": "",
                "error": str(e)
            })
    
    logger.info(f"Successfully fetched {len(results)} exhibits")
    return results


def fetch_and_parse_exhibits(exhibit_links: List[Tuple[str, str]], output_dir: str, parser_fn: Callable[[str], str]) -> List[Dict]:
    """
    Fetch and parse exhibit files, converting them to markdown using SEC-API.
    
    Args:
        exhibit_links: List of (title, url) tuples for exhibits
        output_dir: Directory to save output files (can be empty string if no saving is needed)
        parser_fn: Function to parse HTML/text to markdown
        
    Returns:
        List of dictionaries with information about each exhibit
    """
    # Only create directories if output_dir is provided
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    results = []
    
    # Get SEC API key for API requests
    try:
        sec_api_key = get_sec_api_key()
    except ValueError as e:
        logger.error(f"SEC API key not available: {str(e)}")
        # Return empty results if we can't authenticate
        return [{"title": title, "url": url, "markdown": None, "error": "SEC API key not configured"} 
                for title, url in exhibit_links]
    
    # Set up headers for SEC API
    headers = {
        "Authorization": f"Bearer {sec_api_key}",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    
    for title, url in exhibit_links:
        try:
            # Parse the SEC URL to get accession number and document
            sec_params = _parse_sec_url(url)
            
            if sec_params:
                # Use SEC API with parsed parameters
                logger.info(f"Fetching exhibit from SEC API: {title} ({url})")
                
                # Make the API request using get_with_retries for resilience
                response = get_with_retries(
                    url=SEC_API_BASE_URL,
                    headers=headers,
                    params={
                        'accessionNo': sec_params['accessionNo'],
                        'document': sec_params['document']
                    },
                    timeout=30,  # Increased timeout for potentially large documents
                    retries=3,
                    backoff_factor=1.0
                )
                
                content = response.text
                markdown = None
                
                # Determine content type and process accordingly
                content_type = response.headers.get('Content-Type', '').lower()
                is_html = 'text/html' in content_type or sec_params['document'].lower().endswith(('.htm', '.html'))
                is_text = 'text/plain' in content_type or sec_params['document'].lower().endswith('.txt')
                
                # Only save files if output_dir is provided
                if output_dir:
                    # Generate safe filename based on title
                    safe_title = re.sub(r'[^\w\-\.]', '_', title)
                    
                    if is_html:
                        # Save raw HTML
                        raw_path = os.path.join(output_dir, f"{safe_title}.html")
                        with open(raw_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                    elif is_text:
                        # Save raw text
                        raw_path = os.path.join(output_dir, f"{safe_title}.txt")
                        with open(raw_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                    else:
                        # For other file types, just save as is
                        raw_path = os.path.join(output_dir, safe_title)
                        with open(raw_path, 'wb') as f:
                            f.write(response.content)
                
                # Convert to markdown regardless of whether we're saving
                if is_html or is_text:
                    markdown = parser_fn(content)
                    
                    # Save markdown version if output_dir is provided
                    if output_dir:
                        md_path = os.path.join(output_dir, f"{safe_title}.md")
                        with open(md_path, 'w', encoding='utf-8') as f:
                            f.write(markdown)
                
                logger.info(f"Successfully processed exhibit: {title}")
                results.append({
                    "title": title,
                    "url": url,
                    "markdown": markdown
                })
            else:
                # Couldn't parse the URL, fall back to direct request (legacy behavior)
                logger.warning(f"Using direct request (not SEC API) for: {title} ({url})")
                
                # Use get_with_retries for direct request too
                response = get_with_retries(
                    url=url,
                    timeout=30,
                    retries=2,
                    backoff_factor=0.5
                )
                
                content = response.text
                markdown = None
                
                # Determine content type and process accordingly
                content_type = response.headers.get('Content-Type', '').lower()
                is_html = 'text/html' in content_type or url.lower().endswith(('.htm', '.html'))
                is_text = 'text/plain' in content_type or url.lower().endswith('.txt')
                
                # Only save files if output_dir is provided
                if output_dir:
                    # Generate safe filename based on title
                    safe_title = re.sub(r'[^\w\-\.]', '_', title)
                    
                    if is_html:
                        # Save raw HTML
                        raw_path = os.path.join(output_dir, f"{safe_title}.html")
                        with open(raw_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                    elif is_text:
                        # Save raw text
                        raw_path = os.path.join(output_dir, f"{safe_title}.txt")
                        with open(raw_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                    else:
                        # For other file types, just save as is
                        raw_path = os.path.join(output_dir, safe_title)
                        with open(raw_path, 'wb') as f:
                            f.write(response.content)
                
                # Convert to markdown regardless of whether we're saving
                if is_html or is_text:
                    markdown = parser_fn(content)
                    
                    # Save markdown version if output_dir is provided
                    if output_dir:
                        md_path = os.path.join(output_dir, f"{safe_title}.md")
                        with open(md_path, 'w', encoding='utf-8') as f:
                            f.write(markdown)
                
                logger.info(f"Successfully processed exhibit (direct request): {title}")
                results.append({
                    "title": title,
                    "url": url,
                    "markdown": markdown
                })
            
        except Exception as e:
            # Log the error and continue with next exhibit
            error_msg = f"Error processing {url}: {str(e)}"
            logger.error(error_msg)
            results.append({
                "title": title,
                "url": url,
                "markdown": None,
                "error": str(e)
            })
    
    return results 