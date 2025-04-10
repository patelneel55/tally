# RAG Pipeline Tool Implementation

## ✅ Filename
`infra/tools/pipelines.py`

## ✅ Purpose
This file implements tools that wrap pipeline functionality to be used by LangChain agents. It includes the RAGQueryTool which wraps the RAGFinancialAnalysisPipeline to allow agents to perform retrieval-augmented generation (RAG) queries against indexed financial data.

## ✅ Function and Class List

### `RAGQueryToolInput` (Pydantic Model)
A Pydantic input schema that defines the parameters required to use the RAG query tool. It includes:

- `task_description` (str): The query or analysis task to perform using the RAG system
- `retriever_search_kwargs` (Optional[Dict[str, Any]]): Advanced search parameters for the vector store, including filters
- `retriever_search_type` (Optional[str]): Type of search to perform in the vector store

### `RAGQueryTool` (Class)
A tool implementation that wraps the RAGFinancialAnalysisPipeline. This tool allows agents to query indexed SEC filings and other financial data using retrieval-augmented generation (RAG).

Key methods:
- `__init__(pipeline: RAGFinancialAnalysisPipeline)`: Initializes the tool with a RAG pipeline instance
- `run(**kwargs)`: Executes the RAG pipeline with the provided parameters

This tool is registered in the `HybridController` so that it can be:
1. Used directly via pattern matching on user queries
2. Made available to LangChain agents as a tool in their toolkit

## ✅ Key Logic Decisions

### Tool Interface Pattern
- Implemented using the `PipelineTool` base class which standardizes the interface between agent tools and pipeline functionality
- Used a Pydantic model for input validation to ensure proper parameters are passed to the underlying pipeline
- Maintained consistent naming conventions with other pipeline tools (e.g., IndexingPipelineTool)

### Integration with the Controller
- Added the RAG pipeline to the controller's pipeline initialization
- Created a SimpleTextOutputFormatter for directly returning results
- Used RolePromptingStrategy for better control over the RAG prompts
- Added a pattern matcher to allow direct invocation via natural language

### Prompt and Output Handling
- Implemented a simple output formatter that returns raw text for maximum flexibility
- Used the RolePromptingStrategy which positions the LLM as a financial analyst to improve response quality

## ✅ Best Practices and Alternatives

### Best Practices Followed
- **Separation of Concerns**: Kept the tool implementation separate from the pipeline logic
- **Input Validation**: Used Pydantic for robust input validation
- **Documentation**: Added comprehensive docstrings for tool usage
- **Configuration**: Made the tool configurable with different pipeline implementations
- **Consistent API**: Maintained consistent API with other tools in the system

### Alternatives Considered
- **Custom Run Implementation**: Could have overridden the run method for custom behavior, but chose to use the standard PipelineTool implementation for consistency
- **Structured Output**: Could have implemented a structured output formatter, but chose simple text output for maximum flexibility in the initial implementation
- **Task-Specific Tools**: Could have created multiple specialized RAG tools for different financial tasks, but opted for a general-purpose approach with task differentiation via the task_description parameter

### Future Improvements
- Add support for filtering by document source, date range, or company
- Implement structured output options for specific analysis types
- Create specialized RAG tools for common financial analysis tasks
- Add metrics tracking for RAG query performance and relevance

## Vector Store Filtering and Advanced Search

The RAG pipeline supports advanced document retrieval configuration through the `retriever_search_kwargs` parameter, which allows for both filtering and fine-tuning the retrieval process.

### Using Filters in retriever_search_kwargs

Filters are specified using the `filter` key within the `retriever_search_kwargs` dictionary:

```python
result = rag_tool.run(
    task_description="What were Apple's risk factors?",
    retriever_search_kwargs={
        "filter": {"company": "AAPL", "filing_type": "10-K"},
        "k": 5
    }
)
```

### Filter Field Examples

#### 1. Company-Specific Filtering
```python
# Retrieve only documents for Apple
result = rag_tool.run(
    task_description="What were Apple's main risk factors in 2023?",
    retriever_search_kwargs={"filter": {"company": "AAPL"}}
)
```

#### 2. Filing Type Filtering
```python
# Retrieve only 10-K (annual) reports
result = rag_tool.run(
    task_description="Analyze the revenue trends in annual reports",
    retriever_search_kwargs={"filter": {"filing_type": "10-K"}}
)
```

#### 3. Date Range Filtering
```python
# Retrieve documents from a specific year
result = rag_tool.run(
    task_description="What were the main industry trends in 2023?",
    retriever_search_kwargs={"filter": {"year": 2023}}
)
```

#### 4. Combined Filters
```python
# Retrieve 10-Q reports for Microsoft from 2022-2023
result = rag_tool.run(
    task_description="Analyze Microsoft's quarterly performance in 2022-2023",
    retriever_search_kwargs={
        "filter": {
            "company": "MSFT",
            "filing_type": "10-Q",
            "year": {"$gte": 2022, "$lte": 2023}
        }
    }
)
```

## Advanced Search Configuration

The RAG pipeline supports fine-grained control over the retrieval process through search types and parameters.

### Retriever Search Types

The `retriever_search_type` parameter allows you to specify different search algorithms:

1. **Similarity Search (Default)**
   ```python
   result = rag_tool.run(
       task_description="Analyze revenue growth trends",
       retriever_search_type="similarity"
   )
   ```
   Standard vector similarity search that finds semantically similar documents.

2. **Maximum Marginal Relevance (MMR)**
   ```python
   result = rag_tool.run(
       task_description="Give me diverse perspectives on climate risk",
       retriever_search_type="mmr",
       retriever_search_kwargs={"fetch_k": 20, "k": 5, "lambda_mult": 0.7}
   )
   ```
   Balances relevance with diversity to reduce redundancy in retrieved documents.

3. **Similarity Score Threshold**
   ```python
   result = rag_tool.run(
       task_description="Find very specific information about supply chain risks",
       retriever_search_type="similarity_score_threshold",
       retriever_search_kwargs={"score_threshold": 0.8, "k": 10}
   )
   ```
   Only returns documents with similarity scores above the specified threshold.

### Advanced Search Parameters

The `retriever_search_kwargs` parameter allows you to fine-tune the retrieval process:

#### 1. Controlling Retrieval Count
```python
# Retrieve more documents for complex analyses
result = rag_tool.run(
    task_description="Perform a comprehensive analysis of market risks",
    retriever_search_kwargs={"k": 10}  # Retrieve 10 documents instead of default 4
)
```

#### 2. Combining Advanced Parameters with Filters
```python
# More diverse results for a specific company and filing type
result = rag_tool.run(
    task_description="Give me diverse perspectives on Tesla's risks",
    retriever_search_type="mmr",
    retriever_search_kwargs={
        "filter": {"company": "TSLA", "filing_type": "10-K"},
        "k": 5,           # Return 5 documents
        "fetch_k": 20,    # Initially fetch 20 documents
        "lambda_mult": 0.7  # Balance between relevance (1.0) and diversity (0.0)
    }
)
```

#### 3. Setting Score Threshold
```python
# Only return highly relevant results
result = rag_tool.run(
    task_description="Find specific mentions of chip shortages",
    retriever_search_kwargs={
        "score_threshold": 0.85,  # Only documents with >0.85 similarity score
        "k": 10                   # Up to 10 documents if they meet threshold
    }
)
```

#### 4. Comprehensive Example
```python
# Complex query with multiple parameters
result = rag_tool.run(
    task_description="Analyze semiconductor supply chain risks for tech companies",
    retriever_search_type="mmr",
    retriever_search_kwargs={
        "filter": {
            "filing_type": "10-K",
            "year": {"$gte": 2021, "$lte": 2023}
        },
        "k": 8,               # Return 8 documents
        "fetch_k": 30,        # Initially fetch 30 for diversity selection
        "lambda_mult": 0.6    # Balance relevance vs diversity
    }
)
```
