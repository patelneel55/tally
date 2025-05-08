from abc import ABC, abstractmethod

from langchain_core.rate_limiters import BaseRateLimiter


class BaseRateLimiter(BaseRateLimiter):
    @abstractmethod
    async def configure(self, **kwargs) -> None:
        pass
