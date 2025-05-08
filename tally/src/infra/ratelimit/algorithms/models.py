from abc import ABC, abstractmethod
from typing import Union, Tuple, Any

from infra.ratelimit.models import RateLimitRule

class BaseRateLimiterAlgorithm(ABC):
    """
    Abstract base class for a rate limiting algorithm implementation.
    This class would typically interact with a storage backend.
    """
    @abstractmethod
    async def consume(
        self,
        rule: RateLimitRule,
        identifier: str,
        cost: int = 1
    ):
        """
        Attempts to consume resources based on the rule and identifier.

        Args:
            rule: The RateLimitRule to apply.
            identifier: A unique string identifying the entity being limited.
            cost: The amount of resource to consume (e.g., number of tokens).

        """
        pass

    @abstractmethod
    async def setup(self):
        """Optional setup for the adapter (e.g., initializing resources)."""
        pass

    @abstractmethod
    async def teardown(self):
        """Optional teardown for the adapter (e.g., cleaning up resources)."""
        pass
