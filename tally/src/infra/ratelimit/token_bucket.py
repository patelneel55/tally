from infra.ratelimit.models import BaseRateLimiter


class TokenBucketRateLimiter(BaseRateLimiter):
    def __init__(self):
        super().__init__()
