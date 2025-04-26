# LangGraphAgent

## File: infra/agents/lang_graph.py

### Purpose
The LangGraphAgent implements the IAgent interface using the LangGraph library to create a structured reasoning workflow. It uses the ReAct (Reasoning and Acting) approach to break down complex financial analysis queries into smaller logical questions that can be addressed through tools or vector database queries while maintaining focus on the original task.

### Functions and Classes

#### `AgentState` TypedDict
- Maintains the state during agent execution including:
  - `messages`: Chat history between the user and the agent
  - `tools`: Available tools for the agent to use
  - `tool_results`: Results from executed tools
  - `steps`: Tracking of reasoning steps for transparency
  - `original_query`: Original user query for reference throughout execution

#### `LangGraphAgent` Class
- **Constructor**: Initializes the agent with LLM provider, verbose flag, and max_iterations
- **add_tool(tool)**: Adds a tool to the agent's toolset and resets the graph
- **get_tools()**: Returns all tools available to the agent
- **_create_graph()**: Creates the LangGraph workflow for structured reasoning
- **_extract_final_answer(state)**: Extracts the final answer from the agent's state
- **run(task, **kwargs)**: Core method that executes the agent's workflow on a task

### Key Logic Decisions

1. **State Management**
   - Maintains a persistent state object throughout execution to track progress
   - Keeps the original query in the state to maintain focus on the primary objective

2. **Workflow Structure**
   - Uses LangGraph's StateGraph for a structured reasoning workflow
   - Two main nodes: "prepare" (sets up initial state) and "reason" (executes ReAct loop)
   - Conditional logic to determine when to continue reasoning vs. when to finish

3. **ReAct Prompting**
   - Uses create_react_agent from LangGraph's prebuilt functionality
   - Enables the agent to alternate between reasoning and acting through tools
   - Structured to break down complex queries into manageable sub-tasks

4. **Financial Context**
   - Custom system prompt oriented toward financial analysis
   - Guidelines for maintaining precision with financial metrics and dates
   - Instructions to synthesize information from multiple sources

5. **Termination Conditions**
   - Ends when agent reaches a "Final Answer"
   - Safety limit on maximum reasoning iterations (default 15)
   - Exception handling for graceful failure

### Best Practices and Alternatives Considered

1. **Why LangGraph?**
   - Provides structured state management for complex reasoning workflows
   - Enables detailed tracking of agent reasoning steps
   - Supports conditional branching based on agent's reasoning output
   - Alternative: Direct LangChain agents are simpler but offer less structured workflow control

2. **Why ReAct Prompting?**
   - Enables breaking down complex queries into logical sub-tasks
   - Alternates between reasoning and tool use naturally
   - More transparent reasoning process compared to other prompting methods
   - Alternative: Function calling alone is more concise but lacks explicit reasoning

3. **Verbose Option**
   - Returns detailed execution steps when verbose=True for debugging
   - Returns only the final answer in production for cleaner responses
   - Helps with debugging complex agent reasoning paths

4. **Tool Usage Tracking**
   - Records all tool interactions for auditability
   - Critical for financial analysis where verification and source tracing is important

## Usage Example

```python
from infra.agents import LangGraphAgent
from infra.core.llm_providers import OpenAIProvider
from infra.tools.pipelines import IndexingPipelineTool, RAGQueryTool

# Create components
llm_provider = OpenAIProvider(api_key="your_key", model_name="gpt-4-turbo")
agent = LangGraphAgent(llm_provider=llm_provider, verbose=True)

# Add tools
agent.add_tool(IndexingPipelineTool(pipeline=indexing_pipeline))
agent.add_tool(RAGQueryTool(pipeline=rag_pipeline))

# Run the agent
result = await agent.run("Analyze Apple's R&D expenditures from 2020-2023")
```

In this implementation, the agent can handle complex financial analysis queries by intelligently breaking them down, using financial data tools, and maintaining focus on the original objective throughout the process.

## WebLoader and Tests

### tally/src/infra/ingestion/web_loader.py
**Purpose**: Provides a document loader for web content that can crawl websites and extract content.

**Key Components**:
- `CrawlStrategy` enum: Defines different strategies for crawling websites (same hostname, same domain, etc.)
- `CrawlConfig` class: Configuration for crawling parameters
- `WebLoader` class: Implements the `IDocumentLoader` interface to load and process web content

**Key Logic**:
- Uses PlaywrightCrawler for crawling web pages
- Implements caching for efficient retrieval of previously crawled content
- Processes HTML content into Document objects for further processing

### tally/tests/unit/infra/ingestion/test_web_loader.py
**Purpose**: Tests for the WebLoader class to ensure it behaves as expected.

**Test Suite Components**:
- Mock classes for PlaywrightCrawler, Cache, and related components
- Tests for initialization with default and custom values
- Tests for crawling behavior with and without cached responses
- Tests for the cache hook functionality that intercepts requests

**Key Decisions**:
- Used mocks to avoid making actual web requests during tests
- Tested both cached and non-cached scenarios
- Validated core functionality while isolating external dependencies

## Test Architecture and Shared Fixtures

### tally/tests/unit/conftest.py
**Purpose**: Provides shared test fixtures that can be used across all unit tests.

**Key Components**:
- `mock_sqlalchemy_engine`: Mocks the database engine to avoid actual database connections
- `mock_cache`: Provides a mock implementation of the Cache class for testing
- `mock_settings`: Provides mock application settings for testing

### tally/tests/unit/infra/ingestion/conftest.py
**Purpose**: Provides shared test fixtures specific to the ingestion module.

**Key Components**:
- Mock classes for web components (PlaywrightCrawler, Page, Request, etc.)
- `mock_playwright_crawler`: A fixture to mock the PlaywrightCrawler class

**Key Decisions**:
- Structured fixtures at different levels for better organization and reuse
- Root-level fixtures (`unit/conftest.py`) for widely used components
- Module-specific fixtures in module-specific conftest.py files
- Mock implementations mimic the behavior of real objects while avoiding actual external calls
