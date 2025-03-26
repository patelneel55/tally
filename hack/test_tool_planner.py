"""
Test script for the full tool planning and execution flow.

This script demonstrates:
1. Taking a natural language query
2. Using the LLM to plan the appropriate tool call
3. Executing the tool with the planned arguments
4. Returning the final result
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

def process_natural_language_query(query: str):
    """
    Process a natural language query by:
    1. Planning which tool to use
    2. Executing that tool with the planned arguments
    
    Args:
        query (str): The natural language query
        
    Returns:
        dict: The result from the executed tool
    """
    print(f"Query: {query}")
    
    # Step 1: Plan the tool call
    print("Planning tool call...")
    plan = plan_tool_call(query)
    print(f"Plan: {json.dumps(plan, indent=2)}")
    
    # Check if planning failed
    if plan.get('tool') == 'error':
        print("Tool planning failed.")
        return plan
    
    # Step 2: Execute the planned tool
    tool_name = plan['tool']
    tool_args = plan['args']
    
    print(f"Executing tool '{tool_name}' with args: {json.dumps(tool_args, indent=2)}")
    result = run_tool(tool_name, tool_args)
    print(f"Result: {json.dumps(result, indent=2)}")
    
    return result


if __name__ == "__main__":
    # Define test queries
    test_queries = [
        "What is the CET1 ratio for JPMorgan?",
        "Tell me the price to book ratio for Bank of America",
        "What is the P/E ratio for Apple?",
        "What is the net income for Microsoft?",
        "What is the ROE for an unknown company?"  # Should handle unknown ticker
    ]
    
    # Process each query
    for query in test_queries:
        print("\n" + "="*50)
        result = process_natural_language_query(query)
        print("="*50 + "\n") 