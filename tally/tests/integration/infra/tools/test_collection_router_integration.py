"""Integration tests for the CollectionRouterTool class."""

import json
import logging
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.language_models import BaseLanguageModel

from infra.collections.registry import get_schema_registry
from infra.llm.models import ILLMProvider
from infra.tools.collection_router import (
    CollectionRouterOutput,
    CollectionRouterTool,
)


# Configure logging for tests
logger = logging.getLogger(__name__)


@pytest.fixture
def mock_llm_provider():
    """Create a mock ILLMProvider for testing.

    Note: For integration tests, we still mock the LLM to avoid excessive API calls,
    but we use the real schema registry.
    """
    provider = MagicMock(spec=ILLMProvider)

    # Create a properly configured mock for the LLM
    mock_llm = MagicMock(spec=BaseLanguageModel)

    # Create a mock for the with_structured_output method that returns a mock with an ainvoke method
    structured_output_mock = MagicMock()
    # Make the ainvoke method an AsyncMock so it can be awaited
    structured_output_mock.ainvoke = AsyncMock()

    # Make the with_structured_output method return the structured_output_mock
    mock_llm.with_structured_output = MagicMock(return_value=structured_output_mock)

    provider.get_model.return_value = mock_llm
    return provider


class TestCollectionRouterToolIntegration:
    """Integration tests for the CollectionRouterTool.

    These tests use the real schema registry to ensure compatibility with the actual environment.
    """

    @pytest.mark.asyncio
    async def test_basic_sec_query(self, mock_llm_provider):
        """Test routing a basic SEC filing query."""
        # Get actual collection names from the registry
        registry = get_schema_registry()
        collections_json = json.loads(registry.json_schema())

        # Log available collections for debugging
        logger.info(f"Available collections: {[c['name'] for c in collections_json]}")

        # Arrange
        tool = CollectionRouterTool(llm_provider=mock_llm_provider)

        # Configure the expected collections to return
        # This would typically come from an LLM, but we're mocking it for the test
        expected_collections = [
            c["name"]
            for c in collections_json
            if "SEC" in c["name"] or "sec" in c["name"]
        ]
        if not expected_collections:
            expected_collections = [
                collections_json[0]["name"]
            ]  # Fallback if no SEC collection found

        # Configure the LLM mock
        mock_llm = mock_llm_provider.get_model()
        structured_output = mock_llm.with_structured_output.return_value
        structured_output.ainvoke.return_value = CollectionRouterOutput(
            collections=expected_collections
        )

        # Act
        result = await tool.execute(query="What was Apple's revenue in Q1 2023?")

        # Assert
        parsed_result = json.loads(result)
        assert isinstance(parsed_result, list)
        assert len(parsed_result) > 0

        # Validate schema structure for each result
        for collection_schema in parsed_result:
            assert "metadata_schema" in collection_schema

    @pytest.mark.asyncio
    async def test_earnings_call_query(self, mock_llm_provider):
        """Test routing an earnings call query."""
        # Get actual collection names from the registry
        registry = get_schema_registry()
        collections_json = json.loads(registry.json_schema())

        # Arrange
        tool = CollectionRouterTool(llm_provider=mock_llm_provider)

        # Find earnings call or similar collections
        expected_collections = [
            c["name"]
            for c in collections_json
            if "Earnings" in c["name"]
            or "earnings" in c["name"]
            or "call" in c["description"].lower()
        ]
        if not expected_collections:
            pytest.skip("No earnings call collection found in registry")

        # Configure the LLM mock
        mock_llm = mock_llm_provider.get_model()
        structured_output = mock_llm.with_structured_output.return_value
        structured_output.ainvoke.return_value = CollectionRouterOutput(
            collections=expected_collections
        )

        # Act
        result = await tool.execute(
            query="What did Apple's CEO say about AI in the last earnings call?"
        )

        # Assert
        parsed_result = json.loads(result)
        assert isinstance(parsed_result, list)
        assert len(parsed_result) > 0

    @pytest.mark.asyncio
    async def test_query_returning_multiple_collections(self, mock_llm_provider):
        """Test a query that should span multiple collection types."""
        # Get actual collection names from the registry
        registry = get_schema_registry()
        collections_json = json.loads(registry.json_schema())

        # Skip if we don't have at least 2 collections
        if len(collections_json) < 2:
            pytest.skip("Need at least 2 collections for this test")

        # Use the first two collections for the test
        expected_collections = [
            collections_json[0]["name"],
            collections_json[1]["name"],
        ]

        # Arrange
        tool = CollectionRouterTool(llm_provider=mock_llm_provider)

        # Configure the LLM mock
        mock_llm = mock_llm_provider.get_model()
        structured_output = mock_llm.with_structured_output.return_value
        structured_output.ainvoke.return_value = CollectionRouterOutput(
            collections=expected_collections
        )

        # Act
        result = await tool.execute(
            query="Compare Apple's financial performance with what they said in their earnings calls"
        )

        # Assert
        parsed_result = json.loads(result)
        assert isinstance(parsed_result, list)
        assert len(parsed_result) == 2

        # Each collection should have its schema
        for collection_schema in parsed_result:
            assert isinstance(collection_schema, dict)

    @pytest.mark.asyncio
    async def test_empty_result(self, mock_llm_provider):
        """Test what happens when no collections are relevant to the query."""
        # Arrange
        tool = CollectionRouterTool(llm_provider=mock_llm_provider)

        # Configure the LLM mock to return empty collections
        mock_llm = mock_llm_provider.get_model()
        structured_output = mock_llm.with_structured_output.return_value
        structured_output.ainvoke.return_value = CollectionRouterOutput(collections=[])

        # Act
        result = await tool.execute(query="How to bake a chocolate cake?")

        # Assert
        parsed_result = json.loads(result)
        assert isinstance(parsed_result, list)
        assert len(parsed_result) == 0

    @pytest.mark.asyncio
    async def test_nonexistent_collection(self, mock_llm_provider):
        """Test behavior when the LLM returns a collection that doesn't exist."""
        # Arrange
        tool = CollectionRouterTool(llm_provider=mock_llm_provider)

        # Configure the LLM mock to return a non-existent collection
        mock_llm = mock_llm_provider.get_model()
        structured_output = mock_llm.with_structured_output.return_value
        structured_output.ainvoke.return_value = CollectionRouterOutput(
            collections=["NonExistentCollection"]
        )

        # Act & Assert
        # The tool should raise a ValueError when the collection doesn't exist
        with pytest.raises(ValueError) as excinfo:
            await tool.execute(query="Tell me about space exploration")

        # Verify the error message
        assert "NonExistentCollection" in str(excinfo.value)
        assert "not a registered collection" in str(excinfo.value)

        logger.info(
            f"Test verified that tool correctly raises an error for non-existent collections: {str(excinfo.value)}"
        )

    @pytest.mark.asyncio
    async def test_malformed_query(self, mock_llm_provider):
        """Test routing with a malformed or very vague query."""
        # Arrange
        tool = CollectionRouterTool(llm_provider=mock_llm_provider)

        # Configure the LLM mock
        # For a malformed query, the LLM might still make an attempt with the most general collection
        registry = get_schema_registry()
        collections_json = json.loads(registry.json_schema())

        if not collections_json:
            pytest.skip("No collections available in registry")

        # Use the first collection as a fallback
        expected_collections = [collections_json[0]["name"]]

        mock_llm = mock_llm_provider.get_model()
        structured_output = mock_llm.with_structured_output.return_value
        structured_output.ainvoke.return_value = CollectionRouterOutput(
            collections=expected_collections
        )

        # Act
        result = await tool.execute(query="???")

        # Assert
        parsed_result = json.loads(result)
        assert isinstance(parsed_result, list)
        assert len(parsed_result) > 0  # At least one collection should be returned

    @pytest.mark.asyncio
    async def test_very_long_query(self, mock_llm_provider):
        """Test routing with an unusually long query."""
        # Arrange
        tool = CollectionRouterTool(llm_provider=mock_llm_provider)

        # Very long, detailed query
        long_query = """
        I'm looking for comprehensive information about Apple Inc.'s financial performance over the last 5 years,
        specifically focusing on their revenue growth in the services sector compared to hardware sales.
        Additionally, I want to understand how their R&D investments have correlated with new product launches
        and what their executives have said about future AI initiatives during earnings calls.
        I'd also like to compare this data with their major competitors like Microsoft, Google, and Amazon,
        particularly in terms of profit margins and market share in overlapping product categories.
        Finally, I'm interested in analyst predictions about their stock performance for the next fiscal year
        based on these trends and any recent news about supply chain challenges or regulatory issues they might be facing.
        """

        # Get actual collection names from the registry
        registry = get_schema_registry()
        collections_json = json.loads(registry.json_schema())

        if not collections_json:
            pytest.skip("No collections available in registry")

        # For a complex query, multiple collections are likely relevant
        expected_collections = [
            c["name"] for c in collections_json[: min(3, len(collections_json))]
        ]

        # Configure the LLM mock
        mock_llm = mock_llm_provider.get_model()
        structured_output = mock_llm.with_structured_output.return_value
        structured_output.ainvoke.return_value = CollectionRouterOutput(
            collections=expected_collections
        )

        # Act
        result = await tool.execute(query=long_query)

        # Assert
        parsed_result = json.loads(result)
        assert isinstance(parsed_result, list)
        assert len(parsed_result) > 0

    @pytest.mark.asyncio
    async def test_query_with_special_characters(self, mock_llm_provider):
        """Test routing with a query containing special characters."""
        # Arrange
        tool = CollectionRouterTool(llm_provider=mock_llm_provider)

        # Query with special characters
        query_with_special_chars = "What was Apple's profit/loss % in Q2 2023? Also, how did $AAPL perform vs. $MSFT?"

        # Get actual collection names from the registry
        registry = get_schema_registry()
        collections_json = json.loads(registry.json_schema())

        if not collections_json:
            pytest.skip("No collections available in registry")

        # Use the first collection as a fallback
        expected_collections = [collections_json[0]["name"]]

        # Configure the LLM mock
        mock_llm = mock_llm_provider.get_model()
        structured_output = mock_llm.with_structured_output.return_value
        structured_output.ainvoke.return_value = CollectionRouterOutput(
            collections=expected_collections
        )

        # Act
        result = await tool.execute(query=query_with_special_chars)

        # Assert
        parsed_result = json.loads(result)
        assert isinstance(parsed_result, list)
        assert len(parsed_result) > 0

    @pytest.mark.asyncio
    async def test_unexpected_llm_structure(self, mock_llm_provider):
        """Test handling when LLM returns unexpected structure (error handling)."""
        # Arrange
        tool = CollectionRouterTool(llm_provider=mock_llm_provider)

        # Configure the LLM mock to return an unexpected structure that should be handled
        # This tests the robustness of the structured output parsing
        mock_llm = mock_llm_provider.get_model()

        # Create a mock that will cause the with_structured_output().ainvoke() call to fail
        # Either by raising an exception or returning a malformed result
        mock_llm.with_structured_output.side_effect = ValueError(
            "LLM failed to generate valid structured output"
        )

        # Act & Assert
        try:
            await tool.execute(query="What was Apple's revenue?")
            assert False, "Expected an exception but none was raised"
        except ValueError:
            # Expected - the tool should propagate structured output errors
            pass
        except Exception as e:
            # Any other exception would be unexpected
            assert False, f"Expected ValueError but got {type(e).__name__}: {str(e)}"

    @pytest.mark.asyncio
    async def test_multilingual_query(self, mock_llm_provider):
        """Test routing with multilingual content in the query."""
        # Arrange
        tool = CollectionRouterTool(llm_provider=mock_llm_provider)

        # Multilingual query
        multilingual_query = "What was Apple's revenue in 2023? 苹果公司2023年的收入是多少? Quel était le revenu d'Apple en 2023?"

        # Get actual collection names
        registry = get_schema_registry()
        collections_json = json.loads(registry.json_schema())

        if not collections_json:
            pytest.skip("No collections available in registry")

        # Use the first collection
        expected_collections = [collections_json[0]["name"]]

        # Configure the LLM mock
        mock_llm = mock_llm_provider.get_model()
        structured_output = mock_llm.with_structured_output.return_value
        structured_output.ainvoke.return_value = CollectionRouterOutput(
            collections=expected_collections
        )

        # Act
        result = await tool.execute(query=multilingual_query)

        # Assert
        parsed_result = json.loads(result)
        assert isinstance(parsed_result, list)
        assert len(parsed_result) > 0

    @pytest.mark.asyncio
    async def test_performance_with_large_registry(self, mock_llm_provider):
        """Test performance with a potentially large registry."""
        # Arrange
        start_time = time.time()

        tool = CollectionRouterTool(llm_provider=mock_llm_provider)

        # Get actual collection names
        registry = get_schema_registry()
        collections_json = json.loads(registry.json_schema())

        if not collections_json:
            pytest.skip("No collections available in registry")

        # Use all collections to maximize schema data
        expected_collections = [c["name"] for c in collections_json]

        # Configure the LLM mock
        mock_llm = mock_llm_provider.get_model()
        structured_output = mock_llm.with_structured_output.return_value
        structured_output.ainvoke.return_value = CollectionRouterOutput(
            collections=expected_collections
        )

        # Act
        result = await tool.execute(
            query="Comprehensive financial analysis for all major tech companies"
        )

        # Assert
        execution_time = time.time() - start_time
        logger.info(
            f"Tool execution took {execution_time:.2f} seconds with {len(expected_collections)} collections"
        )

        # No hard performance assertion, but log the time taken for monitoring
        parsed_result = json.loads(result)
        assert isinstance(parsed_result, list)
        assert len(parsed_result) > 0

    @pytest.mark.asyncio
    async def test_sequential_same_query_calls(self, mock_llm_provider):
        """Test multiple sequential calls with the same query."""
        # Arrange
        tool = CollectionRouterTool(llm_provider=mock_llm_provider)

        # Get actual collection names
        registry = get_schema_registry()
        collections_json = json.loads(registry.json_schema())

        if not collections_json:
            pytest.skip("No collections available in registry")

        # Use the first collection
        expected_collections = [collections_json[0]["name"]]

        # Configure the LLM mock
        mock_llm = mock_llm_provider.get_model()
        structured_output = mock_llm.with_structured_output.return_value
        structured_output.ainvoke.return_value = CollectionRouterOutput(
            collections=expected_collections
        )

        # Act - Call multiple times with the same query
        query = "What was Apple's revenue in 2023?"
        results = []

        for _ in range(3):
            result = await tool.execute(query=query)
            results.append(json.loads(result))

        # Assert - All results should be consistent
        assert all(isinstance(r, list) for r in results)
        assert all(len(r) == len(expected_collections) for r in results)

    @pytest.mark.asyncio
    async def test_with_numeric_query(self, mock_llm_provider):
        """Test routing with a query that's primarily numeric/financial."""
        # Arrange
        tool = CollectionRouterTool(llm_provider=mock_llm_provider)

        # Numeric/financial query
        numeric_query = "Apple 2023 Q1: Revenue $123.9B, EPS $1.88, Services $20.8B, Products $104.4B"

        # Get actual collection names
        registry = get_schema_registry()
        collections_json = json.loads(registry.json_schema())

        if not collections_json:
            pytest.skip("No collections available in registry")

        # Use collections that seem financial
        expected_collections = [
            c["name"]
            for c in collections_json
            if "SEC" in c["name"] or "Financial" in c["name"]
        ]
        if not expected_collections:
            expected_collections = [collections_json[0]["name"]]

        # Configure the LLM mock
        mock_llm = mock_llm_provider.get_model()
        structured_output = mock_llm.with_structured_output.return_value
        structured_output.ainvoke.return_value = CollectionRouterOutput(
            collections=expected_collections
        )

        # Act
        result = await tool.execute(query=numeric_query)

        # Assert
        parsed_result = json.loads(result)
        assert isinstance(parsed_result, list)
        assert len(parsed_result) > 0

    @pytest.mark.asyncio
    async def test_context_aware_query(self, mock_llm_provider):
        """Test routing with a query that relies on implicit context."""
        # Arrange
        tool = CollectionRouterTool(llm_provider=mock_llm_provider)

        # Context-dependent query
        context_query = "How did their stock price react to that announcement?"

        # Get actual collection names
        registry = get_schema_registry()
        collections_json = json.loads(registry.json_schema())

        if not collections_json:
            pytest.skip("No collections available in registry")

        # For context-reliant queries, news might be more relevant
        expected_collections = [
            c["name"]
            for c in collections_json
            if "News" in c["name"] or "news" in c["description"].lower()
        ]
        if not expected_collections:
            expected_collections = [collections_json[0]["name"]]

        # Configure the LLM mock
        mock_llm = mock_llm_provider.get_model()
        structured_output = mock_llm.with_structured_output.return_value
        structured_output.ainvoke.return_value = CollectionRouterOutput(
            collections=expected_collections
        )

        # Act
        result = await tool.execute(query=context_query)

        # Assert
        parsed_result = json.loads(result)
        assert isinstance(parsed_result, list)
        assert len(parsed_result) > 0
