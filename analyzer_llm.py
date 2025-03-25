"""
Financial Analysis LLM for Analyst AI.

This module contains functions for using OpenAI LLMs to analyze and interpret 
the results of financial tool calls in natural language.
"""
import json
import logging
from typing import Dict, Any

from openai import OpenAI
from ai_analyst.app.core.config import settings

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=settings.OPENAI_API_KEY)


def analyze_tool_output(tool_result: Dict[str, Any], original_query: str) -> str:
    """
    Uses OpenAI GPT-4 to analyze and interpret financial tool output in natural language.
    
    Args:
        tool_result (dict): The result dictionary from a tool execution
        original_query (str): The original user query that led to this tool call
        
    Returns:
        str: A natural language analysis of the tool result for an investor
        
    Example:
        >>> result = {"value": 13.5, "ticker": "JPM", "metric": "CET1"}
        >>> query = "What is the CET1 ratio for JPMorgan?"
        >>> analyze_tool_output(result, query)
        "JPMorgan's CET1 ratio is 13.5%. This is a strong capital position..."
    """
    try:
        # Convert tool result to a string for the prompt
        tool_result_str = json.dumps(tool_result, indent=2)
        
        # Define the system message for the LLM
        system_message = """You are a financial analyst assistant.
You provide clear, concise interpretations of financial data for investors.
Focus on explaining what the numbers mean, their significance, and implications.
Keep your analysis brief (2-3 sentences) unless the data requires more explanation.
Use professional but accessible language that an investor would understand."""
        
        # Define the user message including the query and tool result
        user_message = f"""Given the following query and result from a data tool, interpret the result for an investor in plain English.

Query: {original_query}
Tool Result: {tool_result_str}

Your analysis:"""
        
        # Call the OpenAI API using the latest client
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            temperature=0.5,  # Slightly higher temperature for more natural language
            max_tokens=400    # Allow for detailed analysis
        )
        
        # Extract the analysis text
        analysis = response.choices[0].message.content.strip()
        
        return analysis
    
    except Exception as e:
        logger.error(f"Error in analyze_tool_output: {str(e)}")
        # Return a default error message
        return f"I couldn't analyze the result due to an error: {str(e)}. The raw result was: {json.dumps(tool_result)}."


if __name__ == "__main__":
    # Example usage
    test_case = {
        "result": {
            "value": 13.5,
            "ticker": "JPM",
            "metric": "CET1"
        },
        "query": "What is the CET1 ratio for JPMorgan?"
    }
    
    analysis = analyze_tool_output(test_case["result"], test_case["query"])
    print(f"Original Query: {test_case['query']}")
    print(f"Tool Result: {json.dumps(test_case['result'], indent=2)}")
    print(f"Analysis: {analysis}") 