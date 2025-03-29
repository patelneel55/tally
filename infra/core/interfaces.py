"""
Core Interfaces
--------------

This module defines the core interfaces used throughout the infrastructure
layer. These interfaces establish the contract that all concrete implementations
must follow.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, date

class IDataFetcher(ABC):
    """
    Abstract base class for data fetchers.
    
    This interface defines the contract that all data fetchers must implement.
    It provides a standardized way to fetch data from various sources while
    maintaining consistent error handling and response formats.
    """
    
    @abstractmethod
    async def fetch(self, identifier: str, **kwargs) -> Any:
        """
        Fetch data for a given identifier.
        
        Args:
            identifier: Unique identifier for the data to fetch (e.g., ticker symbol)
            **kwargs: Additional parameters specific to the data source
            
        Returns:
            The fetched data in a standardized format
            
        Raises:
            DataFetchError: If the data cannot be fetched
            ValidationError: If the input parameters are invalid
        """
        pass
    
    # @abstractmethod
    # async def fetch_batch(self, identifiers: List[str], **kwargs) -> Dict[str, Any]:
    #     """
    #     Fetch data for multiple identifiers in parallel.
        
    #     Args:
    #         identifiers: List of unique identifiers
    #         **kwargs: Additional parameters specific to the data source
            
    #     Returns:
    #         Dictionary mapping identifiers to their fetched data
            
    #     Raises:
    #         DataFetchError: If any of the data cannot be fetched
    #         ValidationError: If the input parameters are invalid
    #     """
    #     pass
    
    # @abstractmethod
    # async def fetch_historical(
    #     self,
    #     identifier: str,
    #     start_date: Optional[Union[datetime, date]] = None,
    #     end_date: Optional[Union[datetime, date]] = None,
    #     **kwargs
    # ) -> List[Any]:
    #     """
    #     Fetch historical data for a given identifier.
        
    #     Args:
    #         identifier: Unique identifier for the data to fetch
    #         start_date: Start date for historical data
    #         end_date: End date for historical data
    #         **kwargs: Additional parameters specific to the data source
            
    #     Returns:
    #         List of historical data points
            
    #     Raises:
    #         DataFetchError: If the historical data cannot be fetched
    #         ValidationError: If the input parameters are invalid
    #     """
    #     pass
    
    # @abstractmethod
    # def validate_identifier(self, identifier: str) -> bool:
    #     """
    #     Validate if an identifier is in the correct format.
        
    #     Args:
    #         identifier: Identifier to validate
            
    #     Returns:
    #         True if the identifier is valid, False otherwise
    #     """
    #     pass
    
    # @abstractmethod
    # def get_rate_limit(self) -> Dict[str, int]:
    #     """
    #     Get the rate limits for this data fetcher.
        
    #     Returns:
    #         Dictionary containing rate limit information:
    #         {
    #             "requests_per_second": int,
    #             "requests_per_minute": int,
    #             "requests_per_hour": int
    #         }
    #     """
    #     pass 