from pydantic import BaseModel, Field
from datetime import timedelta
from enum import Enum
from typing import Dict, Any, Optional

class AlgorithmType(str, Enum):
    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"

class RateLimitRule(BaseModel):
    """
    Defines a single rate limiting rule.
    The specific interpretation of 'limit', 'period', and 'algorithm_params'
    depends on the chosen 'algorithm' and its underlying library.
    """
    algorithm: AlgorithmType = Field(AlgorithmType.TOKEN_BUCKET, description="The rate limiting algorithm to use. Defaults to token bucket")
    limit: int = Field(gt=0, description="The number of allowed units (e.g., requests, tokens).")
    period: timedelta = Field(description="The time period for the limit.")

    # This field allows passing extra parameters to the underlying library's
    # constructor or methods, as interpreted by the specific adapter.
    # For example, for "token_bucket_limits", you might pass {"burst": 15}
    algorithm_params: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional parameters specific to the chosen algorithm/library adapter."
    )

    # Helper for 'limits' library based rules
    def get_limits_rate_string(self) -> str:
        """
        Generates a rate string like '10/minute' for the 'limits' library.
        Includes burst if specified in algorithm_params.
        """
        rate_part: str
        seconds = int(self.period.total_seconds())
        if seconds == 1:
            rate_part = f"{self.limit}/second"
        elif seconds == 60:
            rate_part = f"{self.limit}/minute"
        elif seconds == 3600:
            rate_part = f"{self.limit}/hour"
        elif seconds == 86400:
            rate_part = f"{self.limit}/day"
        else:
            rate_part = f"{self.limit}/{seconds}seconds"

        burst_val = self.algorithm_params.get("burst") if self.algorithm_params else None
        if burst_val is not None:
            return f"{rate_part};burst={burst_val}"
        return rate_part

class GlobalRateLimiterConfig(BaseModel):
    """
    Global configuration for the RateLimiter.
    Currently minimal, can be expanded (e.g., for shared Redis storage config).
    """
    # Example: shared_redis_url: Optional[str] = None
    pass
