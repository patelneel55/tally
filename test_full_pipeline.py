"""
Full Analyst AI Pipeline Test

This script demonstrates the complete flow from natural language query to financial analysis:
1. User enters a natural language query about financial metrics
2. The planner LLM interprets the query and determines the appropriate tool to call
3. The tool is executed with the planned arguments
4. The analyzer LLM interprets the tool result and provides a financial analysis
"""
import os
import sys
import json

# Add the project root to the path so we can import the modules
sys.path.append('.')

# Try different ways to access the OpenAI API key
if not os.environ.get('OPENAI_API_KEY'):
    # Try to read from .env file
    try:
        with open('.env', 'r') as f:
            for line in f:
                if line.startswith('OPENAI_API_KEY='):
                    key = line.strip().split('=', 1)[1].strip('"').strip("'")
                    os.environ['OPENAI_API_KEY'] = key
                    break
    except Exception as e:
        print(f"Could not read .env file: {e}")

# Import our modules
from planner_llm import plan_tool_call
from tool_registry import run_tool
from analyzer_llm import analyze_tool_output


def process_query_with_analysis(query: str):
    """
    Process a natural language query through the full pipeline:
    1. Plan tool call
    2. Execute tool
    3. Analyze result
    
    Args:
        query (str): The natural language query
        
    Returns:
        dict: A dictionary containing all stages of processing
    """
    print(f"\n{'='*80}")
    print(f"QUERY: {query}")
    print(f"{'='*80}")
    
    # Step 1: Plan which tool to use
    print("\n--- PLANNING TOOL CALL ---")
    plan = plan_tool_call(query)
    print(f"Plan: {json.dumps(plan, indent=2)}")
    
    # Error handling for tool planning
    if plan.get('tool') == 'error':
        print("Tool planning failed.")
        return {
            "query": query,
            "plan": plan,
            "result": None,
            "analysis": f"I couldn't understand how to process your query. Error: {plan.get('args', {}).get('error', 'Unknown error')}"
        }
    
    # Step 2: Execute the planned tool
    print("\n--- EXECUTING TOOL ---")
    tool_name = plan['tool']
    tool_args = plan['args']
    
    print(f"Executing tool '{tool_name}' with args: {json.dumps(tool_args, indent=2)}")
    result = run_tool(tool_name, tool_args)
    print(f"Tool Result: {json.dumps(result, indent=2)}")
    
    # Step 3: Analyze the result
    print("\n--- ANALYZING RESULT ---")
    analysis = analyze_tool_output(result, query)
    print(f"Analysis: {analysis}")
    print(f"\n{'-'*80}")
    
    # Return all pipeline stages for reference
    return {
        "query": query,
        "plan": plan,
        "result": result,
        "analysis": analysis
    }


if __name__ == "__main__":
    # Test queries
    test_queries = [
        # Queries specifically targeting the supported metrics
        "What is the company name for ticker AAPL?",
        "What is the market cap of JPMorgan Chase?",
        "How many employees does Microsoft have?",
        
        # Keep some of the original queries to test error handling
        "What is JPMorgan's CET1 ratio?",
        "What's Apple's P/E ratio?",
        "What is the ROE for an unknown company called XYZ Corp?",
        "Explain what a good CET1 ratio is for banks",
    ]
    
    # Process each query
    results = []
    for query in test_queries:
        result = process_query_with_analysis(query)
        results.append(result)
    
    # Print a summary
    print("\n\n" + "="*40)
    print("SUMMARY OF RESULTS")
    print("="*40)
    
    for i, result in enumerate(results, 1):
        query = result["query"]
        analysis = result["analysis"]
        
        print(f"\n{i}. QUERY: {query}")
        print(f"   ANALYSIS: {analysis[:100]}..." if len(analysis) > 100 else f"   ANALYSIS: {analysis}") 