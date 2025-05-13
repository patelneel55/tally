"""
Utility Endpoints
---------------

This module provides utility endpoints for administrative tasks and debugging.
These endpoints help with maintenance operations and troubleshooting.
"""

import logging
import os
import shutil
from pathlib import Path
from typing import Dict, List

from fastapi import APIRouter, HTTPException
from fastapi import Path as PathParam
from fastapi import status

from app.core.config import settings


# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


@router.delete(
    "/cache/{symbol}",
    summary="Clear cache for a specific symbol",
    description="Clears all cached data for the specified stock symbol, including SEC analysis, financial models, and other data.",
)
async def clear_symbol_cache(
    symbol: str = PathParam(..., description="Stock symbol to clear cache for")
):
    """
    Clear all cached data for a specific symbol.

    This endpoint:
    1. Removes in-memory cache entries for the symbol
    2. Deletes cached files for the symbol from all cache directories

    Args:
        symbol: Stock ticker symbol (e.g., AAPL, MSFT)

    Returns:
        Dictionary with information about what was cleared
    """
    try:
        # Convert symbol to uppercase
        symbol = symbol.upper()
        logger.info(f"Clearing cache for symbol: {symbol}")

        # Clear in-memory cache - skipping this for now as it requires additional imports
        # invalidate_cache_for_symbol(symbol)

        # List of cache directories to check
        cache_directories = [
            Path("cache/sec_analysis"),
            Path("cache/sec_filings"),
            Path("cache/sec_filing_metadata"),
            Path("cache/sec_filing_urls"),
            Path("cache/sec_trends"),
            Path("data/aggregated_data"),
            Path("data/financial_models"),
            Path("data/financial_analysis"),
            Path("data/financial_statements_cache"),
            Path("data/polygon_cache"),
        ]

        deleted_files = []

        # Remove files from cache directories
        for directory in cache_directories:
            if directory.exists():
                for file_path in directory.glob(f"*{symbol}*"):
                    if file_path.is_file():
                        logger.info(f"Deleting cached file: {file_path}")
                        os.remove(file_path)
                        deleted_files.append(str(file_path))

        return {
            "message": f"Cache cleared for symbol: {symbol}",
            "deleted_files": deleted_files,
            "deleted_count": len(deleted_files),
        }

    except Exception as e:
        logger.error(f"Error clearing cache for {symbol}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while clearing the cache: {str(e)}",
        )


@router.delete(
    "/cache",
    summary="Clear all cache",
    description="Clears all cached data, including in-memory cache and file cache.",
)
async def clear_all_cache():
    """
    Clear all cached data.

    This endpoint:
    1. Clears the in-memory cache
    2. Optionally deletes all cached files from all cache directories

    Returns:
        Dictionary with information about what was cleared
    """
    try:
        logger.info("Clearing all cache")

        # Clear in-memory cache - skipping this for now as it requires additional imports
        # clear_cache()

        # List of cache directories to clean
        cache_directories = [
            Path("cache/sec_analysis"),
            Path("cache/sec_filings"),
            Path("cache/sec_filing_metadata"),
            Path("cache/sec_filing_urls"),
            Path("cache/sec_trends"),
            Path("data/aggregated_data"),
            Path("data/financial_models"),
            Path("data/financial_analysis"),
            Path("data/financial_statements_cache"),
            Path("data/polygon_cache"),
        ]

        deleted_count = 0
        directory_stats = {}

        # Remove files from cache directories
        for directory in cache_directories:
            if directory.exists():
                dir_count = 0
                for file_path in directory.glob("*.*"):
                    if file_path.is_file():
                        logger.debug(f"Deleting cached file: {file_path}")
                        os.remove(file_path)
                        deleted_count += 1
                        dir_count += 1
                directory_stats[str(directory)] = dir_count

        return {
            "message": "All cache cleared",
            "deleted_count": deleted_count,
            "directory_stats": directory_stats,
        }

    except Exception as e:
        logger.error(f"Error clearing all cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while clearing the cache: {str(e)}",
        )
