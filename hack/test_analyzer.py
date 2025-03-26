"""
Test script for the financial analyzer LLM functionality.

This script demonstrates how the analyzer interprets various financial metrics:
1. CET1 ratio (capital adequacy)
2. P/B ratio (valuation)
3. ROE (profitability)
4. P/E ratio (valuation)
5. Net Income (financial performance)
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
from analyzer_llm import analyze_tool_output


def test_analysis(test_cases):
    """
    Test the analyze_tool_output function with various test cases.
    
    Args:
        test_cases (list): List of dictionaries with 'result' and 'query' keys
        
    Returns:
        None
    """
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*50}")
        print(f"TEST CASE #{i}")
        print(f"{'='*50}")
        
        print(f"Original Query: {test_case['query']}")
        print(f"Tool Result: {json.dumps(test_case['result'], indent=2)}")
        
        # Run the analysis
        analysis = analyze_tool_output(test_case['result'], test_case['query'])
        
        print(f"\nANALYSIS:")
        print(f"{analysis}")
        print(f"\n{'-'*50}")


if __name__ == "__main__":
    # Define test cases for different financial metrics
    test_cases = [
        # CET1 Ratio - Capital adequacy metric
        {
            "result": {
                "value": 13.5,
                "ticker": "JPM",
                "metric": "CET1"
            },
            "query": "What is the CET1 ratio for JPMorgan?"
        },
        
        # P/B Ratio - Valuation metric
        {
            "result": {
                "value": 1.2,
                "ticker": "BAC",
                "metric": "P/B"
            },
            "query": "What's the price to book ratio for Bank of America?"
        },
        
        # ROE - Profitability metric
        {
            "result": {
                "value": 15.2,
                "ticker": "JPM",
                "metric": "ROE"
            },
            "query": "Tell me about JPMorgan's return on equity"
        },
        
        # P/E Ratio - Valuation metric
        {
            "result": {
                "value": 28.4,
                "ticker": "AAPL",
                "metric": "P/E"
            },
            "query": "What is Apple's P/E ratio?"
        },
        
        # Net Income - Performance metric
        {
            "result": {
                "value": 72.4,
                "ticker": "MSFT",
                "metric": "NET_INCOME"
            },
            "query": "How much did Microsoft earn last year?"
        },
        
        # Error case with unknown ticker
        {
            "result": {
                "value": "N/A",
                "ticker": "UNKNOWN",
                "metric": "ROE",
                "error": "Ticker not found"
            },
            "query": "What is the ROE for XYZ Corp?"
        }
    ]
    
    # Run the tests
    test_analysis(test_cases) 