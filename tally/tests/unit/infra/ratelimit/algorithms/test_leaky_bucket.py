import asyncio
from datetime import timedelta

import pytest
from aiolimiter import AsyncLimiter

from infra.ratelimit.algorithms.leaky_bucket import LeakyBucketAlgorithm
from infra.ratelimit.models import AlgorithmType, RateLimitRule


@pytest.fixture
def rate_limit_rule():
    """Create a sample rate limit rule for testing."""
    return RateLimitRule(
        limit=10, period=timedelta(seconds=1), algorithm=AlgorithmType.LEAKY_BUCKET
    )


@pytest.fixture
def leaky_bucket(rate_limit_rule):
    """Create a LeakyBucketAlgorithm instance for testing."""
    return LeakyBucketAlgorithm(rate_limit_rule)


class TestLeakyBucketAlgorithm:
    """Tests for the LeakyBucketAlgorithm class."""

    def test_init_with_invalid_algorithm(self):
        """Test initialization with invalid algorithm type."""
        invalid_rule = RateLimitRule(
            limit=10,
            period=timedelta(seconds=1),
            algorithm=AlgorithmType.TOKEN_BUCKET,  # Wrong algorithm type
        )
        with pytest.raises(
            ValueError, match="invalid algorithm for leaky bucket rate limiting"
        ):
            LeakyBucketAlgorithm(invalid_rule)

    @pytest.mark.asyncio
    async def test_consume_with_zero_cost(self, leaky_bucket):
        """Test consuming with zero cost should not block."""
        await leaky_bucket.consume("test_id", cost=0)

    @pytest.mark.asyncio
    async def test_consume_with_negative_cost(self, leaky_bucket):
        """Test consuming with negative cost should not block."""
        await leaky_bucket.consume("test_id", cost=-1)

    @pytest.mark.asyncio
    async def test_consume_cost_greater_than_limit(self, leaky_bucket):
        """Test that consuming a cost greater than the limit raises ValueError."""
        with pytest.raises(
            ValueError, match="Can't acquire more than the maximum capacity"
        ):
            await leaky_bucket.consume("test_id", cost=11)  # Limit is 10

    @pytest.mark.asyncio
    async def test_rate_limiting_basic(self, leaky_bucket):
        """Test basic rate limiting functionality."""
        identifier = "test_id"
        start_time = asyncio.get_event_loop().time()

        # Try to consume 15 tokens when limit is 10 per second
        # First 10 tokens should be immediate, next 5 should take 0.5 seconds
        for _ in range(15):
            await leaky_bucket.consume(identifier)

        end_time = asyncio.get_event_loop().time()
        # Should take at least 0.5 seconds (5 tokens / 10 tokens per second)
        assert end_time - start_time >= 0.5

    @pytest.mark.asyncio
    async def test_multiple_identifiers(self, leaky_bucket):
        """Test that different identifiers have separate rate limits."""
        start_time = asyncio.get_event_loop().time()

        # Consume from two different identifiers simultaneously
        await asyncio.gather(leaky_bucket.consume("id1"), leaky_bucket.consume("id2"))

        end_time = asyncio.get_event_loop().time()
        # Should take less than 0.1 seconds since they're different identifiers
        assert end_time - start_time < 0.1

    @pytest.mark.asyncio
    async def test_concurrent_access_same_identifier(self, leaky_bucket):
        """Test concurrent access to the same identifier."""
        identifier = "test_id"
        num_concurrent = 15  # More than the limit to ensure rate limiting occurs

        # Create multiple concurrent consumers
        async def consumer():
            await leaky_bucket.consume(identifier)

        # Run consumers concurrently
        start_time = asyncio.get_event_loop().time()
        await asyncio.gather(*(consumer() for _ in range(num_concurrent)))
        end_time = asyncio.get_event_loop().time()

        # First 10 tokens are immediate, next 5 should take 0.5 seconds
        assert end_time - start_time >= 0.5

    @pytest.mark.asyncio
    async def test_get_or_create_limiter(self, leaky_bucket):
        """Test limiter creation and retrieval."""
        identifier = "test_id"

        # First call should create a new limiter
        limiter1 = await leaky_bucket._get_or_create_limiter(identifier)
        assert isinstance(limiter1, AsyncLimiter)

        # Second call should return the same limiter
        limiter2 = await leaky_bucket._get_or_create_limiter(identifier)
        assert limiter1 is limiter2

    @pytest.mark.asyncio
    async def test_limiter_reuse(self, leaky_bucket):
        """Test that limiters are reused for the same identifier."""
        identifier = "test_id"

        # Create initial limiter
        limiter1 = await leaky_bucket._get_or_create_limiter(identifier)

        # Consume some tokens
        await leaky_bucket.consume(identifier, cost=5)

        # Get limiter again
        limiter2 = await leaky_bucket._get_or_create_limiter(identifier)

        # Should be the same limiter instance
        assert limiter1 is limiter2

    @pytest.mark.asyncio
    async def test_different_periods(self, rate_limit_rule):
        """Test rate limiting with different time periods."""
        # Create a rule with 5 tokens per 2 seconds
        rule = RateLimitRule(
            limit=5, period=timedelta(seconds=2), algorithm=AlgorithmType.LEAKY_BUCKET
        )
        bucket = LeakyBucketAlgorithm(rule)

        identifier = "test_id"
        start_time = asyncio.get_event_loop().time()

        # Try to consume 8 tokens when limit is 5 per 2 seconds
        # First 5 tokens are immediate, next 3 should take 1.2 seconds (3 tokens / 5 tokens per 2 seconds)
        for _ in range(8):
            await bucket.consume(identifier)

        end_time = asyncio.get_event_loop().time()
        assert end_time - start_time >= 1.2

    @pytest.mark.asyncio
    async def test_burst_consumption(self, leaky_bucket):
        """Test burst consumption up to the limit."""
        identifier = "test_id"
        start_time = asyncio.get_event_loop().time()

        # Consume exactly at the limit (10 tokens)
        for _ in range(10):
            await leaky_bucket.consume(identifier)

        end_time = asyncio.get_event_loop().time()
        # Should be very fast since we're not exceeding the limit
        assert end_time - start_time < 0.1

    @pytest.mark.asyncio
    async def test_interleaved_consumption(self, leaky_bucket):
        """Test interleaved consumption from multiple identifiers."""

        async def consumer(identifier: str, num_tokens: int):
            for _ in range(num_tokens):
                await leaky_bucket.consume(identifier)

        start_time = asyncio.get_event_loop().time()

        # Run two consumers that each try to consume 8 tokens
        await asyncio.gather(consumer("id1", 8), consumer("id2", 8))

        end_time = asyncio.get_event_loop().time()
        # Each consumer should be able to consume up to their limit without waiting
        assert end_time - start_time < 0.1

    @pytest.mark.asyncio
    async def test_rapid_successive_consumption(self, leaky_bucket):
        """Test rapid successive consumption from the same identifier."""
        identifier = "test_id"
        start_time = asyncio.get_event_loop().time()

        # Consume 5 tokens rapidly
        for _ in range(5):
            await leaky_bucket.consume(identifier)
            await asyncio.sleep(0.01)  # Small delay between requests

        end_time = asyncio.get_event_loop().time()
        # Should be fast since we're not exceeding the limit
        assert end_time - start_time < 0.1

    @pytest.mark.asyncio
    async def test_mixed_cost_consumption(self, leaky_bucket):
        """Test consumption with mixed token costs."""
        identifier = "test_id"
        start_time = asyncio.get_event_loop().time()

        # Mix of different token costs
        costs = [2, 3, 1, 4]
        for cost in costs:
            await leaky_bucket.consume(identifier, cost=cost)

        end_time = asyncio.get_event_loop().time()
        # Should be fast since total cost (10) equals the limit
        assert end_time - start_time < 0.1
