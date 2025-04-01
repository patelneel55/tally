import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Dict, Optional, Any


def get_with_retries(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
    retries: int = 3,
    backoff_factor: float = 1.0,
    status_forcelist: Optional[list] = None
) -> requests.Response:
    """
    Perform an HTTP GET request with retry logic using exponential backoff.
    
    Args:
        url: The URL to request
        headers: Optional HTTP headers to include
        params: Optional query parameters
        timeout: Request timeout in seconds
        retries: Maximum number of retries
        backoff_factor: Backoff factor for retries (wait will be: {backoff_factor} * (2 ** ({retry_count} - 1))
        status_forcelist: List of HTTP status codes to retry on (defaults to [429, 500, 502, 503, 504])
        
    Returns:
        Response object if successful
        
    Raises:
        requests.exceptions.RequestException: If all retries fail
    """
    # Default status codes to retry on if not provided
    if status_forcelist is None:
        status_forcelist = [429, 500, 502, 503, 504]
    
    # Configure retry strategy with exponential backoff
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=["GET"]
    )
    
    # Create a session and mount the retry adapter
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    try:
        # Make the request with configured retry logic
        response = session.get(
            url,
            headers=headers,
            params=params,
            timeout=timeout
        )
        
        # Raise an exception for 4XX/5XX responses that weren't retried
        response.raise_for_status()
        
        return response
    except requests.exceptions.RequestException as e:
        # Log the error (could be enhanced to use a proper logger)
        print(f"Error fetching {url}: {str(e)}")
        raise 