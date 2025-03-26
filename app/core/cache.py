"""
Cache Utility
------------

This module provides caching functionality for API responses and external API calls.
It helps reduce redundant API calls to external financial data services, improving
performance and managing rate limits.

What this file does:
1. Implements time-based in-memory caching for API responses
2. Provides decorators to easily cache function results
3. Manages cache expiration based on configurable settings

How it fits in the architecture:
- Cross-cutting utility used by services when retrieving data
- Helps optimize external API usage and reduce costs
- Improves application performance by reducing redundant data fetching

Financial importance:
- Financial APIs often have usage limits and costs per request
- Market data doesn't change by the second, so caching is appropriate
- Some financial data (like historical data) rarely changes and can be cached longer
"""

import datetime
import functools
import logging
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar

from app.core.config import settings

logger = logging.getLogger(__name__)

# Type variable for generic function return type
T = TypeVar("T")

# In-memory cache dictionary: {cache_key: (data, expiry_time)}
# This simple approach works for a single instance application
# For distributed systems, consider using Redis or similar
cache: Dict[str, Tuple[Any, datetime.datetime]] = {}


def clear_cache() -> None:
    """
    Clear the entire cache.
    
    This is useful when:
    - Testing the application
    - Manually forcing data refresh
    - Handling certain error conditions
    """
    global cache
    logger.info("Clearing entire cache")
    cache = {}


def get_cache_key(func_name: str, args: Tuple, kwargs: Dict) -> str:
    """
    Generate a unique cache key based on function name and arguments.
    
    Args:
        func_name: Name of the function being cached
        args: Positional arguments to the function
        kwargs: Keyword arguments to the function
        
    Returns:
        A string key unique to this function call with these parameters
    """
    # Convert args and kwargs to strings and combine them
    arg_str = ":".join(str(arg) for arg in args)
    kwarg_str = ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
    
    # Combine function name with argument strings
    return f"{func_name}:{arg_str}:{kwarg_str}"


def cache_response(expiry_minutes: Optional[int] = None) -> Callable:
    """
    Decorator to cache function responses.
    
    This decorator can be applied to any function to cache its results.
    Particularly useful for functions that:
    - Make expensive API calls
    - Retrieve data that doesn't change frequently
    - Have computationally intensive operations
    
    Args:
        expiry_minutes: How long to keep data in cache (overrides default)
        
    Returns:
        Decorator function that handles caching
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            # Skip caching if it's disabled in settings
            if not settings.ENABLE_CACHE:
                return await func(*args, **kwargs)
            
            # Get unique key for this function call
            cache_key = get_cache_key(func.__name__, args, kwargs)
            now = datetime.datetime.now()
            
            # Check if we have a valid cached response
            if cache_key in cache:
                cached_data, expiry_time = cache[cache_key]
                
                # If the cached data is still valid, return it
                if now < expiry_time:
                    logger.debug(f"Cache hit: {cache_key}")
                    return cached_data
                else:
                    logger.debug(f"Cache expired: {cache_key}")
            
            # No valid cache found, call the original function
            result = await func(*args, **kwargs)
            
            # Calculate expiry time based on parameters or default
            minutes = expiry_minutes if expiry_minutes is not None else settings.CACHE_EXPIRY_MINUTES
            expiry_time = now + datetime.timedelta(minutes=minutes)
            
            # Store the result in cache
            cache[cache_key] = (result, expiry_time)
            logger.debug(f"Cached: {cache_key}, expires at {expiry_time}")
            
            return result
        
        return wrapper
    
    return decorator


def invalidate_cache_for_symbol(symbol: str) -> None:
    """
    Invalidate all cached data for a specific stock symbol.
    
    This is useful when:
    - New financial information becomes available
    - The application detects outdated or incorrect data
    - Manually forcing a refresh for a specific company
    
    Args:
        symbol: Stock ticker symbol to invalidate cache for
    """
    global cache
    symbol_upper = symbol.upper()  # Normalize symbol to uppercase
    
    # Find and remove all cache entries containing this symbol
    keys_to_remove = []
    for key in cache:
        if symbol_upper in key:
            keys_to_remove.append(key)
    
    # Remove the identified keys
    for key in keys_to_remove:
        del cache[key]
    
    logger.info(f"Invalidated cache for symbol: {symbol_upper}, removed {len(keys_to_remove)} entries") 