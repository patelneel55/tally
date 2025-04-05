import abc


class AcquisitionOutput(abc.ABC):
    """
    Abstract base class for acquisition outputs.
    """

    @abc.abstractmethod
    def get_uris(self):
        """
        Abstract method to get the URIs from the acquisition output.
        """
        pass

    @abc.abstractmethod
    def get_metadata(self):
        """
        Abstract method to get the metadata from the acquisition output.
        """
        pass
