from typing import Any


class DataFetchError(Exception):
    """
    Exception raised when data cannot be fetched from a source.

    This exception indicates a failure in the data fetching process,
    such as network errors, API failures, or invalid responses.
    """

    def __init__(self, message: str, source: str = None, status_code: int = None):
        """
        Initialize the DataFetchError.

        Args:
            message: Error message describing the failure
            source: Name of the data source that failed
            status_code: HTTP status code if applicable
        """
        self.message = message
        self.source = source
        self.status_code = status_code
        super().__init__(
            f"{message} (Source: {source}, Status: {status_code})"
            if source or status_code
            else message
        )


class ValidationError(Exception):
    """
    Exception raised when input validation fails.

    This exception indicates that the input parameters or data format
    are invalid and cannot be processed.
    """

    def __init__(self, message: str, field: str = None, value: Any = None):
        """
        Initialize the ValidationError.

        Args:
            message: Error message describing the validation failure
            field: Name of the field that failed validation
            value: Invalid value that caused the failure
        """
        self.message = message
        self.field = field
        self.value = value
        super().__init__(
            f"{message} (Field: {field}, Value: {value})" if field or value else message
        )


class RateLimitError(DataFetchError):
    """
    Exception raised when rate limits are exceeded.

    This exception indicates that too many requests were made to a
    data source in a given time period.
    """

    def __init__(self, message: str, source: str, retry_after: int = None):
        """
        Initialize the RateLimitError.

        Args:
            message: Error message describing the rate limit violation
            source: Name of the data source
            retry_after: Number of seconds to wait before retrying
        """
        self.retry_after = retry_after
        super().__init__(message, source)


class AuthenticationError(DataFetchError):
    """
    Exception raised when authentication fails.

    This exception indicates that the provided credentials or API keys
    are invalid or have expired.
    """

    def __init__(self, message: str, source: str):
        """
        Initialize the AuthenticationError.

        Args:
            message: Error message describing the authentication failure
            source: Name of the data source
        """
        super().__init__(message, source)


class DataFormatError(DataFetchError):
    """
    Exception raised when the data format is invalid.

    This exception indicates that the received data does not match
    the expected format or schema.
    """

    def __init__(self, message: str, source: str, data: Any = None):
        """
        Initialize the DataFormatError.

        Args:
            message: Error message describing the format issue
            source: Name of the data source
            data: The invalid data that caused the error
        """
        self.data = data
        super().__init__(message, source)
