#!/usr/bin/env python
"""
Quick test script for the get_financial_metric function.
This is a simple sanity check, not a full pytest-based test.
"""

from tools.get_financial_metric import get_financial_metric

def main():
    # Call the function to get JPM's market cap
    print("Testing get_financial_metric with JPM market_cap:")
    result = get_financial_metric("JPM", "market_cap")
    
    # Print the entire result dictionary
    print(f"Result: {result}")
    
    # Print formatted output for better readability
    value = result.get('value', 'Not available')
    ticker = result.get('ticker', '')
    metric = result.get('metric', '')
    error = result.get('error', None)
    
    print(f"\nTicker: {ticker}")
    print(f"Metric: {metric}")
    print(f"Value: {value}")
    
    if error:
        print(f"Error: {error}")
    else:
        print("No errors reported")

if __name__ == "__main__":
    main() 