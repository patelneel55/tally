import logging
import time

from aiolimiter import AsyncLimiter


logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(
        self,
        request_limiters: list[AsyncLimiter] = None,
        token_limiters: list[AsyncLimiter] = None,
    ):
        self.request_limiters = request_limiters or []
        self.token_limiters = token_limiters or []
        self.total_requests_acquired = 0
        self.total_tokens_acquired = 0

    async def acquire(self, tokens: int = 1):
        start_time = time.perf_counter()

        for limiter in self.request_limiters:
            await limiter.acquire()
        self.total_requests_acquired += 1

        for limiter in self.token_limiters:
            await limiter.acquire(tokens)
        self.total_tokens_acquired += tokens
        duration = time.perf_counter() - start_time

        logger.info(
            f"[{time.strftime('%X')}] RateLimiter acquired "
            f"{tokens} tokens | "
            f"total requests: {self.total_requests_acquired}, "
            f"total tokens: {self.total_tokens_acquired} | "
            f"waited: {duration:.2f}s"
        )
