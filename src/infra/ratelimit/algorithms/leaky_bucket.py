import asyncio
from typing import Dict

from aiolimiter import AsyncLimiter

from infra.ratelimit.algorithms.models import BaseRateLimiterAlgorithm
from infra.ratelimit.models import AlgorithmType, RateLimitRule


class LeakyBucketAlgorithm(BaseRateLimiterAlgorithm):
    def __init__(self, rule: RateLimitRule):
        if rule.algorithm != AlgorithmType.LEAKY_BUCKET:
            raise ValueError(
                f"invalid algorithm for leaky bucket rate limiting: {rule.algorithm}"
            )

        self._rule_config = rule
        self._lock = asyncio.Lock()
        self._limiters: Dict[str, AsyncLimiter] = {}
        self._lock = asyncio.Lock()  # Protects access to self._limiters dictionary

    async def _get_or_create_limiter(self, identifier: str) -> AsyncLimiter:
        async with self._lock:
            if identifier not in self._limiters:
                self._limiters[identifier] = AsyncLimiter(
                    self._rule_config.limit, self._rule_config.period.total_seconds()
                )
            return self._limiters[identifier]

    async def consume(self, identifier: str, cost: int = 1):
        if cost <= 0:
            return
        limiter = await self._get_or_create_limiter(identifier)
        await limiter.acquire(cost)
