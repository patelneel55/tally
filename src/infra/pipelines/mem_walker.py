import asyncio
import json
import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Set

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
        None,
        description="Reasoning behind the decision made by the LLM.",
    )
    next_children_ids: Optional[List[str]] = Field(
        default=None,
        description="List of child node IDs to explore next.",
    )
    confidence: float = Field(
        ...,
        description="Confidence level of the decision made by the LLM. Must be between 0.0 and 1.0",
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
You are currently at a node in the memory tree. Your task is to analyze this node's content, its children, and the overall query context (including prior memory) to choose the next best action.

**Your Task:**
IMPORTANT: You are navigating a financial document like 10-K, 10-Q etc. Any decision you make should consider the overall structure of a financial document and
think about where the data to answer the user's query can lie when reasoning about possible decisions.

**Decision Options:**
1.  **`explore_children`**: The current node is relevant but not sufficient. Deeper inspection of child nodes is warranted. This option is not valid if there are no children.
2.  **`answer_here`**: ONLY if the **current node** has no children. If the content of the **current node** clearly answers a part of the query OR the full query. IMPORTANT: It is sufficient if it only answers a part of the query and it has no children.
3.  **`deadend`**: If the current node and its children are not relevant to the query, and this path should be abandoned. ONLY chosen when the path is confidently irrelevant.

<

**Output Requirements:**
You MUST provide your response as a JSON object that strictly conforms to the following structure. The field descriptions from this structure will guide your response:

```json
{{
  "decision": "DecisionType (must be one of 'explore_children', 'answer_here', 'deadend')",
  "reasoning": "Your detailed reasoning for choosing this decision, explaining how the current node's content and children (if any) relate to the overall user query.",
  "next_children_ids": ["Optional list of the whole child node IDs to explore next. This field is ONLY required and should ONLY be populated if your decision is 'explore_children'. In that case, list the IDs of the children you deem most relevant to explore further. If the decision is not 'explore_children', this field should be null or an empty list."],
  "confidence": "A float value between 0.0 and 1.0 representing your confidence in this decision. For example, 0.95 for high confidence."
}}

Guidelines for Decision Making:
- Relevance: Always prioritize paths and information most relevant to the user query.
- Breadth over narrowness: If multiple children contain partial, complimentary or thematically related content that could contribute to answering the query, select multiple of them. Do NOT over-prune to only one unless you're highly confident it's vastly more relevant.
- Specificity for `explore_children`: Select **all** children IDs that are most likely to contain **any** portion of the answer to the user's query.
- Sufficiency for `answer_here`: Only choose `answer_here` if the current node's content can answer a part of the user's query and the current node has no children, else continue exploring children
- Sufficiency for `deadend`: Before answering `deadend`, make sure that the node has no relevance to the query. Even if the node partially answers the query or if there's even a slight chance that one of the children can answer the question partially. It should explore the children or use it as the answer. If the query had to be relevant to any of the children, and you had to pick a child, pick one as long as confidence is above 0.0
- Relevance for `deadend`: Before answering `deadend`, think about what kind of document this is. If you think the user's query can be partially answered in such a document and there is chance that the children have the answer, NEVER make the decision of a `deadend`. It's CHEAPER to navigate the children if the decision is wrong rather than saying `deadend` and in actuality the children have the answer. It will lead to CATASTROPHE if you pick `deadend` too early. So be absolutely certain!
- Reasoning is Key: Your `reasoning` should clearly justify your `decision`.
- Confidence: Reflect your certainty in the decision.
- The section under <working_memory> refers to the memory of the decision tree traversal. USE that as guidance on the memory until now
"""
    _MEMWALKER_HUMAN_PROMPT = """
**Overall User Query:**
{query}

**Current Traversal Context:**
* **Current Node ID:** {current_node_id}
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

<custom_instructions>
{custom_instructions}
</custom_instructions>

<working_memory>
{working_memory}
</working_memory>

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

    async def _navigate_recurse(
        self,
        query: str,
        current_node: MemoryTreeNode,
        visited_nodes: Set[MemoryTreeNode] = None,
        llm_calls: int = 0,
        navigation_so_far: List[NavigationLogStep] = None,
    ) -> Output:
        if visited_nodes is None:
            visited_nodes = set()
        if llm_calls >= self.max_llm_calls or current_node in visited_nodes:
            logger.info(f"Node {current_node.id} already visited. Skipping.")
            return Output()
        visited_nodes.add(current_node)
        child_summaries = self._get_child_summaries(current_node)
        working_memory = self._get_memory_from_navigation(navigation_so_far or [])

        logger.info(f"Retrieved child summaries for node {current_node.id}")
        decision = await self.make_navigation_decision(
            query=query,
            current_node=current_node,
            child_summaries=child_summaries,
            memory=working_memory,
        )
        logger.info(f"LLM decision at node {current_node.id}: {decision.decision}")

        llm_calls += 1
        step = 1
        output = Output(
            navigation_log=[
                NavigationLogStep(
                    step=step,
                    visited_node_id=current_node.id,
                    visited_node_summary=current_node.summary,
                    llm_decision=decision,
                )
            ]
        )
        visited_children = []

        async def _decision_branch(decision: NavigationDecision):
            nonlocal step
            nonlocal llm_calls
            logger.info(
                f"Processing decision {decision.decision} at node {current_node.id}"
            )
            if decision.decision == DecisionType.ExploreChildren:
                # Add child nodes to the stack for further exploration
                if decision.next_children_ids:
                    visited_children.extend(decision.next_children_ids)
                    logger.info(
                        f"Exploring children {decision.next_children_ids} from node {current_node.id}"
                    )
                    tasks = []
                    for child_id in decision.next_children_ids:
                        child_node = self._get_child_by_id(current_node, child_id)
                        if child_node and child_node not in visited_nodes:
                            tasks.append(
                                self._navigate_recurse(
                                    query,
                                    child_node,
                                    visited_nodes,
                                    llm_calls,
                                    output.navigation_log,
                                )
                            )

                    results: List[Output] = await asyncio.gather(*tasks)
                    for child_output in results:
                        output.collected_context.extend(child_output.collected_context)
                        output.navigation_log.extend(child_output.navigation_log)

                if len(output.collected_context) == 0:
                    logger.warning(
                        f"No context gathered from children of node {current_node.id}, retrying with updated decision."
                    )
                    working_memory = self._get_memory_from_navigation(
                        output.navigation_log
                    )
                    new_decision = await self.make_navigation_decision(
                        query=query,
                        current_node=current_node,
                        child_summaries=child_summaries,
                        custom_instructions="""
The following chosen children IDs do not have the information to answer the user's query. Do NOT pick the same IDs again and those IDs are not valid anymore, since picking them again can lead to catastrophe. Make the decision again:
```
{children_ids}
```
""".format(
                            children_ids=visited_children
                        ),
                        memory=working_memory,
                    )
                    step += 1
                    llm_calls += 1
                    output.navigation_log.append(
                        NavigationLogStep(
                            step=step,
                            visited_node_id=current_node.id,
                            visited_node_summary=current_node.summary,
                            llm_decision=new_decision,
                        )
                    )
                    await _decision_branch(new_decision)

            elif decision.decision == DecisionType.AnswerHere:
                logger.info(f"Answer found at node {current_node.id}")
                # Collect the current node's content
                output.collected_context.append(
                    SummaryContext(
                        node_id=current_node.id,
                        summary_text=current_node.summary,
                        reasoning=decision.reasoning,
                        confidence=decision.confidence,
                    )
                )
            elif decision.decision == DecisionType.DeadEnd:
                # If its a deadend, we should backtrack
                logger.info(f"Dead end encountered at node {current_node.id}")
            else:
                logger.warning(f"Unknown decision from LLM: {decision.decision}")

        await _decision_branch(decision)

        return output

    async def navigate_tree(self, query: str, root_node: MemoryTreeNode) -> Output:
        """
        Performs MemWalker navigation on the document tree.
        Returns a list of context snippets associated with the query
        """
        return await self._navigate_recurse(query, root_node)

    def _get_child_summaries(self, parent_node: MemoryTreeNode) -> List[Dict[str, str]]:
        child_summaries_map = []
        for child in parent_node.children:
            if child:
                child_summaries_map.append(
                    {
                        "id": child.id,
                        "summary": child.summary,
                    }
                )
        return child_summaries_map

    def _get_memory_from_navigation(
        self, log: List[NavigationLogStep]
    ) -> List[Dict[str, Any]]:
        memory = []
        for step, navigate in enumerate(log, 1):
            memory.append(
                {"step": step, "decision": navigate.llm_decision.model_dump()}
            )
        return memory

    def _get_child_by_id(
        self, parent_node: MemoryTreeNode, child_id: str
    ) -> Optional[MemoryTreeNode]:
        for child in parent_node.children:
            if child.id == child_id or child.id.startswith(child_id):
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
        child_summaries: List[Dict[str, str]],
        custom_instructions: str = "",
        memory=None,
    ) -> NavigationDecision:
        llm = self._llm().with_structured_output(NavigationDecision)
        prompt = self.prompt_template.format_prompt(
            query=query,
            current_node_id=current_node.id,
            current_node_summary=current_node.summary,
            children_info=json.dumps(child_summaries),
            custom_instructions=custom_instructions,
            working_memory=json.dumps(memory),
        )
        response: NavigationDecision = await llm.ainvoke(prompt)
        return response
