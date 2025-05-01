from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from infra.collections.models import BaseMetadata, ChunkType
from infra.llm.models import ILLMProvider
from infra.pipelines.mem_walker import (
    DecisionType,
    MemoryTreeNode,
    MemWalker,
    NavigationDecision,
    NavigationLogStep,
    Output,
    SummaryContext,
)


class TestMemoryTreeNode:
    def test_memory_tree_node_creation(self):
        """Test creating a MemoryTreeNode with minimal fields."""
        node = MemoryTreeNode(
            id="test-id", summary="Test summary", content="Test content"
        )

        assert node.id == "test-id"
        assert node.summary == "Test summary"
        assert node.content == "Test content"
        assert node.node_type == ChunkType.TEXT
        assert node.metadata is None
        assert node.children == []

    def test_memory_tree_node_with_children(self):
        """Test creating a MemoryTreeNode with children."""
        child_node = MemoryTreeNode(
            id="child-id", summary="Child summary", content="Child content"
        )

        parent_node = MemoryTreeNode(
            id="parent-id",
            summary="Parent summary",
            content="Parent content",
            children=[child_node],
        )

        assert len(parent_node.children) == 1
        assert parent_node.children[0].id == "child-id"

    def test_memory_tree_node_with_all_fields(self):
        """Test creating a MemoryTreeNode with all fields specified."""
        metadata = BaseMetadata(source="test-source", chunk_type=ChunkType.TEXT)

        node = MemoryTreeNode(
            id="test-id",
            summary="Test summary",
            content="Test content",
            node_type=ChunkType.TEXT,
            metadata=metadata,
            children=[],
        )

        assert node.id == "test-id"
        assert node.summary == "Test summary"
        assert node.content == "Test content"
        assert node.node_type == ChunkType.TEXT
        assert node.metadata.source == "test-source"
        assert node.children == []

    def test_memory_tree_node_nested_hierarchy(self):
        """Test creating a MemoryTreeNode with multiple levels of nesting."""
        grandchild = MemoryTreeNode(
            id="grandchild-id",
            summary="Grandchild summary",
            content="Grandchild content",
        )

        child = MemoryTreeNode(
            id="child-id",
            summary="Child summary",
            content="Child content",
            children=[grandchild],
        )

        parent = MemoryTreeNode(
            id="parent-id",
            summary="Parent summary",
            content="Parent content",
            children=[child],
        )

        assert len(parent.children) == 1
        assert parent.children[0].id == "child-id"
        assert len(parent.children[0].children) == 1
        assert parent.children[0].children[0].id == "grandchild-id"

    def test_memory_tree_node_serialization(self):
        """Test that MemoryTreeNode can be properly serialized to JSON."""
        node = MemoryTreeNode(
            id="test-id", summary="Test summary", content="Test content"
        )

        serialized = node.model_dump_json()
        deserialized = MemoryTreeNode.model_validate_json(serialized)

        assert deserialized.id == node.id
        assert deserialized.summary == node.summary
        assert deserialized.content == node.content
        assert deserialized.node_type == node.node_type

    def test_memory_tree_node_with_empty_summary(self):
        """Test creating a MemoryTreeNode with an empty summary."""
        node = MemoryTreeNode(id="test-id", summary="", content="Test content")

        assert node.id == "test-id"
        assert node.summary == ""
        assert node.content == "Test content"


class TestNavigationDecision:
    def test_navigation_decision_creation(self):
        """Test creating a NavigationDecision."""
        decision = NavigationDecision(
            decision=DecisionType.ExploreChildren,
            reasoning="This node has relevant children",
            next_children_ids=["child-1", "child-2"],
            confidence=0.9,
        )

        assert decision.decision == DecisionType.ExploreChildren
        assert decision.reasoning == "This node has relevant children"
        assert decision.next_children_ids == ["child-1", "child-2"]
        assert decision.confidence == 0.9

    def test_navigation_decision_answer_here(self):
        """Test creating a NavigationDecision with AnswerHere decision type."""
        decision = NavigationDecision(
            decision=DecisionType.AnswerHere,
            reasoning="This node contains the answer",
            confidence=0.95,
        )

        assert decision.decision == DecisionType.AnswerHere
        assert decision.reasoning == "This node contains the answer"
        assert decision.next_children_ids is None
        assert decision.confidence == 0.95

    def test_navigation_decision_dead_end(self):
        """Test creating a NavigationDecision with DeadEnd decision type."""
        decision = NavigationDecision(
            decision=DecisionType.DeadEnd,
            reasoning="This path is not relevant",
            confidence=0.85,
        )

        assert decision.decision == DecisionType.DeadEnd
        assert decision.reasoning == "This path is not relevant"
        assert decision.next_children_ids is None
        assert decision.confidence == 0.85

    def test_navigation_decision_default_reasoning(self):
        """Test creating a NavigationDecision with default reasoning."""
        decision = NavigationDecision(decision=DecisionType.DeadEnd, confidence=0.7)

        assert decision.decision == DecisionType.DeadEnd
        assert decision.reasoning == "No reasoning provided."
        assert decision.next_children_ids is None
        assert decision.confidence == 0.7

    def test_navigation_decision_empty_children_list(self):
        """Test creating a NavigationDecision with an empty children list."""
        decision = NavigationDecision(
            decision=DecisionType.ExploreChildren,
            reasoning="No relevant children but still exploring",
            next_children_ids=[],
            confidence=0.6,
        )

        assert decision.decision == DecisionType.ExploreChildren
        assert decision.reasoning == "No relevant children but still exploring"
        assert decision.next_children_ids == []
        assert decision.confidence == 0.6

    @pytest.mark.parametrize("confidence", [0.0, 0.5, 1.0])
    def test_navigation_decision_confidence_range(self, confidence):
        """Test creating a NavigationDecision with various valid confidence values."""
        decision = NavigationDecision(
            decision=DecisionType.AnswerHere,
            reasoning="Testing confidence",
            confidence=confidence,
        )

        assert decision.confidence == confidence

    def test_navigation_decision_serialization(self):
        """Test that NavigationDecision can be properly serialized to JSON."""
        decision = NavigationDecision(
            decision=DecisionType.ExploreChildren,
            reasoning="Testing serialization",
            next_children_ids=["child-1", "child-2"],
            confidence=0.85,
        )

        serialized = decision.model_dump_json()
        deserialized = NavigationDecision.model_validate_json(serialized)

        assert deserialized.decision == decision.decision
        assert deserialized.reasoning == decision.reasoning
        assert deserialized.next_children_ids == decision.next_children_ids
        assert deserialized.confidence == decision.confidence

    def test_navigation_decision_with_next_children_ids_for_non_explore(self):
        """Test that next_children_ids can be provided but ignored for non-ExploreChildren decisions."""
        decision = NavigationDecision(
            decision=DecisionType.AnswerHere,
            reasoning="Testing with next_children_ids for AnswerHere",
            next_children_ids=["should-be-ignored"],
            confidence=0.75,
        )

        # The next_children_ids is allowed but not used for AnswerHere
        assert decision.next_children_ids == ["should-be-ignored"]

    def test_compare_navigation_decisions(self):
        """Test comparing two NavigationDecision objects by confidence."""
        high_confidence = NavigationDecision(
            decision=DecisionType.AnswerHere,
            reasoning="High confidence answer",
            confidence=0.95,
        )

        low_confidence = NavigationDecision(
            decision=DecisionType.AnswerHere,
            reasoning="Low confidence answer",
            confidence=0.6,
        )

        assert high_confidence.confidence > low_confidence.confidence

    @pytest.mark.parametrize("invalid_confidence", [-0.1, 1.1, 2.0])
    def test_navigation_decision_invalid_confidence(self, invalid_confidence):
        """Test that creating a NavigationDecision with invalid confidence values raises ValidationError."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            NavigationDecision(
                decision=DecisionType.AnswerHere,
                reasoning="Testing invalid confidence",
                confidence=invalid_confidence,
            )


class TestSummaryContext:
    def test_summary_context_creation(self):
        """Test creating a SummaryContext."""
        context = SummaryContext(
            node_id="test-id",
            summary_text="Test summary",
            reasoning="This node is relevant",
            confidence=0.85,
        )

        assert context.node_id == "test-id"
        assert context.summary_text == "Test summary"
        assert context.reasoning == "This node is relevant"
        assert context.confidence == 0.85

    def test_summary_context_without_confidence(self):
        """Test creating a SummaryContext without confidence."""
        context = SummaryContext(
            node_id="test-id",
            summary_text="Test summary",
            reasoning="This node is relevant",
        )

        assert context.node_id == "test-id"
        assert context.summary_text == "Test summary"
        assert context.reasoning == "This node is relevant"
        assert context.confidence is None

    def test_summary_context_serialization(self):
        """Test that SummaryContext can be properly serialized to JSON."""
        context = SummaryContext(
            node_id="test-id",
            summary_text="Test summary",
            reasoning="This node is relevant",
            confidence=0.85,
        )

        serialized = context.model_dump_json()
        deserialized = SummaryContext.model_validate_json(serialized)

        assert deserialized.node_id == context.node_id
        assert deserialized.summary_text == context.summary_text
        assert deserialized.reasoning == context.reasoning
        assert deserialized.confidence == context.confidence

    @pytest.mark.parametrize("confidence", [0.0, 0.5, 1.0])
    def test_summary_context_valid_confidence(self, confidence):
        """Test creating a SummaryContext with valid confidence values."""
        context = SummaryContext(
            node_id="test-id",
            summary_text="Test summary",
            reasoning="This node is relevant",
            confidence=confidence,
        )

        assert context.confidence == confidence

    @pytest.mark.parametrize("invalid_confidence", [-0.1, 1.1, 2.0])
    def test_summary_context_invalid_confidence(self, invalid_confidence):
        """Test that creating a SummaryContext with invalid confidence raises ValidationError."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SummaryContext(
                node_id="test-id",
                summary_text="Test summary",
                reasoning="This node is relevant",
                confidence=invalid_confidence,
            )

    def test_summary_context_with_long_reasoning(self):
        """Test creating a SummaryContext with a very long reasoning text."""
        long_reasoning = "This is a very long reasoning text. " * 50  # Repeat 50 times

        context = SummaryContext(
            node_id="test-id",
            summary_text="Test summary",
            reasoning=long_reasoning,
            confidence=0.75,
        )

        assert context.reasoning == long_reasoning
        assert len(context.reasoning) > 1000


class TestOutput:
    def test_output_creation(self):
        """Test creating an Output."""
        context = SummaryContext(
            node_id="test-id",
            summary_text="Test summary",
            reasoning="This node is relevant",
            confidence=0.85,
        )

        log_step = NavigationLogStep(
            step=1,
            visited_node_id="test-id",
            visited_node_summary="Test summary",
            llm_decision=NavigationDecision(
                decision=DecisionType.AnswerHere,
                reasoning="This node has the answer",
                confidence=0.9,
            ),
        )

        output = Output(collected_context=[context], navigation_log=[log_step])

        assert len(output.collected_context) == 1
        assert output.collected_context[0].node_id == "test-id"
        assert len(output.navigation_log) == 1
        assert output.navigation_log[0].step == 1

    def test_output_with_empty_collections(self):
        """Test creating an Output with empty collections."""
        output = Output()

        assert output.collected_context == []
        assert output.navigation_log == []

    def test_output_with_multiple_contexts(self):
        """Test creating an Output with multiple context entries."""
        context1 = SummaryContext(
            node_id="test-id-1",
            summary_text="Test summary 1",
            reasoning="This node is relevant",
            confidence=0.85,
        )

        context2 = SummaryContext(
            node_id="test-id-2",
            summary_text="Test summary 2",
            reasoning="This node is also relevant",
            confidence=0.75,
        )

        output = Output(collected_context=[context1, context2])

        assert len(output.collected_context) == 2
        assert output.collected_context[0].node_id == "test-id-1"
        assert output.collected_context[1].node_id == "test-id-2"

    def test_output_with_multiple_log_steps(self):
        """Test creating an Output with multiple navigation log steps."""
        log_step1 = NavigationLogStep(
            step=1,
            visited_node_id="test-id-1",
            visited_node_summary="Test summary 1",
            llm_decision=NavigationDecision(
                decision=DecisionType.ExploreChildren,
                reasoning="Exploring children",
                next_children_ids=["child-1"],
                confidence=0.9,
            ),
        )

        log_step2 = NavigationLogStep(
            step=2,
            visited_node_id="child-1",
            visited_node_summary="Child summary",
            llm_decision=NavigationDecision(
                decision=DecisionType.AnswerHere,
                reasoning="This node has the answer",
                confidence=0.95,
            ),
        )

        output = Output(navigation_log=[log_step1, log_step2])

        assert len(output.navigation_log) == 2
        assert output.navigation_log[0].step == 1
        assert output.navigation_log[1].step == 2
        assert output.navigation_log[0].visited_node_id == "test-id-1"
        assert output.navigation_log[1].visited_node_id == "child-1"

    def test_output_serialization(self):
        """Test that Output can be properly serialized to JSON."""
        context = SummaryContext(
            node_id="test-id",
            summary_text="Test summary",
            reasoning="This node is relevant",
            confidence=0.85,
        )

        log_step = NavigationLogStep(
            step=1,
            visited_node_id="test-id",
            visited_node_summary="Test summary",
            llm_decision=NavigationDecision(
                decision=DecisionType.AnswerHere,
                reasoning="This node has the answer",
                confidence=0.9,
            ),
        )

        output = Output(collected_context=[context], navigation_log=[log_step])

        serialized = output.model_dump_json()
        deserialized = Output.model_validate_json(serialized)

        assert len(deserialized.collected_context) == 1
        assert deserialized.collected_context[0].node_id == "test-id"
        assert len(deserialized.navigation_log) == 1
        assert deserialized.navigation_log[0].step == 1


class MockLLMProvider(ILLMProvider):
    def __init__(self, mock_responses: List[Dict[str, Any]]):
        self.mock_responses = mock_responses
        self.response_index = 0

    def get_model(self):
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock()

        # Configure the mock to return different responses for each call
        async def side_effect(*args, **kwargs):
            if self.response_index < len(self.mock_responses):
                response = self.mock_responses[self.response_index]
                self.response_index += 1
                return NavigationDecision(**response)
            return NavigationDecision(
                decision=DecisionType.DeadEnd,
                reasoning="Default mock response",
                confidence=0.5,
            )

        mock_llm.ainvoke.side_effect = side_effect
        return mock_llm

    def estimate_tokens(self, prompt: str) -> int:
        return 1


@pytest.fixture
def mock_llm_provider():
    """Create a mock LLM provider with predefined responses."""
    mock_responses = [
        {
            "decision": DecisionType.ExploreChildren,
            "reasoning": "This node has relevant children",
            "next_children_ids": ["child-1"],
            "confidence": 0.9,
        },
        {
            "decision": DecisionType.AnswerHere,
            "reasoning": "This node has the answer",
            "confidence": 0.95,
        },
    ]
    return MockLLMProvider(mock_responses)


@pytest.fixture
def sample_memory_tree():
    """Create a sample memory tree for testing."""
    child_1 = MemoryTreeNode(
        id="child-1", summary="Child 1 summary", content="Child 1 content"
    )

    child_2 = MemoryTreeNode(
        id="child-2", summary="Child 2 summary", content="Child 2 content"
    )

    root_node = MemoryTreeNode(
        id="root",
        summary="Root summary",
        content="Root content",
        children=[child_1, child_2],
    )

    return root_node


class TestMemWalker:
    def test_init(self, mock_llm_provider):
        """Test initializing a MemWalker."""
        walker = MemWalker(llm_provider=mock_llm_provider)

        assert walker.llm_provider == mock_llm_provider
        assert walker.max_llm_calls == 20
        assert walker._llm_instance is None

    def test_get_child_summaries(self, sample_memory_tree):
        """Test _get_child_summaries method."""
        walker = MemWalker(llm_provider=MagicMock())
        summaries = walker._get_child_summaries(sample_memory_tree)

        assert len(summaries) == 2
        assert summaries["child-1"] == "Child 1 summary"
        assert summaries["child-2"] == "Child 2 summary"

    def test_get_child_by_id(self, sample_memory_tree):
        """Test _get_child_by_id method."""
        walker = MemWalker(llm_provider=MagicMock())

        child = walker._get_child_by_id(sample_memory_tree, "child-1")
        assert child is not None
        assert child.id == "child-1"

        nonexistent_child = walker._get_child_by_id(sample_memory_tree, "nonexistent")
        assert nonexistent_child is None

    def test_get_child_by_id_with_none_children(self):
        """Test _get_child_by_id with None children."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            MemoryTreeNode(
                id="test",
                summary="Test",
                content="Test content",
                children=[
                    None,
                    MemoryTreeNode(
                        id="valid", summary="Valid", content="Valid content"
                    ),
                ],
            )

    @pytest.mark.asyncio
    async def test_make_navigation_decision(
        self, mock_llm_provider, sample_memory_tree
    ):
        """Test make_navigation_decision method."""
        walker = MemWalker(llm_provider=mock_llm_provider)

        child_summaries = walker._get_child_summaries(sample_memory_tree)
        decision = await walker.make_navigation_decision(
            query="test query",
            current_node=sample_memory_tree,
            child_summaries=child_summaries,
        )

        assert decision.decision == DecisionType.ExploreChildren
        assert decision.next_children_ids == ["child-1"]
        assert decision.confidence == 0.9

    @pytest.mark.asyncio
    async def test_navigate_tree(self, mock_llm_provider, sample_memory_tree):
        """Test navigate_tree method."""
        walker = MemWalker(llm_provider=mock_llm_provider)

        output = await walker.navigate_tree(
            query="test query", root_node=sample_memory_tree
        )

        assert len(output.navigation_log) == 2
        assert output.navigation_log[0].visited_node_id == "root"
        assert output.navigation_log[1].visited_node_id == "child-1"

        assert len(output.collected_context) == 1
        assert output.collected_context[0].node_id == "child-1"

    @pytest.mark.asyncio
    async def test_navigate_tree_max_calls(self, mock_llm_provider):
        """Test navigate_tree with max_llm_calls limit."""
        # Create a circular tree to test max_llm_calls
        node1 = MemoryTreeNode(id="node1", summary="Node 1", content="Content 1")
        node2 = MemoryTreeNode(id="node2", summary="Node 2", content="Content 2")
        node1.children = [node2]
        node2.children = [node1]

        # Create a walker with only 1 max call
        walker = MemWalker(llm_provider=mock_llm_provider, max_llm_calls=1)

        output = await walker.navigate_tree(query="test query", root_node=node1)

        # Should only have made one call despite the circular reference
        assert len(output.navigation_log) == 1

    @pytest.mark.asyncio
    async def test_navigate_tree_deadend(self):
        """Test navigate_tree with a deadend decision."""
        # Create a mock LLM provider that returns a deadend decision
        mock_provider = MockLLMProvider(
            [
                {
                    "decision": DecisionType.DeadEnd,
                    "reasoning": "This is a dead end",
                    "confidence": 0.8,
                }
            ]
        )

        node = MemoryTreeNode(id="test", summary="Test", content="Test content")

        walker = MemWalker(llm_provider=mock_provider)
        output = await walker.navigate_tree(query="test query", root_node=node)

        assert len(output.navigation_log) == 1
        assert output.navigation_log[0].llm_decision.decision == DecisionType.DeadEnd
        assert len(output.collected_context) == 0

    @pytest.mark.asyncio
    async def test_navigate_tree_cycle_detection(self, mock_llm_provider):
        """Test that navigate_tree doesn't get stuck in cycles."""
        # Create a mock LLM provider that keeps returning ExploreChildren
        mock_responses = []
        for _ in range(5):
            mock_responses.append(
                {
                    "decision": DecisionType.ExploreChildren,
                    "reasoning": "Exploring children",
                    "next_children_ids": ["child-1"],
                    "confidence": 0.9,
                }
            )

        provider = MockLLMProvider(mock_responses)

        # Create a circular tree
        child = MemoryTreeNode(id="child-1", summary="Child", content="Child content")
        root = MemoryTreeNode(
            id="root", summary="Root", content="Root content", children=[child]
        )

        walker = MemWalker(llm_provider=provider, max_llm_calls=10)
        output = await walker.navigate_tree(query="test query", root_node=root)

        # Should have detected and handled the cycle
        assert len(output.navigation_log) <= 2  # Root and child only

    def test_llm_lazy_loading(self, mock_llm_provider):
        """Test that _llm method lazy loads the LLM instance."""
        walker = MemWalker(llm_provider=mock_llm_provider)

        # Initially the instance should be None
        assert walker._llm_instance is None

        # After calling _llm(), it should be set
        llm = walker._llm()
        assert walker._llm_instance is not None

        # Subsequent calls should use the same instance
        llm2 = walker._llm()
        assert llm is llm2

    def test_custom_max_llm_calls(self):
        """Test initializing a MemWalker with custom max_llm_calls."""
        walker = MemWalker(llm_provider=MagicMock(), max_llm_calls=50)

        assert walker.max_llm_calls == 50

    @pytest.mark.asyncio
    async def test_navigate_tree_with_empty_children(self):
        """Test navigate_tree with a node that has empty children."""
        mock_provider = MockLLMProvider(
            [
                {
                    "decision": DecisionType.ExploreChildren,
                    "reasoning": "Trying to explore children but there are none",
                    "next_children_ids": [],
                    "confidence": 0.7,
                }
            ]
        )

        node = MemoryTreeNode(
            id="test", summary="Test", content="Test content", children=[]
        )

        walker = MemWalker(llm_provider=mock_provider)
        output = await walker.navigate_tree(query="test query", root_node=node)

        assert len(output.navigation_log) == 1
        assert (
            output.navigation_log[0].llm_decision.decision
            == DecisionType.ExploreChildren
        )
        assert len(output.collected_context) == 0

    @pytest.mark.asyncio
    async def test_navigate_tree_skip_visited_nodes(self):
        """Test that navigate_tree skips already visited nodes."""
        # Create a provider that would cause an infinite loop without visited node tracking
        mock_responses = []
        for _ in range(10):  # More than needed to cause an issue
            mock_responses.append(
                {
                    "decision": DecisionType.ExploreChildren,
                    "reasoning": "Keep exploring the same node",
                    "next_children_ids": ["same-node"],
                    "confidence": 0.8,
                }
            )

        provider = MockLLMProvider(mock_responses)

        # Create a tree where a child points back to itself
        node = MemoryTreeNode(
            id="same-node", summary="Same node", content="Same node content"
        )
        node.children = [node]  # Self-reference

        walker = MemWalker(llm_provider=provider, max_llm_calls=5)
        output = await walker.navigate_tree(query="test query", root_node=node)

        # Should only have one log entry since the same node would be skipped on subsequent visits
        assert len(output.navigation_log) == 1

    def test_get_child_summaries_empty_children(self):
        """Test _get_child_summaries with empty children list."""
        node = MemoryTreeNode(
            id="test", summary="Test", content="Test content", children=[]
        )

        walker = MemWalker(llm_provider=MagicMock())
        summaries = walker._get_child_summaries(node)

        assert len(summaries) == 0
        assert isinstance(summaries, dict)

    @pytest.mark.asyncio
    async def test_navigate_tree_with_nonexistent_child_ids(self):
        """Test navigate_tree when LLM returns nonexistent child IDs."""
        mock_provider = MockLLMProvider(
            [
                {
                    "decision": DecisionType.ExploreChildren,
                    "reasoning": "Trying to explore nonexistent children",
                    "next_children_ids": ["nonexistent-1", "nonexistent-2"],
                    "confidence": 0.7,
                }
            ]
        )

        node = MemoryTreeNode(
            id="test", summary="Test", content="Test content", children=[]
        )

        walker = MemWalker(llm_provider=mock_provider)
        output = await walker.navigate_tree(query="test query", root_node=node)

        # Should still navigate but not add any children to the stack
        assert len(output.navigation_log) == 1
        assert len(output.collected_context) == 0

    @pytest.mark.asyncio
    async def test_navigate_tree_with_multiple_answers(self):
        """Test navigate_tree when multiple nodes provide answers."""
        mock_provider = MockLLMProvider(
            [
                {
                    "decision": DecisionType.ExploreChildren,
                    "reasoning": "Exploring both children",
                    "next_children_ids": ["child-1", "child-2"],
                    "confidence": 0.9,
                },
                {
                    "decision": DecisionType.AnswerHere,
                    "reasoning": "This child has an answer",
                    "confidence": 0.85,
                },
                {
                    "decision": DecisionType.AnswerHere,
                    "reasoning": "This child also has an answer",
                    "confidence": 0.9,
                },
            ]
        )

        child1 = MemoryTreeNode(
            id="child-1", summary="Child 1", content="Child 1 content"
        )
        child2 = MemoryTreeNode(
            id="child-2", summary="Child 2", content="Child 2 content"
        )

        root = MemoryTreeNode(
            id="root", summary="Root", content="Root content", children=[child1, child2]
        )

        walker = MemWalker(llm_provider=mock_provider)
        output = await walker.navigate_tree(query="test query", root_node=root)

        # Should collect context from both child nodes
        assert len(output.navigation_log) == 3  # Root + 2 children
        assert len(output.collected_context) == 2

    @pytest.mark.asyncio
    async def test_navigate_tree_mixed_decisions(self):
        """Test navigate_tree with a mix of decision types in different nodes."""
        mock_provider = MockLLMProvider(
            [
                {
                    "decision": DecisionType.ExploreChildren,
                    "reasoning": "Exploring children",
                    "next_children_ids": ["child-1", "child-2"],
                    "confidence": 0.8,
                },
                {
                    "decision": DecisionType.AnswerHere,
                    "reasoning": "This child has an answer",
                    "confidence": 0.9,
                },
                {
                    "decision": DecisionType.DeadEnd,
                    "reasoning": "This is a dead end",
                    "confidence": 0.7,
                },
            ]
        )

        child1 = MemoryTreeNode(
            id="child-1", summary="Child 1", content="Child 1 content"
        )
        child2 = MemoryTreeNode(
            id="child-2", summary="Child 2", content="Child 2 content"
        )

        root = MemoryTreeNode(
            id="root", summary="Root", content="Root content", children=[child1, child2]
        )

        walker = MemWalker(llm_provider=mock_provider)
        output = await walker.navigate_tree(query="test query", root_node=root)

        # Should follow all paths but only collect from the AnswerHere node
        assert len(output.navigation_log) == 3  # Root + 2 children
        assert len(output.collected_context) == 1
        assert (
            output.collected_context[0].node_id == "child-1"
        )  # First child had AnswerHere

    def test_memwalker_system_prompt_content(self):
        """Test that the system prompt contains the expected guidance."""
        walker = MemWalker(llm_provider=MagicMock())

        system_prompt = walker._MEMWALKER_SYSTEM_PROMPT

        # Check for key instruction components
        assert "explore_children" in system_prompt
        assert "answer_here" in system_prompt
        assert "deadend" in system_prompt
        assert "confidence" in system_prompt
        assert "JSON" in system_prompt

    def test_memwalker_human_prompt_content(self):
        """Test that the human prompt contains the expected variables."""
        walker = MemWalker(llm_provider=MagicMock())

        human_prompt = walker._MEMWALKER_HUMAN_PROMPT

        # Check for template variables
        assert "{query}" in human_prompt
        assert "{current_node_id}" in human_prompt
        assert "{current_node_content}" in human_prompt
        assert "{current_node_summary}" in human_prompt
        assert "{children_info}" in human_prompt

    @pytest.mark.asyncio
    async def test_make_navigation_decision_json_escaping(self):
        """Test that make_navigation_decision properly escapes JSON braces."""
        mock_provider = MockLLMProvider(
            [
                {
                    "decision": DecisionType.AnswerHere,
                    "reasoning": "Test reasoning",
                    "confidence": 0.9,
                }
            ]
        )

        walker = MemWalker(llm_provider=mock_provider)

        # Create a simple node and child_summaries
        node = MemoryTreeNode(id="test", summary="Test", content="Test content")
        child_summaries = {"child-1": "Summary 1"}

        # This would throw an error if the JSON wasn't properly escaped
        decision = await walker.make_navigation_decision(
            query="test query", current_node=node, child_summaries=child_summaries
        )

        assert decision.decision == DecisionType.AnswerHere
        assert decision.confidence == 0.9

    def test_get_child_by_id_mixed_children(self):
        """Test _get_child_by_id with a mix of children types."""
        child1 = MemoryTreeNode(
            id="child-1", summary="Child 1", content="Child 1 content"
        )
        child2 = MemoryTreeNode(
            id="child-2", summary="Child 2", content="Child 2 content"
        )

        parent = MemoryTreeNode(id="parent", summary="Parent", content="Parent content")
        # Add children directly to test object mutation
        parent.children = [child1, child2]

        walker = MemWalker(llm_provider=MagicMock())

        # Test fetching the second child
        result = walker._get_child_by_id(parent, "child-2")
        assert result is not None
        assert result.id == "child-2"

        # Test fetching a nonexistent child
        result = walker._get_child_by_id(parent, "nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_navigate_tree_with_deep_hierarchy(self):
        """Test navigate_tree with a deeply nested hierarchy."""
        # Create responses for each level
        mock_responses = [
            {
                "decision": DecisionType.ExploreChildren,
                "reasoning": "Exploring level 1",
                "next_children_ids": ["level-1"],
                "confidence": 0.9,
            },
            {
                "decision": DecisionType.ExploreChildren,
                "reasoning": "Exploring level 2",
                "next_children_ids": ["level-2"],
                "confidence": 0.85,
            },
            {
                "decision": DecisionType.ExploreChildren,
                "reasoning": "Exploring level 3",
                "next_children_ids": ["level-3"],
                "confidence": 0.8,
            },
            {
                "decision": DecisionType.AnswerHere,
                "reasoning": "Found answer at level 3",
                "confidence": 0.95,
            },
        ]

        provider = MockLLMProvider(mock_responses)

        # Create a deep hierarchy
        level3 = MemoryTreeNode(
            id="level-3", summary="Level 3", content="Level 3 content"
        )
        level2 = MemoryTreeNode(
            id="level-2",
            summary="Level 2",
            content="Level 2 content",
            children=[level3],
        )
        level1 = MemoryTreeNode(
            id="level-1",
            summary="Level 1",
            content="Level 1 content",
            children=[level2],
        )
        root = MemoryTreeNode(
            id="root", summary="Root", content="Root content", children=[level1]
        )

        walker = MemWalker(llm_provider=provider)
        output = await walker.navigate_tree(query="test query", root_node=root)

        # Should navigate to the deepest level
        assert len(output.navigation_log) == 4  # Root + 3 levels
        assert len(output.collected_context) == 1
        assert output.collected_context[0].node_id == "level-3"

    @pytest.mark.asyncio
    async def test_navigate_tree_breadth_first_exploration(self):
        """Test navigate_tree with breadth-first exploration pattern."""
        # Create mock responses that explore children in a breadth-first pattern
        mock_responses = [
            {
                "decision": DecisionType.ExploreChildren,
                "reasoning": "Exploring both children at root level",
                "next_children_ids": ["child-1", "child-2"],
                "confidence": 0.9,
            },
            {
                "decision": DecisionType.AnswerHere,
                "reasoning": "This child has part of the answer",
                "confidence": 0.85,
            },
            {
                "decision": DecisionType.AnswerHere,
                "reasoning": "This child also has part of the answer",
                "confidence": 0.8,
            },
        ]

        provider = MockLLMProvider(mock_responses)

        # Create a tree with two children
        child1 = MemoryTreeNode(
            id="child-1", summary="Child 1", content="Child 1 content"
        )
        child2 = MemoryTreeNode(
            id="child-2", summary="Child 2", content="Child 2 content"
        )
        root = MemoryTreeNode(
            id="root", summary="Root", content="Root content", children=[child1, child2]
        )

        walker = MemWalker(llm_provider=provider)
        output = await walker.navigate_tree(query="test query", root_node=root)

        # Should navigate to both children and collect from both
        assert len(output.navigation_log) == 3  # Root + 2 children
        assert len(output.collected_context) == 2
        assert {context.node_id for context in output.collected_context} == {
            "child-1",
            "child-2",
        }

    @pytest.mark.asyncio
    async def test_order_of_navigation_stack(self):
        """Test that the navigation stack processes nodes in the correct order."""
        # Create responses that will reveal the traversal order
        mock_responses = [
            {
                "decision": DecisionType.ExploreChildren,
                "reasoning": "Exploring all children",
                "next_children_ids": ["child-3", "child-2", "child-1"],  # Reverse order
                "confidence": 0.9,
            },
            {
                "decision": DecisionType.AnswerHere,
                "reasoning": "Child 1 has answer",
                "confidence": 0.8,
            },
            {
                "decision": DecisionType.AnswerHere,
                "reasoning": "Child 2 has answer",
                "confidence": 0.8,
            },
            {
                "decision": DecisionType.AnswerHere,
                "reasoning": "Child 3 has answer",
                "confidence": 0.8,
            },
        ]

        provider = MockLLMProvider(mock_responses)

        # Create a tree with three children
        child1 = MemoryTreeNode(
            id="child-1", summary="Child 1", content="Child 1 content"
        )
        child2 = MemoryTreeNode(
            id="child-2", summary="Child 2", content="Child 2 content"
        )
        child3 = MemoryTreeNode(
            id="child-3", summary="Child 3", content="Child 3 content"
        )
        root = MemoryTreeNode(
            id="root",
            summary="Root",
            content="Root content",
            children=[child1, child2, child3],
        )

        walker = MemWalker(llm_provider=provider)
        output = await walker.navigate_tree(query="test query", root_node=root)

        # Check that children were processed in reverse order (due to the stack)
        # Since we add to stack in reverse order and pop from the end, the order should be:
        # root -> child-1 -> child-2 -> child-3
        assert len(output.navigation_log) == 4
        assert output.navigation_log[0].visited_node_id == "root"
        assert output.navigation_log[1].visited_node_id == "child-3"
        assert output.navigation_log[2].visited_node_id == "child-2"
        assert output.navigation_log[3].visited_node_id == "child-1"

    @pytest.mark.asyncio
    async def test_navigate_tree_with_large_fan_out(self):
        """Test navigate_tree with a node that has many children."""
        # Create responses
        mock_responses = [
            {
                "decision": DecisionType.ExploreChildren,
                "reasoning": "Exploring specific children",
                "next_children_ids": [
                    "child-2",
                    "child-5",
                    "child-8",
                ],  # Only select a few
                "confidence": 0.8,
            },
            {
                "decision": DecisionType.AnswerHere,
                "reasoning": "Child 2 has an answer",
                "confidence": 0.85,
            },
            {
                "decision": DecisionType.DeadEnd,
                "reasoning": "Child 5 is not relevant",
                "confidence": 0.9,
            },
            {
                "decision": DecisionType.AnswerHere,
                "reasoning": "Child 8 has an answer",
                "confidence": 0.95,
            },
        ]

        provider = MockLLMProvider(mock_responses)

        # Create a tree with many children
        children = []
        for i in range(10):
            child = MemoryTreeNode(
                id=f"child-{i}", summary=f"Child {i}", content=f"Child {i} content"
            )
            children.append(child)

        root = MemoryTreeNode(
            id="root", summary="Root", content="Root content", children=children
        )

        walker = MemWalker(llm_provider=provider)
        output = await walker.navigate_tree(query="test query", root_node=root)

        # Should only navigate to the 3 selected children
        assert len(output.navigation_log) == 4  # Root + 3 children
        assert len(output.collected_context) == 2  # 2 AnswerHere decisions

        # Verify that only the selected children were visited
        visited_ids = [step.visited_node_id for step in output.navigation_log]
        assert "child-2" in visited_ids
        assert "child-5" in visited_ids
        assert "child-8" in visited_ids
        assert "child-1" not in visited_ids  # Not selected

    @pytest.mark.asyncio
    async def test_navigate_tree_with_confidence_tracking(self):
        """Test that navigate_tree correctly tracks confidence values."""
        mock_provider = MockLLMProvider(
            [
                {
                    "decision": DecisionType.ExploreChildren,
                    "reasoning": "Exploring child",
                    "next_children_ids": ["child-1"],
                    "confidence": 0.75,
                },
                {
                    "decision": DecisionType.AnswerHere,
                    "reasoning": "This node has the answer",
                    "confidence": 0.92,
                },
            ]
        )

        child = MemoryTreeNode(id="child-1", summary="Child", content="Child content")
        root = MemoryTreeNode(
            id="root", summary="Root", content="Root content", children=[child]
        )

        walker = MemWalker(llm_provider=mock_provider)
        output = await walker.navigate_tree(query="test query", root_node=root)

        # Check confidence values were transferred correctly
        assert len(output.navigation_log) == 2
        assert output.navigation_log[0].llm_decision.confidence == 0.75
        assert output.navigation_log[1].llm_decision.confidence == 0.92

        # Check confidence in collected context
        assert len(output.collected_context) == 1
        assert output.collected_context[0].confidence == 0.92

    @pytest.mark.asyncio
    async def test_navigate_tree_with_identical_node_ids(self):
        """Test navigate_tree with nodes that have identical IDs but different content."""
        mock_provider = MockLLMProvider(
            [
                {
                    "decision": DecisionType.ExploreChildren,
                    "reasoning": "Exploring child",
                    "next_children_ids": ["same-id"],
                    "confidence": 0.8,
                },
                {
                    "decision": DecisionType.AnswerHere,
                    "reasoning": "This node has the answer",
                    "confidence": 0.9,
                },
            ]
        )

        # Create two nodes with the same ID but different content
        child = MemoryTreeNode(id="same-id", summary="Child", content="Child content")
        different_child = MemoryTreeNode(
            id="same-id", summary="Different child", content="Different content"
        )

        # Create two different trees, but with child nodes having the same ID
        root1 = MemoryTreeNode(
            id="root1", summary="Root 1", content="Root 1 content", children=[child]
        )

        # The nodes should be considered equal due to ID equality
        assert child == different_child

        walker = MemWalker(llm_provider=mock_provider)
        output = await walker.navigate_tree(query="test query", root_node=root1)

        # Should navigate correctly despite ID duplication
        assert len(output.navigation_log) == 2
        assert output.navigation_log[0].visited_node_id == "root1"
        assert output.navigation_log[1].visited_node_id == "same-id"
