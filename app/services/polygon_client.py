"""
Polygon.io API Client
------------------

This module provides direct access to various Polygon.io API endpoints
for retrieving market data, reference data, and company information.

What this file does:
1. Provides a reusable client for accessing Polygon.io API endpoints
2. Handles API authentication, error handling, and rate limiting
3. Standardizes API responses into consistent Python dictionaries
4. Centralizes Polygon.io API access for the application

How it fits in the architecture:
- Serves as a base client for Polygon.io data access
- Complements polygon_financials.py for non-financial data endpoints
- Provides company metadata needed for financial analysis context

Financial importance:
- Retrieves essential company information for proper financial analysis
- Enables lookups of ticker symbols, company details and market data
- Supports financial research with accurate company reference data
"""

import logging
import time
import requests
from typing import Dict, Any, Optional

from app.core.config import settings

# Set up logging
logger = logging.getLogger(__name__)

def get_ticker_details(ticker: str) -> Dict[str, Any]:
    """
    Get detailed information about a ticker symbol using Polygon.io's reference API.
    
    Args:
        ticker: The ticker symbol to look up (e.g., 'AAPL', 'MSFT')
        
    Returns:
        Dictionary containing ticker details including company name, description,
        industry, market cap, etc.
        
    Raises:
        ValueError: If the ticker is invalid or not found
        ConnectionError: If there's an issue connecting to the Polygon API
        Exception: For other API errors including rate limits
    """
    api_key = settings.POLYGON_API_KEY
    if not api_key:
        raise ValueError("Polygon API key not found in configuration")
    
    # Normalize ticker symbol
    ticker = ticker.upper().strip()
    
    # Construct the API URL
    base_url = "https://api.polygon.io"
    endpoint = f"/v3/reference/tickers/{ticker}"
    url = f"{base_url}{endpoint}"
    
    # Set up query parameters
    params = {"apiKey": api_key}
    
    try:
        # Make the API request
        logger.debug(f"Requesting ticker details for {ticker} from Polygon.io")
        response = requests.get(url, params=params, timeout=10)  # 10 second timeout
        
        # Handle rate limiting
        if response.status_code == 429:
            logger.warning("Polygon API rate limit reached, waiting and retrying...")
            time.sleep(1)  # Wait for 1 second before retrying
            response = requests.get(url, params=params, timeout=10)  # Also add timeout here
            
        # Raise exception for any HTTP errors
        response.raise_for_status()
        
        # Parse the JSON response
        data = response.json()
        
        # Check for API error in the response
        if "error" in data:
            raise Exception(f"Polygon API error: {data['error']}")
            
        # Return the results
        return data.get("results", {})
        
    except requests.exceptions.HTTPError as e:
        if response.status_code == 404:
            raise ValueError(f"Ticker {ticker} not found")
        elif response.status_code == 403:
            raise ValueError("Invalid Polygon API key or unauthorized access")
        else:
            logger.error(f"HTTP error during Polygon API request: {e}")
            raise ConnectionError(f"Failed to fetch ticker details: {e}")
    
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error during Polygon API request: {e}")
        raise ConnectionError(f"Could not connect to Polygon API: {e}")
    
    except Exception as e:
        logger.error(f"Unexpected error during Polygon API request: {e}")
        raise Exception(f"Failed to retrieve ticker details: {e}")

def get_fundamentals(ticker: str, use_v2: bool = False) -> Dict[str, Any]:
    """
    Get fundamental financial data for a ticker using Polygon.io's financials API.
    
    Args:
        ticker: The ticker symbol to look up (e.g., 'AAPL', 'MSFT')
        use_v2: Whether to use the v2 endpoint (default: False, uses vX)
        
    Returns:
        Dictionary containing financial fundamentals including TTM revenue, 
        net income, P/E ratio, and ROE. Returns the full parsed JSON response.
        
    Raises:
        ValueError: If the ticker is invalid or API key not found
        ConnectionError: If there's an issue connecting to the Polygon API
        Exception: For other API errors including rate limits
    """
    api_key = settings.POLYGON_API_KEY
    if not api_key:
        raise ValueError("Polygon API key not found in configuration")
    
    # Normalize ticker symbol
    ticker = ticker.upper().strip()
    
    # Construct the API URL - use vX endpoint by default, v2 as fallback
    base_url = "https://api.polygon.io"
    
    if use_v2:
        # Use the v2 endpoint (older version)
        endpoint = f"/v2/reference/financials/{ticker}"
        url = f"{base_url}{endpoint}"
        
        # Set up query parameters for v2
        params = {
            "apiKey": api_key,
            "limit": 1,                 # Only get the most recent report
            "type": "Q",                # Quarterly reports (Q for quarterly, A for annual)
            "sort": "reportPeriod"      # Sort by report period to get the most recent
        }
    else:
        # Use the vX endpoint (newer version)
        endpoint = f"/vX/reference/financials"
        url = f"{base_url}{endpoint}"
        
        # Set up query parameters for vX
        params = {
            "apiKey": api_key,
            "ticker": ticker,
            "limit": 1,                # Only get the most recent report
            "timeframe": "quarterly",  # Use quarterly data
            "include_sources": True,   # Include data sources information
            "sort": "period_of_report_date" # Sort by report date to get most recent
        }
    
    try:
        # Make the API request
        logger.debug(f"Requesting financial fundamentals for {ticker} from Polygon.io using {'v2' if use_v2 else 'vX'} endpoint")
        response = requests.get(url, params=params, timeout=15)  # 15 second timeout
        
        # Handle rate limiting
        if response.status_code == 429:
            logger.warning("Polygon API rate limit reached, waiting and retrying...")
            time.sleep(2)  # Wait for 2 seconds before retrying
            response = requests.get(url, params=params, timeout=15)
        
        # Raise exception for any HTTP errors
        response.raise_for_status()
        
        # Parse the JSON response
        data = response.json()
        
        # Check for API error in the response
        if "error" in data:
            logger.error(f"Polygon API error: {data['error']}")
            return {}
            
        # Check if results are empty
        results = data.get("results", [])
        if not results:
            logger.warning(f"No financial data found for {ticker}")
            return {}
        
        # Return the results dictionary directly - this will include all metrics
        # like TTM revenue, net income, P/E, ROE that will be accessed by get_financial_metric
        return data
        
    except requests.exceptions.HTTPError as e:
        if response.status_code == 404:
            logger.warning(f"Financial data for ticker {ticker} not found")
            return {}
        elif response.status_code == 403:
            raise ValueError("Invalid Polygon API key or unauthorized access")
        else:
            logger.error(f"HTTP error during Polygon API request: {e}")
            raise ConnectionError(f"Failed to fetch fundamentals: {e}")
    
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error during Polygon API request: {e}")
        raise ConnectionError(f"Could not connect to Polygon API: {e}")
    
    except requests.exceptions.Timeout as e:
        logger.error(f"Timeout error during Polygon API request: {e}")
        raise ConnectionError(f"Request to Polygon API timed out: {e}")
    
    except Exception as e:
        logger.error(f"Unexpected error during Polygon API request: {e}")
        raise Exception(f"Failed to retrieve fundamental data: {e}") 