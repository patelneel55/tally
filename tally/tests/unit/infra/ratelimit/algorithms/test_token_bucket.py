"""Tests for the TokenBucketAlgorithm class."""

import asyncio
from datetime import timedelta

import pytest
from limiter import Limiter

from infra.ratelimit.algorithms.token_bucket import TokenBucketAlgorithm
from infra.ratelimit.models import AlgorithmType, RateLimitRule


@pytest.fixture
def rate_limit_rule():
    """Create a sample rate limit rule for testing."""
    return RateLimitRule(
        limit=10, period=timedelta(seconds=1), algorithm=AlgorithmType.TOKEN_BUCKET
    )


@pytest.fixture
def token_bucket(rate_limit_rule):
    """Create a TokenBucketAlgorithm instance for testing."""
    return TokenBucketAlgorithm(rate_limit_rule)


class TestTokenBucketAlgorithm:
    """Tests for the TokenBucketAlgorithm class."""

    def test_init_with_invalid_algorithm(self):
        """Test initialization with invalid algorithm type."""
        invalid_rule = RateLimitRule(
            limit=10,
            period=timedelta(seconds=1),
            algorithm=AlgorithmType.LEAKY_BUCKET,  # Wrong algorithm type
        )
        with pytest.raises(
            ValueError, match="invalid algorithm for token bucket rate limiting"
        ):
            TokenBucketAlgorithm(invalid_rule)

    @pytest.mark.asyncio
    async def test_consume_with_zero_cost(self, token_bucket):
        """Test consuming with zero cost should not block."""
        await token_bucket.consume("test_id", cost=0)

    @pytest.mark.asyncio
    async def test_consume_with_negative_cost(self, token_bucket):
        """Test consuming with negative cost should not block."""
        await token_bucket.consume("test_id", cost=-1)

    @pytest.mark.asyncio
    async def test_burst_consumption(self, token_bucket):
        """Test burst consumption up to the capacity."""
        identifier = "test_id"
        start_time = asyncio.get_event_loop().time()

        # Consume exactly at the capacity (10 tokens)
        for _ in range(10):
            await token_bucket.consume(identifier)

        end_time = asyncio.get_event_loop().time()
        # Should be very fast since we're not exceeding the capacity
        assert end_time - start_time < 0.1

    @pytest.mark.asyncio
    async def test_consumption_beyond_capacity(self, token_bucket):
        """Test consumption beyond capacity triggers rate limiting."""
        identifier = "test_id"
        start_time = asyncio.get_event_loop().time()

        # Try to consume 15 tokens when capacity is 10
        for _ in range(15):
            await token_bucket.consume(identifier)

        end_time = asyncio.get_event_loop().time()
        # Should take at least 0.5 seconds (5 tokens / 10 tokens per second)
        assert end_time - start_time >= 0.5

    @pytest.mark.asyncio
    async def test_multiple_identifiers(self, token_bucket):
        """Test that different identifiers have separate rate limits."""
        start_time = asyncio.get_event_loop().time()

        # Consume from two different identifiers simultaneously
        await asyncio.gather(token_bucket.consume("id1"), token_bucket.consume("id2"))

        end_time = asyncio.get_event_loop().time()
        # Should take less than 0.1 seconds since they're different identifiers
        assert end_time - start_time < 0.1

    @pytest.mark.asyncio
    async def test_concurrent_access_same_identifier(self, token_bucket):
        """Test concurrent access to the same identifier."""
        identifier = "test_id"
        num_concurrent = 15  # More than the capacity to ensure rate limiting occurs

        # Create multiple concurrent consumers
        async def consumer():
            await token_bucket.consume(identifier)

        # Run consumers concurrently
        start_time = asyncio.get_event_loop().time()
        await asyncio.gather(*(consumer() for _ in range(num_concurrent)))
        end_time = asyncio.get_event_loop().time()

        # First 10 tokens are immediate, next 5 should take 0.5 seconds
        assert end_time - start_time >= 0.5

    @pytest.mark.asyncio
    async def test_get_or_create_limiter(self, token_bucket):
        """Test limiter creation and retrieval."""
        identifier = "test_id"

        # First call should create a new limiter
        limiter1 = await token_bucket._get_or_create_limiter(identifier)
        assert isinstance(limiter1, Limiter)

        # Second call should return the same limiter
        limiter2 = await token_bucket._get_or_create_limiter(identifier)
        assert limiter1 is limiter2

    @pytest.mark.asyncio
    async def test_limiter_reuse(self, token_bucket):
        """Test that limiters are reused for the same identifier."""
        identifier = "test_id"

        # Create initial limiter
        limiter1 = await token_bucket._get_or_create_limiter(identifier)

        # Consume some tokens
        await token_bucket.consume(identifier, cost=5)

        # Get limiter again
        limiter2 = await token_bucket._get_or_create_limiter(identifier)

        # Should be the same limiter instance
        assert limiter1 is limiter2

    @pytest.mark.asyncio
    async def test_different_periods(self, rate_limit_rule):
        """Test rate limiting with different time periods."""
        # Create a rule with 5 tokens per 2 seconds
        rule = RateLimitRule(
            limit=5, period=timedelta(seconds=2), algorithm=AlgorithmType.TOKEN_BUCKET
        )
        bucket = TokenBucketAlgorithm(rule)

        identifier = "test_id"
        start_time = asyncio.get_event_loop().time()

        # Try to consume 8 tokens when capacity is 5
        # First 5 tokens are immediate, next 3 should take 1.2 seconds (3 tokens / 5 tokens per 2 seconds)
        for _ in range(8):
            await bucket.consume(identifier)

        end_time = asyncio.get_event_loop().time()
        assert end_time - start_time >= 1.2

    @pytest.mark.asyncio
    async def test_token_refill(self, token_bucket):
        """Test that tokens are refilled at the correct rate."""
        identifier = "test_id"

        # Consume all tokens
        for _ in range(10):
            await token_bucket.consume(identifier)

        # Wait for 0.5 seconds to allow token refill
        await asyncio.sleep(0.5)

        # Should be able to consume 5 more tokens immediately
        start_time = asyncio.get_event_loop().time()
        for _ in range(5):
            await token_bucket.consume(identifier)
        end_time = asyncio.get_event_loop().time()

        # Should be fast since tokens have been refilled
        assert end_time - start_time < 0.1

    @pytest.mark.asyncio
    async def test_mixed_cost_consumption(self, token_bucket):
        """Test consumption with mixed token costs."""
        identifier = "test_id"
        start_time = asyncio.get_event_loop().time()

        # Mix of different token costs
        costs = [2, 3, 1, 4]
        for cost in costs:
            await token_bucket.consume(identifier, cost=cost)

        end_time = asyncio.get_event_loop().time()
        # Should be fast since total cost (10) equals the capacity
        assert end_time - start_time < 0.1

    @pytest.mark.asyncio
    async def test_rapid_successive_consumption(self, token_bucket):
        """Test rapid successive consumption from the same identifier."""
        identifier = "test_id"
        start_time = asyncio.get_event_loop().time()

        # Consume 5 tokens rapidly
        for _ in range(5):
            await token_bucket.consume(identifier)
            await asyncio.sleep(0.01)  # Small delay between requests

        end_time = asyncio.get_event_loop().time()
        # Should be fast since we're not exceeding the capacity
        assert end_time - start_time < 0.1

    @pytest.mark.asyncio
    async def test_token_refill_after_depletion(self, token_bucket):
        """Test that tokens are refilled correctly after complete depletion."""
        identifier = "test_id"

        # Consume all tokens
        for _ in range(10):
            await token_bucket.consume(identifier)

        # Wait for 1 second to allow full refill
        await asyncio.sleep(1)

        # Should be able to consume all tokens again
        start_time = asyncio.get_event_loop().time()
        for _ in range(10):
            await token_bucket.consume(identifier)
        end_time = asyncio.get_event_loop().time()

        # Should be fast since tokens have been fully refilled
        assert end_time - start_time < 0.1

    @pytest.mark.asyncio
    async def test_partial_token_refill(self, token_bucket):
        """Test that tokens are refilled partially when waiting less than full period."""
        identifier = "test_id"

        # Consume all tokens
        for _ in range(10):
            await token_bucket.consume(identifier)

        # Wait for 0.3 seconds (should refill 3 tokens)
        await asyncio.sleep(0.3)

        # Should be able to consume 3 tokens immediately
        start_time = asyncio.get_event_loop().time()
        for _ in range(3):
            await token_bucket.consume(identifier)
        end_time = asyncio.get_event_loop().time()

        # Should be fast since we're only consuming refilled tokens
        assert end_time - start_time < 0.1

    @pytest.mark.asyncio
    async def test_high_cost_consumption(self, token_bucket):
        """Test consumption with high token costs."""
        identifier = "test_id"
        start_time = asyncio.get_event_loop().time()

        # Try to consume 8 tokens at once
        await token_bucket.consume(identifier, cost=8)

        # Should be able to consume 2 more tokens immediately
        await token_bucket.consume(identifier, cost=2)

        end_time = asyncio.get_event_loop().time()
        # Should be fast since total cost equals capacity
        assert end_time - start_time < 0.1

    @pytest.mark.asyncio
    async def test_intermittent_consumption(self, token_bucket):
        """Test consumption with intermittent delays."""
        identifier = "test_id"
        start_time = asyncio.get_event_loop().time()

        # Consume 5 tokens
        for _ in range(5):
            await token_bucket.consume(identifier)

        # Wait for 0.5 seconds to allow token refill
        await asyncio.sleep(0.5)

        # Consume 5 more tokens
        for _ in range(5):
            await token_bucket.consume(identifier)

        end_time = asyncio.get_event_loop().time()
        # Should be fast since we're consuming at a rate below the limit
        assert end_time - start_time < 0.6

    @pytest.mark.asyncio
    async def test_multiple_identifiers_with_different_costs(self, token_bucket):
        """Test multiple identifiers with different token costs."""

        async def consumer(identifier: str, costs: list[int]):
            for cost in costs:
                await token_bucket.consume(identifier, cost=cost)

        start_time = asyncio.get_event_loop().time()

        # Run two consumers with different cost patterns
        await asyncio.gather(
            consumer("id1", [3, 4, 3]),  # Total: 10
            consumer("id2", [5, 5]),  # Total: 10
        )

        end_time = asyncio.get_event_loop().time()
        # Should be fast since each identifier stays within its limit
        assert end_time - start_time < 0.1

    @pytest.mark.asyncio
    async def test_rapid_burst_after_refill(self, token_bucket):
        """Test rapid burst consumption immediately after token refill."""
        identifier = "test_id"

        # Consume all tokens
        for _ in range(10):
            await token_bucket.consume(identifier)

        # Wait for full refill
        await asyncio.sleep(1)

        # Try to consume 15 tokens rapidly
        start_time = asyncio.get_event_loop().time()
        for _ in range(15):
            await token_bucket.consume(identifier)
        end_time = asyncio.get_event_loop().time()

        # First 10 should be immediate, next 5 should take 0.5 seconds
        assert end_time - start_time >= 0.5

    @pytest.mark.asyncio
    async def test_concurrent_consumers_with_refill(self, token_bucket):
        """Test concurrent consumers with token refill during consumption."""
        identifier = "test_id"
        num_consumers = 3

        async def consumer():
            # Each consumer tries to consume 8 tokens
            for _ in range(8):
                await token_bucket.consume(identifier)
                await asyncio.sleep(0.1)  # Small delay to allow token refill

        start_time = asyncio.get_event_loop().time()
        await asyncio.gather(*(consumer() for _ in range(num_consumers)))
        end_time = asyncio.get_event_loop().time()

        # Should take some time due to rate limiting and refill
        assert end_time - start_time >= 0.5
