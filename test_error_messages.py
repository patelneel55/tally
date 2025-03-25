#!/usr/bin/env python
"""
Test error messages when metrics aren't found in Polygon API responses.
"""
from tools.get_financial_metric import get_financial_metric

def main():
    """Test various error cases and print the results."""
    print("\n=== TESTING IMPROVED ERROR MESSAGES ===\n")
    
    # Test cases likely to result in errors
    test_cases = [
        # Metrics from ticker details that might not be available
        {"ticker": "AAPL", "metric": "total_employees"},
        
        # Metrics from fundamentals that might not be available
        {"ticker": "GOOGL", "metric": "pe_ratio"},
        {"ticker": "AMZN", "metric": "roe"},
        
        # Unknown/invalid ticker
        {"ticker": "INVALID", "metric": "net_income"},
        
        # Test a ticker that might not have fundamentals data
        {"ticker": "TSLA", "metric": "eps"}
    ]
    
    # Run each test case
    for i, case in enumerate(test_cases, 1):
        ticker = case["ticker"]
        metric = case["metric"]
        
        print(f"\nTest {i}: {ticker} - {metric}")
        result = get_financial_metric(ticker, metric)
        
        if "error" in result:
            print(f"Error returned: {result['error']}")
        else:
            print(f"Value: {result['value']}")
            
    print("\n=== TESTING COMPLETE ===\n")

if __name__ == "__main__":
    main() 