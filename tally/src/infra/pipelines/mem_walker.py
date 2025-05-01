import json
import logging
from enum import Enum
from typing import Dict, List, Optional, Set

from langchain_core.language_models import BaseLanguageModel
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from pydantic import BaseModel, Field

from infra.collections.models import BaseMetadata, ChunkType
from infra.llm.models import ILLMProvider


logger = logging.getLogger(__name__)


class MemoryTreeNode(BaseModel):
    id: str = Field(description="Unique identifier for the node in the memory tree.")
    summary: str = Field(..., description="Summary of the node's content.")
    content: str = Field(..., description="Raw content of the node")
    node_type: ChunkType = Field(
        default=ChunkType.TEXT, description="Type of the node."
    )
    metadata: Optional[BaseMetadata] = Field(
        default=None, description="Metadata associated with the node."
    )

    children: Optional[List["MemoryTreeNode"]] = Field(
        default_factory=list,
        description="List of child nodes in the memory tree.",
    )

    def __eq__(self, other):
        if not isinstance(other, MemoryTreeNode):
            return False
        return isinstance(other, MemoryTreeNode) and self.id == other.id

    def __hash__(self):
        return hash(self.id)


class DecisionType(str, Enum):
    ExploreChildren = "explore_children"
    AnswerHere = "answer_here"
    DeadEnd = "deadend"


class NavigationDecision(BaseModel):
    decision: DecisionType = Field(..., description="Decision made by the LLM.")
    reasoning: str = Field(
        default="No reasoning provided.",
        description="Reasoning behind the decision made by the LLM.",
    )
    next_children_ids: Optional[List[str]] = Field(
        default=None,
        description="List of child node IDs to explore next.",
    )
    confidence: float = Field(
        ...,
        description="Confidence level of the decision made by the LLM.",
        ge=0.0,
        le=1.0,
    )


class SummaryContext(BaseModel):
    """
    Represents a summary context identified as relevant during navigation.
    """

    node_id: str = Field(..., description="ID of the relevant MemoryTreeNode.")
    summary_text: str = Field(..., description="The summary text of the node.")
    reasoning: str = Field(
        ..., description="LLM's reasoning for this node's relevance to the query."
    )
    confidence: Optional[float] = Field(
        None,
        description="Confidence that this node is relevant, usually from LLM decision.",
        ge=0.0,
        le=1.0,
    )


class NavigationLogStep(BaseModel):
    step: int = Field(
        ..., description="Sequential step number in the navigation process."
    )
    visited_node_id: str = Field(
        ..., description="ID of the MemoryTreeNode being considered at this step."
    )
    visited_node_summary: str = Field(
        ..., description="Summary of the visited node (can be truncated for logging)."
    )
    llm_decision: NavigationDecision = Field(
        ..., description="The full decision object returned by the LLM for this step."
    )


class Output(BaseModel):
    collected_context: List[SummaryContext] = Field(
        default_factory=list,
        description="List of summary contexts identified as relevant.",
    )
    navigation_log: List[NavigationLogStep] = Field(
        default_factory=list,
        description="Detailed log of the navigation process and reasoning steps.",
    )
    # document_id: str = Field(..., description="The ID of the document that was navigated.")
    # error_message: Optional[str] = Field(None, description="Any error message encountered during navigation.")


class MemWalker:
    _MEMWALKER_SYSTEM_PROMPT = """
You are an intelligent agent, "MemWalker," navigating a hierarchical memory tree to find information relevant to a specific user query provided in the <user_query> tag.
Your task is to analyze the current node and its children, then decide the next best action.

**Your Task:**
Based on the overall user query, the content of the current node, and the summaries of its children (if any), you must make a navigation decision.

**Decision Options:**
1.  **`explore_children`**: If the current node is relevant but not specific enough, or if its children seem more promising to answer the query. This option is not valid if there are no children.
2.  **`answer_here`**: If the content of the **current node** directly and sufficiently answers the overall user query.
3.  **`deadend`**: If the current node and its children are not relevant to the query, and this path should be abandoned.

**Output Requirements:**
You MUST provide your response as a JSON object that strictly conforms to the following structure. The field descriptions from this structure will guide your response:

```json
{{
  "decision": "DecisionType (must be one of 'explore_children', 'answer_here', 'deadend')",
  "reasoning": "Your detailed reasoning for choosing this decision, explaining how the current node's content and children (if any) relate to the overall user query.",
  "next_children_ids": ["Optional list of child node IDs to explore next. This field is ONLY required and should ONLY be populated if your decision is 'explore_children'. In that case, list the IDs of the children you deem most relevant to explore further. If the decision is not 'explore_children', this field should be null or an empty list."],
  "confidence": "A float value between 0.0 and 1.0 representing your confidence in this decision. For example, 0.95 for high confidence."
}}

Guidelines for Decision Making:
- Relevance: Always prioritize paths and information most relevant to the overall user query.
- Specificity: If `explore_children` is chosen, select only the children IDs that are most likely to lead to the answer.
- Sufficiency for `answer_here`: Only choose `answer_here` if the current node's content itself is sufficient.
- Reasoning is Key: Your `reasoning` should clearly justify your `decision`.
- Confidence: Reflect your certainty in the decision.
"""
    _MEMWALKER_HUMAN_PROMPT = """
**Overall User Query:**
{query}

**Current Traversal Context:**
* **Current Node ID:** {current_node_id}
* **Current Node Content:**
    ```
    {current_node_content}
    ```
* **Current Node Summary:**
    ```
    {current_node_summary}
    ```

**Available Child Nodes from Current Node ({current_node_id}):**
```
{children_info}
```
(Provided as a JSON array of objects, e.g.,
[
  {{"id": "child1_id", "summary": "Brief summary or title of child 1"}},
  {{"id": "child2_id", "summary": "Brief summary or title of child 2"}},
  ...
])
If there are no children, provided an empty list `[]`.

Based on the system instructions, the overall user query, and the current context provided above, please analyze the information and provide your navigation decision in the specified JSON format.
"""

    def __init__(self, llm_provider: ILLMProvider, max_llm_calls=20):
        self.llm_provider = llm_provider
        self._llm_instance = None  # Lazy loading
        self.max_llm_calls = max_llm_calls

        self.prompt_template = ChatPromptTemplate.from_messages(
            [
                SystemMessagePromptTemplate.from_template(
                    self._MEMWALKER_SYSTEM_PROMPT
                ),
                HumanMessagePromptTemplate.from_template(self._MEMWALKER_HUMAN_PROMPT),
            ]
        )

    async def navigate_tree(self, query: str, root_node: MemoryTreeNode) -> Output:
        """
        Performs MemWalker navigation on the document tree.
        Returns a list of context snippets associated with the query
        """
        collected_context: List[SummaryContext] = []
        navigation_log: List[NavigationLogStep] = []
        visited_nodes: Set[MemoryTreeNode] = set()
        llm_calls = 0

        stack: List[MemoryTreeNode] = [root_node]

        while stack and llm_calls < self.max_llm_calls:
            current_node = stack.pop()
            if current_node in visited_nodes:
                continue
            visited_nodes.add(current_node)

            child_summaries = self._get_child_summaries(current_node)
            decision = await self.make_navigation_decision(
                query=query,
                current_node=current_node,
                child_summaries=child_summaries,
            )
            llm_calls += 1
            if decision.decision == DecisionType.ExploreChildren:
                action_log_children = []
                # Add child nodes to the stack for further exploration
                if decision.next_children_ids:
                    for child_id in reversed(decision.next_children_ids):
                        child_node = self._get_child_by_id(current_node, child_id)
                        if child_node and child_node not in visited_nodes:
                            stack.append(child_node)
                            action_log_children.append(child_node.id)
            elif decision.decision == DecisionType.AnswerHere:
                # Collect the current node's content
                collected_context.append(
                    SummaryContext(
                        node_id=current_node.id,
                        summary_text=current_node.summary,
                        reasoning=decision.reasoning,
                        confidence=decision.confidence,
                    )
                )
            elif decision.decision == DecisionType.DeadEnd:
                # If its a deadend, we should backtrack
                pass
            else:
                logger.warning(f"Unknown decision from LLM: {decision.decision}")

            navigation_log.append(
                NavigationLogStep(
                    step=len(navigation_log) + 1,
                    visited_node_id=current_node.id,
                    visited_node_summary=current_node.summary,
                    llm_decision=decision,
                )
            )

        return Output(
            collected_context=collected_context,
            navigation_log=navigation_log,
        )

    def _get_child_summaries(self, parent_node: MemoryTreeNode) -> Dict[str, str]:
        child_summaries_map = {}
        for child in parent_node.children:
            if child:
                child_summaries_map["id"] = child.id
                child_summaries_map["summary"] = child.summary
        return child_summaries_map

    def _get_child_by_id(
        self, parent_node: MemoryTreeNode, child_id: str
    ) -> Optional[MemoryTreeNode]:
        for child in parent_node.children:
            if child.id == child_id:
                return child
        return None

    def _llm(self) -> BaseLanguageModel:
        """
        Lazy load the language model instance.

        This method ensures that the language model is only loaded when needed.
        """
        if self._llm_instance is None:
            self._llm_instance = self.llm_provider.get_model()
        return self._llm_instance

    async def make_navigation_decision(
        self,
        query: str,
        current_node: MemoryTreeNode,
        child_summaries: Dict[str, str],
    ) -> NavigationDecision:
        llm = self._llm().with_structured_output(NavigationDecision)
        prompt = self.prompt_template.format_prompt(
            query=query,
            current_node_id=current_node.id,
            current_node_content=current_node.content,
            current_node_summary=current_node.summary,
            children_info=json.dumps(child_summaries),
        )
        response: NavigationDecision = await llm.ainvoke(prompt)
        return response
