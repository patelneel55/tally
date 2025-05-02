from aiolimiter import AsyncLimiter


class RateLimiter:
    def __init__(
        self,
        request_limiters: list[AsyncLimiter] = None,
        token_limiters: list[AsyncLimiter] = None,
    ):
        self.request_limiters = request_limiters or []
        self.token_limiters = token_limiters or []

    async def acquire(self, tokens: int = 1):
        for limiter in self.request_limiters:
            await limiter.acquire()
        for limiter in self.token_limiters:
            await limiter.acquire(tokens)
