class RateLimitException(Exception):
    """Base exception for rate limiting errors."""
    pass

class RateLimitExceeded(RateLimitException):
    """Exception raised when a rate limit is exceeded."""
    def __init__(self, identifier: str, rule_name: str, retry_after: float | None = None, message: str = "Rate limit exceeded"):
        self.identifier = identifier
        self.rule_name = rule_name
        self.retry_after = retry_after
        self.message = message
        super().__init__(f"{message} for identifier '{identifier}' on rule '{rule_name}'. Retry after: {retry_after or 'N/A'}s")

class RateLimiterConfigError(RateLimitException):
    """Exception for configuration errors."""
    pass
