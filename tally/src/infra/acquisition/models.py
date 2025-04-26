from abc import ABC
from abc import abstractmethod
from enum import Enum
from typing import Any
from typing import List

from infra.collections.models import BaseMetadata


class DataFormat(str, Enum):
    """Data format options for SEC filings."""

    HTML = "html"
    PDF = "pdf"


class AcquisitionOutput(ABC):
    """
    Abstract base class for acquisition outputs.
    """

    @abstractmethod
    def get_uris(self) -> List[str]:
        """
        Abstract method to get the URIs from the acquisition output.
        """
        pass

    @abstractmethod
    def get_metadata(self) -> BaseMetadata:
        """
        Abstract method to get the metadata from the acquisition output.
        """
        pass


class IDataFetcher(ABC):
    """
    Abstract base class for data fetchers.

    This interface defines the contract that all data fetchers must implement.
    It provides a standardized way to fetch data from various sources while
    maintaining consistent error handling and response formats.
    """

    @abstractmethod
    async def fetch(self, **kwargs) -> AcquisitionOutput:
        """
        Fetch data for a given identifier.

        Args:
            **kwargs: Parameters required to fetch the data. The specific parameters depend
                on the implementation of the data fetcher.

        Returns:
            The fetched data in a AcquisitionOutput format.
        """
        pass
