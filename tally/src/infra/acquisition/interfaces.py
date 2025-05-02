from abc import ABC, abstractmethod

from infra.acquisition.models import AcquisitionOutput


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
