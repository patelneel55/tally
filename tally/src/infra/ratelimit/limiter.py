import asyncio
from typing import Dict, List, Optional, Tuple

from infra.ratelimit.algorithms.leaky_bucket import LeakyBucketAlgorithm
from infra.ratelimit.algorithms.models import BaseRateLimiterAlgorithm
from infra.ratelimit.algorithms.token_bucket import TokenBucketAlgorithm
from infra.ratelimit.exceptions import RateLimiterConfigError
from infra.ratelimit.models import AlgorithmType, GlobalRateLimiterConfig, RateLimitRule


class RateLimiter:
    def __init__(
        self,
        rules: Dict[str, RateLimitRule] = None,
        config: Optional[GlobalRateLimiterConfig] = None,
    ):
        self.global_config = config or GlobalRateLimiterConfig()
        self.rules: Dict[str, RateLimitRule] = rules.copy() if rules else {}

        self.adapters: Dict[str, BaseRateLimiterAlgorithm] = {}
        self._async_init_lock = asyncio.Lock()
        self._initialized = False

    async def _setup_adapters(self):
        async with self._async_init_lock:
            for rule_name, rule_config in self.rules.items():
                if rule_name not in self.adapters:
                    if rule_name in self.adapters:
                        return self.adapters[rule_name]

                    adapter: BaseRateLimiterAlgorithm
                    if rule_config.algorithm == AlgorithmType.LEAKY_BUCKET:
                        adapter = LeakyBucketAlgorithm(rule_config)
                    elif rule_config.algorithm == AlgorithmType.TOKEN_BUCKET:
                        adapter = TokenBucketAlgorithm(rule_config)
                    else:
                        raise RateLimiterConfigError(
                            f"Unsupported async algorithm_type: {rule_config.algorithm_type} for rule '{rule_name}'"
                        )
                    self.adapters[rule_name] = adapter
            self._initialized = True

    async def _get_or_create_adapter(self, rule_name: str) -> BaseRateLimiterAlgorithm:
        if not self._initialized:
            await self._setup_adapters()

        if rule_name not in self.rules:
            raise RateLimiterConfigError(f"Rule '{rule_name}' not found.")

        return self.adapters.get(rule_name)

    def add_rule(self, rule_name: str, rule_config: RateLimitRule):
        self.rules[rule_name] = rule_config
        self._initialized = False

    async def acquire(self, rules: List[Tuple[str, int]], identifier: str = "global"):
        for rule_name, cost in rules:
            if rule_name not in self.rules:
                raise RateLimiterConfigError(f"Invalid rule: '{rule_name}'")
            if cost <= 0:
                raise ValueError(
                    f"Cost for rule '{rule_name}' must be positive ({cost} given)."
                )

            adapter: BaseRateLimiterAlgorithm = await self._get_or_create_adapter(
                rule_name
            )
            await adapter.consume(identifier=identifier, cost=cost)
