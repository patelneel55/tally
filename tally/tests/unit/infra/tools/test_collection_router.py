"""Tests for the CollectionRouterTool class."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.language_models import BaseLanguageModel
from langchain_core.prompts import ChatPromptTemplate

from infra.llm.models import ILLMProvider
from infra.tools.collection_router import (
    CollectionRouterOutput,
    CollectionRouterTool,
)


@pytest.fixture
def mock_llm_provider():
    """Create a mock ILLMProvider for testing."""
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


@pytest.fixture
def mock_schema_registry():
    """Create a mock schema registry for testing."""
    registry = MagicMock()

    # Define sample collections for the test
    collections = [
        {
            "name": "SECFilings",
            "description": "Contains SEC filing documents including 10-K, 10-Q, and 8-K reports",
        },
        {
            "name": "EarningsCallChunk",
            "description": "Contains transcripts from company earnings calls",
        },
        {
            "name": "NewsChunk",
            "description": "Contains financial news articles and press releases",
        },
        {
            "name": "AnalystReports",
            "description": "Contains reports from financial analysts about companies and markets",
        },
        {
            "name": "CompanyProfiles",
            "description": "Contains detailed company information and background",
        },
    ]

    # Mock the json_schema method to return the collection list
    registry.json_schema.return_value = json.dumps(collections)

    # Mock the get_collection method to return a mock collection with json_schema
    mock_collection = MagicMock()
    mock_collection.json_schema.return_value = json.dumps(
        {"metadata_fields": ["ticker", "period"]}
    )
    registry.get_collection.return_value = mock_collection

    return registry


@pytest.mark.parametrize(
    "query,expected_collections",
    [
        ("What was Apple's revenue in Q1 2023?", ["SECFilings", "EarningsCallChunk"]),
        ("Find recent news about Tesla's stock performance", ["NewsChunk"]),
        (
            "What did the CEO say about future growth in the last earnings call?",
            ["EarningsCallChunk"],
        ),
        ("Compare the balance sheets of Microsoft and Google", ["SECFilings"]),
        ("Show me all financial statements for Amazon", ["SECFilings"]),
        # More complex queries
        (
            "How has Apple's gross margin changed compared to analyst expectations?",
            ["SECFilings", "AnalystReports", "EarningsCallChunk"],
        ),
        (
            "What is the competitive landscape for Microsoft's cloud services?",
            ["AnalystReports", "NewsChunk", "CompanyProfiles"],
        ),
        (
            "How does Tesla's revenue from energy products compare to its automotive revenue?",
            ["SECFilings"],
        ),
        (
            "Show me what financial experts are saying about Google's latest acquisition",
            ["NewsChunk", "AnalystReports"],
        ),
    ],
)
class TestCollectionRouterTool:
    """Tests for the CollectionRouterTool class."""

    @pytest.mark.asyncio
    async def test_execute(
        self, query, expected_collections, mock_llm_provider, mock_schema_registry
    ):
        """Test the execute method of CollectionRouterTool."""
        # Arrange
        with patch(
            "infra.tools.collection_router.get_schema_registry",
            return_value=mock_schema_registry,
        ):
            tool = CollectionRouterTool(llm_provider=mock_llm_provider)

            # Configure the LLM mock to return the expected collections
            mock_llm = mock_llm_provider.get_model()
            structured_output = mock_llm.with_structured_output.return_value
            structured_output.ainvoke.return_value = CollectionRouterOutput(
                collections=expected_collections
            )

            # Act
            result = await tool.execute(query=query)

            # Assert
            # Verify LLM's with_structured_output was called with CollectionRouterOutput
            mock_llm.with_structured_output.assert_called_once_with(
                CollectionRouterOutput
            )

            # Verify that structured_output.ainvoke was called with a prompt
            structured_output.ainvoke.assert_called_once()

            # Verify that execute returns a JSON string
            parsed_result = json.loads(result)
            assert isinstance(parsed_result, list)
            assert len(parsed_result) == len(expected_collections)

            # Verify collections were retrieved from registry
            for collection in expected_collections:
                mock_schema_registry.get_collection.assert_any_call(collection)


# Non-parameterized tests
class TestCollectionRouterToolAdditional:
    """Additional tests for the CollectionRouterTool class that don't use parameterization."""

    @pytest.mark.asyncio
    async def test_execute_with_empty_result(
        self, mock_llm_provider, mock_schema_registry
    ):
        """Test the execute method when no collections are relevant."""
        # Arrange
        with patch(
            "infra.tools.collection_router.get_schema_registry",
            return_value=mock_schema_registry,
        ):
            tool = CollectionRouterTool(llm_provider=mock_llm_provider)

            # Configure the LLM mock to return empty collections
            mock_llm = mock_llm_provider.get_model()
            structured_output = mock_llm.with_structured_output.return_value
            structured_output.ainvoke.return_value = CollectionRouterOutput(
                collections=[]
            )

            # Act
            result = await tool.execute(query="How to bake a cake?")

            # Assert
            parsed_result = json.loads(result)
            assert isinstance(parsed_result, list)
            assert len(parsed_result) == 0

            # Verify the JSON schema was retrieved but no collections were looked up
            mock_schema_registry.json_schema.assert_called_once()
            mock_schema_registry.get_collection.assert_not_called()

    @pytest.mark.asyncio
    async def test_lazy_loading_of_llm(self, mock_llm_provider, mock_schema_registry):
        """Test lazy loading of the LLM."""
        # Arrange
        with patch(
            "infra.tools.collection_router.get_schema_registry",
            return_value=mock_schema_registry,
        ):
            tool = CollectionRouterTool(llm_provider=mock_llm_provider)

            # Act - Get the LLM
            tool._llm()

            # Assert
            # Verify the LLM was loaded
            mock_llm_provider.get_model.assert_called_once()
            # Second call should not reload the LLM
            tool._llm()
            # Provider should still be called only once
            mock_llm_provider.get_model.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_invalid_input(
        self, mock_llm_provider, mock_schema_registry
    ):
        """Test execute method with invalid input."""
        # Arrange
        with patch(
            "infra.tools.collection_router.get_schema_registry",
            return_value=mock_schema_registry,
        ):
            tool = CollectionRouterTool(llm_provider=mock_llm_provider)

            # Act & Assert
            with pytest.raises(ValueError):
                # Missing required 'query' parameter
                await tool.execute()

    @pytest.mark.asyncio
    async def test_execute_handles_llm_error(
        self, mock_llm_provider, mock_schema_registry
    ):
        """Test that the execute method properly handles LLM errors."""
        # Arrange
        with patch(
            "infra.tools.collection_router.get_schema_registry",
            return_value=mock_schema_registry,
        ):
            tool = CollectionRouterTool(llm_provider=mock_llm_provider)

            # Configure the LLM mock to raise an exception
            mock_llm = mock_llm_provider.get_model()
            structured_output = mock_llm.with_structured_output.return_value
            structured_output.ainvoke.side_effect = Exception("LLM error")

            # Act & Assert
            with pytest.raises(Exception, match="LLM error"):
                await tool.execute(query="What was Apple's revenue?")

    @pytest.mark.asyncio
    async def test_with_empty_query(self, mock_llm_provider, mock_schema_registry):
        """Test with an empty query string."""
        # Arrange
        with patch(
            "infra.tools.collection_router.get_schema_registry",
            return_value=mock_schema_registry,
        ):
            tool = CollectionRouterTool(llm_provider=mock_llm_provider)

            # Configure the LLM mock
            mock_llm = mock_llm_provider.get_model()
            structured_output = mock_llm.with_structured_output.return_value
            structured_output.ainvoke.return_value = CollectionRouterOutput(
                collections=["SECFilings"]
            )

            # Act & Assert
            # Empty string should be considered valid but might return defaults
            result = await tool.execute(query="")

            # Verify prompt was created with empty query
            call_args = structured_output.ainvoke.call_args[0][0]
            assert isinstance(call_args, object)  # Should be a prompt object

            # Verify result structure
            parsed_result = json.loads(result)
            assert isinstance(parsed_result, list)
            assert len(parsed_result) == 1

    @pytest.mark.asyncio
    async def test_with_very_long_query(self, mock_llm_provider, mock_schema_registry):
        """Test with an unusually long query."""
        # Arrange
        with patch(
            "infra.tools.collection_router.get_schema_registry",
            return_value=mock_schema_registry,
        ):
            tool = CollectionRouterTool(llm_provider=mock_llm_provider)

            # Create a very long query (10K+ characters)
            long_query = "What is Apple's financial performance? " * 500

            # Configure the LLM mock
            mock_llm = mock_llm_provider.get_model()
            structured_output = mock_llm.with_structured_output.return_value
            structured_output.ainvoke.return_value = CollectionRouterOutput(
                collections=["SECFilings"]
            )

            # Act
            result = await tool.execute(query=long_query)

            # Assert
            parsed_result = json.loads(result)
            assert isinstance(parsed_result, list)
            assert len(parsed_result) == 1

    @pytest.mark.asyncio
    async def test_with_unicode_characters(
        self, mock_llm_provider, mock_schema_registry
    ):
        """Test with non-ASCII Unicode characters in the query."""
        # Arrange
        with patch(
            "infra.tools.collection_router.get_schema_registry",
            return_value=mock_schema_registry,
        ):
            tool = CollectionRouterTool(llm_provider=mock_llm_provider)

            # Unicode query with various non-ASCII characters
            unicode_query = "What is Xiaomi (小米)'s revenue in 2023? How about Tencent (腾讯)? €£¥₹"

            # Configure the LLM mock
            mock_llm = mock_llm_provider.get_model()
            structured_output = mock_llm.with_structured_output.return_value
            structured_output.ainvoke.return_value = CollectionRouterOutput(
                collections=["SECFilings"]
            )

            # Act
            result = await tool.execute(query=unicode_query)

            # Assert
            parsed_result = json.loads(result)
            assert isinstance(parsed_result, list)
            assert len(parsed_result) == 1

    @pytest.mark.asyncio
    async def test_prompt_template_content(
        self, mock_llm_provider, mock_schema_registry
    ):
        """Test that the prompt template contains expected content."""
        # Arrange
        with patch(
            "infra.tools.collection_router.get_schema_registry",
            return_value=mock_schema_registry,
        ):
            tool = CollectionRouterTool(llm_provider=mock_llm_provider)

            # Verify prompt template structure
            assert hasattr(tool, "_prompt_template")
            assert isinstance(tool._prompt_template, ChatPromptTemplate)

            # Extract template content
            template_str = str(tool._prompt_template)

            # Verify template contains key words/phrases
            assert "query" in template_str.lower()
            assert "collections" in template_str.lower()

    @pytest.mark.asyncio
    async def test_with_complex_query_characters(
        self, mock_llm_provider, mock_schema_registry
    ):
        """Test with query containing SQL-like or code-like content."""
        # Arrange
        with patch(
            "infra.tools.collection_router.get_schema_registry",
            return_value=mock_schema_registry,
        ):
            tool = CollectionRouterTool(llm_provider=mock_llm_provider)

            # Query with special characters that might confuse parsers
            complex_query = "Show me revenue WHERE quarter='Q1' AND year=2023 AND company='Apple'; -- not actually SQL"

            # Configure the LLM mock
            mock_llm = mock_llm_provider.get_model()
            structured_output = mock_llm.with_structured_output.return_value
            structured_output.ainvoke.return_value = CollectionRouterOutput(
                collections=["SECFilings"]
            )

            # Act
            result = await tool.execute(query=complex_query)

            # Assert
            parsed_result = json.loads(result)
            assert isinstance(parsed_result, list)
            assert len(parsed_result) == 1
