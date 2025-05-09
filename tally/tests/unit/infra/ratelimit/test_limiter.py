"""Tests for the RateLimiter class."""

import asyncio
from datetime import timedelta

import pytest

from infra.ratelimit.exceptions import RateLimiterConfigError
from infra.ratelimit.limiter import RateLimiter
from infra.ratelimit.models import AlgorithmType, GlobalRateLimiterConfig, RateLimitRule


@pytest.fixture
def token_bucket_rule():
    """Create a sample token bucket rate limit rule."""
    return RateLimitRule(
        limit=10, period=timedelta(seconds=1), algorithm=AlgorithmType.TOKEN_BUCKET
    )


@pytest.fixture
def leaky_bucket_rule():
    """Create a sample leaky bucket rate limit rule."""
    return RateLimitRule(
        limit=10, period=timedelta(seconds=1), algorithm=AlgorithmType.LEAKY_BUCKET
    )


@pytest.fixture
def rate_limiter(token_bucket_rule, leaky_bucket_rule):
    """Create a RateLimiter instance with sample rules."""
    rules = {"token_bucket": token_bucket_rule, "leaky_bucket": leaky_bucket_rule}
    return RateLimiter(rules=rules)


class TestRateLimiter:
    """Tests for the RateLimiter class."""

    def test_init_with_no_rules(self):
        """Test initialization with no rules."""
        limiter = RateLimiter()
        assert limiter.rules == {}
        assert isinstance(limiter.global_config, GlobalRateLimiterConfig)

    def test_init_with_rules(self, token_bucket_rule, leaky_bucket_rule):
        """Test initialization with rules."""
        rules = {"token_bucket": token_bucket_rule, "leaky_bucket": leaky_bucket_rule}
        limiter = RateLimiter(rules=rules)
        assert limiter.rules == rules

    def test_add_rule(self, rate_limiter):
        """Test adding a new rule."""
        new_rule = RateLimitRule(
            limit=5, period=timedelta(seconds=2), algorithm=AlgorithmType.TOKEN_BUCKET
        )
        rate_limiter.add_rule("new_rule", new_rule)
        assert rate_limiter.rules["new_rule"] == new_rule
        assert not rate_limiter._initialized

    @pytest.mark.asyncio
    async def test_acquire_single_rule(self, rate_limiter):
        """Test acquiring a single rule."""
        # Should not raise any exceptions
        await rate_limiter.acquire([("token_bucket", 1)], "test_id")

    @pytest.mark.asyncio
    async def test_acquire_multiple_rules(self, rate_limiter):
        """Test acquiring multiple rules simultaneously."""
        # Should not raise any exceptions
        await rate_limiter.acquire(
            [("token_bucket", 1), ("leaky_bucket", 1)], "test_id"
        )

    @pytest.mark.asyncio
    async def test_acquire_invalid_rule(self, rate_limiter):
        """Test acquiring an invalid rule."""
        with pytest.raises(RateLimiterConfigError):
            await rate_limiter.acquire([("invalid_rule", 1)], "test_id")

    @pytest.mark.asyncio
    async def test_acquire_zero_cost(self, rate_limiter):
        """Test acquiring with zero cost."""
        with pytest.raises(ValueError):
            await rate_limiter.acquire([("token_bucket", 0)], "test_id")

    @pytest.mark.asyncio
    async def test_acquire_negative_cost(self, rate_limiter):
        """Test acquiring with negative cost."""
        with pytest.raises(ValueError):
            await rate_limiter.acquire([("token_bucket", -1)], "test_id")

    @pytest.mark.asyncio
    async def test_concurrent_acquire_same_rule(self, rate_limiter):
        """Test concurrent acquisition of the same rule."""

        async def acquire():
            await rate_limiter.acquire([("token_bucket", 1)], "test_id")

        # Run 15 concurrent acquisitions
        start_time = asyncio.get_event_loop().time()
        await asyncio.gather(*(acquire() for _ in range(15)))
        end_time = asyncio.get_event_loop().time()

        # Should take at least 0.5 seconds (5 tokens / 10 tokens per second)
        assert end_time - start_time >= 0.5

    @pytest.mark.asyncio
    async def test_different_identifiers(self, rate_limiter):
        """Test that different identifiers have separate rate limits."""
        start_time = asyncio.get_event_loop().time()

        # Acquire from two different identifiers simultaneously
        await asyncio.gather(
            rate_limiter.acquire([("token_bucket", 1)], "id1"),
            rate_limiter.acquire([("token_bucket", 1)], "id2"),
        )

        end_time = asyncio.get_event_loop().time()
        # Should be fast since they're different identifiers
        assert end_time - start_time < 0.1

    @pytest.mark.asyncio
    async def test_mixed_algorithm_acquire(self, rate_limiter):
        """Test acquiring from different algorithm types simultaneously."""
        start_time = asyncio.get_event_loop().time()

        # Try to acquire from both token bucket and leaky bucket
        await rate_limiter.acquire(
            [("token_bucket", 5), ("leaky_bucket", 5)], "test_id"
        )

        end_time = asyncio.get_event_loop().time()
        # Should be fast since we're not exceeding either limit
        assert end_time - start_time < 0.1

    @pytest.mark.asyncio
    async def test_rule_addition_after_initialization(self, rate_limiter):
        """Test adding a rule after initialization."""
        # Initialize the rate limiter
        await rate_limiter.acquire([("token_bucket", 1)], "test_id")

        # Add a new rule
        new_rule = RateLimitRule(
            limit=5, period=timedelta(seconds=2), algorithm=AlgorithmType.TOKEN_BUCKET
        )
        rate_limiter.add_rule("new_rule", new_rule)

        # Should be able to acquire from the new rule
        await rate_limiter.acquire([("new_rule", 1)], "test_id")

    @pytest.mark.asyncio
    async def test_high_cost_acquire(self, rate_limiter):
        """Test acquiring with high costs."""
        start_time = asyncio.get_event_loop().time()

        # Try to acquire 8 tokens at once
        await rate_limiter.acquire([("token_bucket", 8)], "test_id")

        # Should be able to acquire 2 more tokens immediately
        await rate_limiter.acquire([("token_bucket", 2)], "test_id")

        end_time = asyncio.get_event_loop().time()
        # Should be fast since total cost equals limit
        assert end_time - start_time < 0.1

    @pytest.mark.asyncio
    async def test_rapid_successive_acquire(self, rate_limiter):
        """Test rapid successive acquisitions."""
        start_time = asyncio.get_event_loop().time()

        # Make 5 rapid acquisitions
        for _ in range(5):
            await rate_limiter.acquire([("token_bucket", 1)], "test_id")
            await asyncio.sleep(0.01)  # Small delay between requests

        end_time = asyncio.get_event_loop().time()
        # Should be fast since we're not exceeding the limit
        assert end_time - start_time < 0.1

    @pytest.mark.asyncio
    async def test_limiter_cleanup(self, rate_limiter):
        """Test cleanup of unused limiters."""
        # Create and use a limiter
        await rate_limiter.acquire([("token_bucket", 1)], "test_id")

        # Get the adapter
        adapter = await rate_limiter._get_or_create_adapter("token_bucket")
        initial_limiters = len(adapter._limiters)

        # Use a different identifier
        await rate_limiter.acquire([("token_bucket", 1)], "new_id")

        # Verify that limiters are properly managed
        assert len(adapter._limiters) == initial_limiters + 1

    @pytest.mark.asyncio
    async def test_concurrent_rule_addition(self, rate_limiter):
        """Test concurrent addition of rules."""

        async def add_rule(rule_name: str):
            rule = RateLimitRule(
                limit=10,
                period=timedelta(seconds=1),
                algorithm=AlgorithmType.TOKEN_BUCKET,
            )
            rate_limiter.add_rule(rule_name, rule)
            await rate_limiter.acquire([(rule_name, 1)], "test_id")

        # Add multiple rules concurrently
        await asyncio.gather(add_rule("rule1"), add_rule("rule2"), add_rule("rule3"))

        # Verify all rules were added and are usable
        assert "rule1" in rate_limiter.rules
        assert "rule2" in rate_limiter.rules
        assert "rule3" in rate_limiter.rules

    @pytest.mark.asyncio
    async def test_mixed_cost_multiple_rules(self, rate_limiter):
        """Test mixed cost consumption across multiple rules."""
        start_time = asyncio.get_event_loop().time()

        # Try to acquire different costs from different rules
        await rate_limiter.acquire(
            [
                ("token_bucket", 3),
                ("leaky_bucket", 4),
                ("token_bucket", 2),
                ("leaky_bucket", 1),
            ],
            "test_id",
        )

        end_time = asyncio.get_event_loop().time()
        # Should be fast since we're not exceeding any limits
        assert end_time - start_time < 0.1

    @pytest.mark.asyncio
    async def test_rule_modification(self, rate_limiter):
        """Test modifying an existing rule."""
        # Add initial rule
        initial_rule = RateLimitRule(
            limit=5, period=timedelta(seconds=1), algorithm=AlgorithmType.TOKEN_BUCKET
        )
        rate_limiter.add_rule("modifiable_rule", initial_rule)

        # Modify the rule
        modified_rule = RateLimitRule(
            limit=10, period=timedelta(seconds=2), algorithm=AlgorithmType.TOKEN_BUCKET
        )
        rate_limiter.add_rule("modifiable_rule", modified_rule)

        # Verify the rule was updated
        assert rate_limiter.rules["modifiable_rule"] == modified_rule
        assert not rate_limiter._initialized  # Should trigger reinitialization

    @pytest.mark.asyncio
    async def test_rapid_rule_changes(self, rate_limiter):
        """Test rapid changes to rules with concurrent access."""

        async def modify_and_use(rule_name: str, limit: int):
            rule = RateLimitRule(
                limit=limit,
                period=timedelta(seconds=1),
                algorithm=AlgorithmType.TOKEN_BUCKET,
            )
            rate_limiter.add_rule(rule_name, rule)
            await rate_limiter.acquire([(rule_name, 1)], "test_id")

        # Rapidly modify and use rules
        await asyncio.gather(
            modify_and_use("dynamic_rule", 5),
            modify_and_use("dynamic_rule", 10),
            modify_and_use("dynamic_rule", 15),
        )

        # Verify the final rule state
        assert rate_limiter.rules["dynamic_rule"].limit == 15

    @pytest.mark.asyncio
    async def test_error_handling_zero_limit(self, rate_limiter):
        """Test error handling for zero limit."""
        with pytest.raises(ValueError):
            invalid_rule = RateLimitRule(
                limit=0,  # Invalid zero limit
                period=timedelta(seconds=1),
                algorithm=AlgorithmType.TOKEN_BUCKET,
            )
            rate_limiter.add_rule("invalid_rule", invalid_rule)
