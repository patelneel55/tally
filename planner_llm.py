"""
Tool Planning LLM for Analyst AI.

This module contains functions for using OpenAI LLMs to plan and execute tool calls
based on user natural language queries.
"""
import json
import re
import logging
from typing import Dict, Any

from openai import OpenAI
from ai_analyst.app.core.config import settings

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=settings.OPENAI_API_KEY)


def plan_tool_call(user_query: str) -> Dict[str, Any]:
    """
    Uses OpenAI GPT-4 to plan a tool call based on a natural language query.
    
    Args:
        user_query (str): The user's natural language query
        
    Returns:
        dict: A dictionary containing:
            - tool: The name of the tool to use
            - args: The arguments to pass to the tool
            
    Example:
        >>> plan_tool_call("What's the CET1 ratio for JPMorgan?")
        {'tool': 'get_financial_metric', 'args': {'ticker': 'JPM', 'metric': 'CET1'}}
    """
    try:
        # Define the system message for the LLM
        system_message = """You are a tool planner for a financial research assistant.
Given a natural language query, return only a JSON object with:
    • tool: the name of the tool to use
    • args: the function arguments

You only have access to one tool: get_financial_metric(ticker, metric)

For get_financial_metric, the ONLY supported metrics are:
 * "name" - Full company name
 * "market_cap" - Market capitalization 
 * "total_employees" - Number of employees
 * "net_income" - Net income
 * "pe_ratio" - Price to earnings ratio (P/E)
 * "roe" - Return on equity
 * "total_revenue" - Total revenue
 * "price_to_book" - Price to book ratio
 * "eps" - Earnings per share
 * "total_assets" - Total assets
 * "total_liabilities" - Total liabilities

Example for a supported request:
{
"tool": "get_financial_metric",
"args": {
"ticker": "AAPL",
"metric": "net_income"
}
}

IMPORTANT: 
1. Only use EXACTLY these metric names - e.g., use "pe_ratio" not "P/E" or "P/E ratio"
2. For any query about metrics NOT in the above list (like CET1, beta, dividend yield, etc.), return:
{
"tool": "error",
"args": {
"error": "Unsupported metric"
}
}
3. If the user asks for an explanation rather than a specific metric, also return an error."""
        
        # Call the OpenAI API using the latest client
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_query}
            ],
            temperature=0,  # Use deterministic output for more reliable tool planning
            max_tokens=300  # Limit token usage as we only need a short JSON response
        )
        
        # Extract the raw response text
        raw_response = response.choices[0].message.content.strip()
        
        # Try to extract JSON from the response (handles markdown formatting)
        json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(json_pattern, raw_response)
        
        if match:
            # If JSON is in markdown code block, extract it
            json_str = match.group(1).strip()
        else:
            # Otherwise use the whole response
            json_str = raw_response
        
        # Parse the JSON response
        result = json.loads(json_str)
        
        # Ensure we have the expected keys
        if 'tool' not in result or 'args' not in result:
            logger.warning(f"Malformed tool planning response: {result}")
            raise ValueError("Tool planning response missing required keys")
            
        return result
    
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from LLM response: {e}")
        logger.debug(f"Raw response: {raw_response if 'raw_response' in locals() else 'Not available'}")
        # Return a default error response
        return {
            "tool": "error",
            "args": {
                "error": f"Failed to parse tool planning response: {str(e)}",
                "raw_response": raw_response if 'raw_response' in locals() else "Not available"
            }
        }
    
    except Exception as e:
        logger.error(f"Error in plan_tool_call: {str(e)}")
        # Return a default error response
        return {
            "tool": "error",
            "args": {
                "error": f"Tool planning failed: {str(e)}"
            }
        }


if __name__ == "__main__":
    # Example usage
    test_queries = [
        # Supported metrics
        "What is the company name for Apple?",
        "What is the market cap of JPMorgan?",
        "How many employees does Microsoft have?",
        "What's the net income for Amazon?",
        "What is Tesla's P/E ratio?",
        
        # Unsupported metrics / explanations
        "What is the CET1 ratio for JPMorgan?",
        "What's the dividend yield for Verizon?",
        "Explain how to calculate ROE",
    ]
    
    for query in test_queries:
        print(f"Query: {query}")
        result = plan_tool_call(query)
        print(f"Result: {result}")
        print() 