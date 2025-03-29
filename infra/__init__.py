"""
Infrastructure Package
--------------------

This package contains core infrastructure components for data acquisition
and processing in the Analyst AI system. It provides abstract interfaces
and concrete implementations for fetching and processing financial data.

Components:
- core: Core interfaces and exceptions
- acquisition: Data fetching implementations
"""

from .core.interfaces import IDataFetcher
from .core.exceptions import DataFetchError, ValidationError

__all__ = ['IDataFetcher', 'DataFetchError', 'ValidationError'] 