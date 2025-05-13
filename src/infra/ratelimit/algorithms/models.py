from abc import ABC, abstractmethod

from infra.ratelimit.models import RateLimitRule


class BaseRateLimiterAlgorithm(ABC):
    """
    Abstract base class for a rate limiting algorithm implementation.
    This class would typically interact with a storage backend.
    """

    @abstractmethod
    async def consume(self, rule: RateLimitRule, identifier: str, cost: int = 1):
        """
        Attempts to consume resources based on the rule and identifier.

        Args:
            rule: The RateLimitRule to apply.
            identifier: A unique string identifying the entity being limited.
            cost: The amount of resource to consume (e.g., number of tokens).

        """
        pass
