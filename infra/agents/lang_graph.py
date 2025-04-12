"""
LangGraph Agent
--------------

This module provides an agent implementation using LangGraph for structured workflow
and ReAct prompting for reasoning through complex tasks.
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict, Union, cast

from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from infra.agents.interfaces import IAgent
from infra.core.interfaces import ILLMProvider
from infra.tools.base import ITool

# Set up logging
logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """State maintained during agent execution."""

    messages: List[Dict[str, Any]]  # Chat messages
    tools: List[ITool]  # Available tools
    tool_results: Dict[str, Any]  # Results from tool executions
    steps: List[Dict[str, Any]]  # Track reasoning steps
    original_query: str  # Original user query


class LangGraphAgent(IAgent):
    """
    Agent implementation using LangGraph for structured reasoning workflows.

    This agent uses the ReAct (Reasoning and Acting) approach to break down complex
    queries into smaller sub-tasks, interact with tools, and maintain focus on the
    original objective throughout the process.
    """

    def __init__(
        self,
        llm_provider: ILLMProvider,
        verbose: bool = False,
        max_iterations: int = 15,
    ):
        """
        Initialize the LangGraph agent.

        Args:
            llm_provider: Provider for the LLM to use for decision making
            verbose: Whether to enable verbose logging
            max_iterations: Maximum number of iterations for the agent
        """
        self.llm_provider = llm_provider
        self.verbose = verbose
        self.max_iterations = max_iterations
        self.tools: List[ITool] = []
        self._graph = None

    def add_tool(self, tool: ITool) -> None:
        """
        Add a tool to the agent's toolset.

        Args:
            tool: The tool to add
        """
        self.tools.append(tool)
        # Reset graph so it will be recreated with new tools
        self._graph = None

    def get_tools(self) -> List[ITool]:
        """
        Get all tools available to this agent.

        Returns:
            A list of tools available to the agent
        """
        return self.tools

    def _create_graph(self) -> StateGraph:
        """
        Create the LangGraph workflow for agent execution.

        Returns:
            An initialized StateGraph for execution
        """
        llm = self.llm_provider.get_model()

        # Create system prompt with enhanced financial analysis context
        system_prompt = """You are an intelligent equity research assistant specialized in financial analysis.

Your goal is to accurately answer financial analysis questions by breaking them down into smaller sub-tasks.
For each sub-task, you'll either:
1. Use your existing knowledge to reason through the question
2. Use appropriate tools to find information in financial documents
3. Query vector databases containing indexed SEC filings and financial data

IMPORTANT GUIDELINES:
- Break complex questions into logical sub-questions
- Maintain focus on the original query throughout your analysis
- When analyzing company financials, be precise about metrics, dates, and sources
- Always keep track of the information you've gathered and what's still needed
- Be specific in your tool queries - target exact information needed
- Synthesize information from multiple sources for comprehensive answers
- For financial metrics, note the time period (quarterly/annual) and any relevant context

When you've completely answered the original question with sufficient depth and accuracy,
summarize your findings and conclude.
"""

        # Create the React agent using LangGraph's prebuilt functionality
        react_agent = create_react_agent(llm, self.tools)

        # Define the agent workflow
        builder = StateGraph(AgentState)

        # Add the initial state preparation node
        def prepare_state(state: AgentState) -> Dict:
            """Prepare the initial state for agent execution."""
            query = state["original_query"]
            logger.info(f"🔍 Starting agent with query: {query}")

            return {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query},
                ],
                "tools": state["tools"],
                "tool_results": {},
                "steps": [],
                "original_query": query,
            }

        # Add the reasoning node using React pattern
        def process_reasoning(state: AgentState) -> Dict:
            """Process agent reasoning and tool execution."""
            # Log the current step number
            current_step = len(state.get("steps", []))
            logger.info(f"🤔 Executing reasoning step {current_step + 1}...")

            # Call the React agent to decide the next action
            result = react_agent.invoke(state)

            # Update state with the agent's reasoning
            new_state = state.copy()
            new_state["messages"] = result["messages"]

            # If agent used a tool, record the result
            if "tool_calls" in result:
                for tool_call in result["tool_calls"]:
                    tool_name = tool_call["name"]
                    args = tool_call["args"]
                    logger.info(f"🔧 Using tool: {tool_name} with args: {args}")

                    # Log the result summary (truncated for readability)
                    result_text = str(tool_call["result"])
                    result_summary = (
                        result_text[:100] + "..."
                        if len(result_text) > 100
                        else result_text
                    )
                    logger.info(f"📊 Tool result: {result_summary}")

                    new_state["tool_results"][tool_call["id"]] = tool_call["result"]

                    # Add the reasoning step
                    thought = result.get("thought", "")
                    logger.info(
                        f"💭 Agent thought: {thought[:150]}..."
                        if len(thought) > 150
                        else thought
                    )

                    new_state["steps"].append(
                        {
                            "thought": thought,
                            "action": tool_name,
                            "action_input": args,
                            "result": tool_call["result"],
                        }
                    )
            else:
                # If no tool was used, the agent might be answering
                logger.info("📝 Agent is formulating an answer (no tool used)")

                # Try to extract thought if available
                thought = result.get("thought", "")
                if thought:
                    logger.info(
                        f"💭 Agent thought: {thought[:150]}..."
                        if len(thought) > 150
                        else thought
                    )

            return new_state

        # Check if we should end the process
        def should_end(state: AgentState) -> Union[bool, str]:
            """Determine if the agent execution should end."""
            # If we've reached max iterations
            if len(state["steps"]) >= self.max_iterations:
                logger.warning(f"⚠️ Reached maximum iterations ({self.max_iterations})")
                return True

            # Check the latest message for finish indication
            messages = state["messages"]
            if messages:
                last_message = messages[-1]
                # Check if it's an assistant message (AIMessage in LangChain)
                if hasattr(last_message, "type") and last_message.type == "ai":
                    content = last_message.content
                    # Look for React's final answer pattern
                    if "Final Answer:" in content:
                        logger.info("✅ Agent reached final answer")
                        return True
                # For backward compatibility with dictionary messages
                elif (
                    isinstance(last_message, dict)
                    and last_message.get("role") == "assistant"
                ):
                    content = last_message["content"]
                    if "Final Answer:" in content:
                        logger.info("✅ Agent reached final answer")
                        return True

            return False

        # Define the graph structure
        builder.add_node("prepare", prepare_state)
        builder.add_node("reason", process_reasoning)

        # Add edges
        builder.set_entry_point("prepare")
        builder.add_edge("prepare", "reason")
        builder.add_conditional_edges(
            "reason", should_end, {True: END, False: "reason"}
        )

        return builder.compile()

    def _extract_final_answer(self, state: AgentState) -> str:
        """
        Extract the final answer from the agent state.

        Args:
            state: The final agent state

        Returns:
            The final answer as a string
        """
        messages = state["messages"]
        if not messages:
            return "No answer was generated."

        # Find the last assistant message
        last_message = messages[-1]
        content = ""

        # Handle different message types
        if hasattr(last_message, "type") and last_message.type == "ai":
            content = last_message.content
        elif isinstance(last_message, dict) and last_message.get("role") == "assistant":
            content = last_message["content"]
        else:
            # Try to find the last assistant message
            for msg in reversed(messages):
                if (hasattr(msg, "type") and msg.type == "ai") or (
                    isinstance(msg, dict) and msg.get("role") == "assistant"
                ):
                    if hasattr(msg, "content"):
                        content = msg.content
                    elif isinstance(msg, dict):
                        content = msg.get("content", "")
                    break

        if not content:
            return "No answer was generated."

        # Extract the final answer section if present
        if "Final Answer:" in content:
            _, answer = content.split("Final Answer:", 1)
            return answer.strip()

        return content.strip()

    async def run(self, task: str, **kwargs) -> Any:
        """
        Run the agent on a specific task.

        The agent will break down the task into smaller sub-tasks and use its tools
        to accomplish the overall objective.

        Args:
            task: The task to perform
            **kwargs: Additional arguments for the agent

        Returns:
            The result of the agent's execution
        """
        logger.info(f"🧠 Running LangGraph agent with task: {task}")
        logger.info(
            f"🧰 Available tools: {', '.join([tool.name for tool in self.tools])}"
        )

        # Create graph if it hasn't been created already
        if self._graph is None:
            logger.info("🔄 Creating LangGraph workflow")
            self._graph = self._create_graph()

        # Prepare initial state
        initial_state = {
            "messages": [],
            "tools": self.tools,
            "tool_results": {},
            "steps": [],
            "original_query": task,
        }

        # Execute the graph
        try:
            logger.info("🚀 Starting LangGraph execution")
            final_state = self._graph.invoke(initial_state)

            # Extract and return the final answer
            result = self._extract_final_answer(final_state)
            logger.info(
                f"✅ Agent completed task successfully after {len(final_state.get('steps', []))} steps"
            )

            # If in verbose mode, include the reasoning steps
            if self.verbose:
                steps = final_state.get("steps", [])
                return {"answer": result, "steps": steps, "num_steps": len(steps)}

            return result

        except Exception as e:
            logger.error(f"❌ Agent execution failed: {str(e)}")
            raise
