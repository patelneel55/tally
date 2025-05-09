import asyncio
from typing import Dict

from limiter import Limiter, async_limit_rate

from infra.ratelimit.algorithms.models import BaseRateLimiterAlgorithm
from infra.ratelimit.models import AlgorithmType, RateLimitRule


class TokenBucketAlgorithm(BaseRateLimiterAlgorithm):
    def __init__(self, rule: RateLimitRule):
        if rule.algorithm != AlgorithmType.TOKEN_BUCKET:
            raise ValueError(
                f"invalid algorithm for token bucket rate limiting: {rule.algorithm}"
            )

        self._rule_config = rule
        self._lock = asyncio.Lock()
        self._limiters: Dict[str, Limiter] = {}
        self._lock = asyncio.Lock()  # Protects access to self._limiters dictionary

    async def _get_or_create_limiter(self, identifier: str) -> Limiter:
        async with self._lock:
            if identifier not in self._limiters:
                self._limiters[identifier] = Limiter(
                    capacity=self._rule_config.limit,
                    rate=(
                        self._rule_config.limit
                        / self._rule_config.period.total_seconds()
                    ),
                )
            return self._limiters[identifier]

    async def consume(self, identifier: str, cost: int = 1):
        if cost <= 0:
            return
        limiter = await self._get_or_create_limiter(identifier)
        async with async_limit_rate(
            limiter, consume=cost, bucket=limiter.bucket, jitter=limiter.jitter
        ):
            pass
