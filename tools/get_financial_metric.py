"""
Financial Metric Tool for Analyst AI.

This module provides functions to retrieve financial metrics for given tickers
using the Polygon.io API through the polygon_client module.
"""
from typing import Dict, Union, Any, List, Callable
from functools import reduce

from ai_analyst.app.services.polygon_client import get_ticker_details, get_fundamentals

# Define a metric mapping to handle different data sources and paths
metric_map = {
    # Basic company information from ticker details endpoint
    "name": {"source": "details", "path": ["name"]},
    "market_cap": {"source": "details", "path": ["market_cap"]},
    "total_employees": {"source": "details", "path": ["total_employees"]},
    
    # Financial metrics from fundamentals vX endpoint
    "net_income": {"source": "fundamentals", "path": ["results", 0, "financials", "income_statement", "net_income_loss"]},
    "revenue": {"source": "fundamentals", "path": ["results", 0, "financials", "income_statement", "revenues"]},
    "roe": {"source": "fundamentals", "path": ["results", 0, "financials", "ratios", "return_on_equity"]},
    "pe_ratio": {"source": "fundamentals", "path": ["results", 0, "financials", "ratios", "pe_ratio"]},
    
    # For backward compatibility - using different naming
    "total_revenue": {"source": "fundamentals", "path": ["results", 0, "financials", "income_statement", "revenues"]},
    "price_to_book": {"source": "fundamentals", "path": ["results", 0, "financials", "ratios", "price_to_book_value"]},
    "eps": {"source": "fundamentals", "path": ["results", 0, "financials", "ratios", "earnings_per_basic_share"]},
    "total_assets": {"source": "fundamentals", "path": ["results", 0, "financials", "balance_sheet", "assets"]},
    "total_liabilities": {"source": "fundamentals", "path": ["results", 0, "financials", "balance_sheet", "liabilities"]}
}

def get_nested_value(data: Dict[str, Any], path: List[str], default: Any = "N/A") -> Any:
    """
    Safely extract a value from a nested dictionary using a path list.
    
    Args:
        data: Dictionary to extract value from
        path: List of keys defining the path to the value
        default: Default value to return if path doesn't exist
        
    Returns:
        The value at the specified path, or the default if not found
    """
    try:
        return reduce(lambda d, k: d.get(k, {}) if isinstance(d, dict) else {}, path[:-1], data).get(path[-1], default)
    except (AttributeError, TypeError, IndexError):
        return default


def get_financial_metric(ticker: str, metric: str) -> Dict[str, Union[float, str, int]]:
    """
    Retrieve a specific financial metric for a given ticker using Polygon.io API.
    
    Args:
        ticker (str): The stock ticker symbol (e.g., 'AAPL', 'JPM')
        metric (str): The financial metric to retrieve (e.g., 'name', 'market_cap', 'pe_ratio', 'revenue', 'net_income', 'roe')
        
    Returns:
        dict: A dictionary containing:
            - 'value': The metric value (could be string, float, or int depending on metric)
            - 'ticker': The ticker symbol provided
            - 'metric': The metric name provided
            - 'error': Error message if any
    
    Example:
        >>> get_financial_metric('AAPL', 'name')
        {'value': 'Apple Inc.', 'ticker': 'AAPL', 'metric': 'name'}
        
        >>> get_financial_metric('AAPL', 'revenue')
        {'value': 394328000000, 'ticker': 'AAPL', 'metric': 'revenue'}
    """
    # Convert ticker to uppercase for consistency
    ticker = ticker.upper().strip()
    # Keep metric lowercase for matching with our metric map
    metric = metric.lower().strip()
    
    # Check if the requested metric is supported
    if metric not in metric_map:
        return {
            'value': 'N/A',
            'ticker': ticker,
            'metric': metric,
            'error': f'Unsupported metric. Supported metrics: {", ".join(metric_map.keys())}'
        }
    
    try:
        # Get the metric mapping details
        metric_info = metric_map[metric]
        data_source = metric_info["source"]
        value_path = metric_info["path"]
        
        # Fetch data based on the source
        if data_source == "details":
            # Get data from ticker details endpoint
            data = get_ticker_details(ticker)
            
            # Verify data is valid
            if not data or not isinstance(data, dict):
                return {
                    'value': 'N/A',
                    'ticker': ticker,
                    'metric': metric,
                    'error': f'No valid ticker details returned for {ticker}'
                }
                
        elif data_source == "fundamentals":
            # Get data from fundamentals endpoint
            data = get_fundamentals(ticker)
            
            # Check if the result is empty
            if not data:
                return {
                    'value': 'N/A',
                    'ticker': ticker,
                    'metric': metric,
                    'error': f'No fundamental data available for {ticker}'
                }
                
        else:
            # This should never happen unless there's a programming error
            return {
                'value': 'N/A',
                'ticker': ticker,
                'metric': metric,
                'error': f'Unknown data source specified: {data_source}'
            }
        
        # Extract the value using the path and reduce function
        value = get_nested_value(data, value_path, "N/A")
            
        # Check if the value is None or not available
        if value is None or value == "N/A" or value == {}:
            # Determine which source the metric was supposed to come from
            source_name = "ticker details" if data_source == "details" else "fundamentals"
            return {
                'value': 'N/A',
                'ticker': ticker,
                'metric': metric,
                'error': f"Metric not found in Polygon {source_name} data"
            }
            
        # Return the metric value
        return {
            'value': value,
            'ticker': ticker,
            'metric': metric
        }
        
    except ValueError as e:
        # Handle ValueError (like ticker not found)
        return {
            'value': 'N/A',
            'ticker': ticker,
            'metric': metric,
            'error': str(e)
        }
    except ConnectionError as e:
        # Handle connection errors
        return {
            'value': 'N/A',
            'ticker': ticker,
            'metric': metric,
            'error': f'Connection error: {str(e)}'
        }
    except Exception as e:
        # Handle any unexpected errors
        return {
            'value': 'N/A',
            'ticker': ticker,
            'metric': metric,
            'error': f'An error occurred: {str(e)}'
        }


if __name__ == "__main__":
    # Simple tests for both endpoints
    print("\n--- Ticker Details Tests ---")
    print(get_financial_metric('AAPL', 'name'))
    print(get_financial_metric('MSFT', 'market_cap'))
    print(get_financial_metric('JPM', 'total_employees'))
    
    print("\n--- Fundamentals Tests ---")
    print(get_financial_metric('AAPL', 'net_income'))
    print(get_financial_metric('MSFT', 'pe_ratio'))
    print(get_financial_metric('JPM', 'revenue'))
    print(get_financial_metric('AAPL', 'roe'))
    
    print("\n--- Error Handling Tests ---")
    print(get_financial_metric('UNKNOWN', 'name'))
    print(get_financial_metric('AAPL', 'unknown_metric')) 