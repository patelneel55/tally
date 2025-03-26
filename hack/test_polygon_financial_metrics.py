"""
Test Polygon Financial Metrics

This script tests the get_financial_metric function with real Polygon API data
to validate functionality and identify supported metrics.

What this file does:
1. Tests valid metrics that should return real values from Polygon
2. Tests error handling for invalid metrics and tickers
3. Provides clear output of results with error highlighting
"""

import sys
from tools.get_financial_metric import get_financial_metric

# ANSI color codes for terminal output
class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"


def print_separator(width=80):
    """Print a separator line for better readability."""
    print("-" * width)


def print_section_header(title):
    """Print a formatted section header."""
    print_separator()
    print(f"{Colors.BOLD}{Colors.BLUE}{title}{Colors.RESET}")
    print_separator()


def print_result(description, result):
    """
    Print a test result with formatting.
    Highlights errors in red if present.
    """
    print(f"\n{Colors.BOLD}{description}:{Colors.RESET}")
    
    # Check if the result has an error
    if "error" in result:
        print(f"  Ticker: {result.get('ticker')}")
        print(f"  Metric: {result.get('metric')}")
        print(f"  Value: {result.get('value')}")
        print(f"  {Colors.RED}Error: {result.get('error')}{Colors.RESET}")
    else:
        print(f"  Ticker: {result.get('ticker')}")
        print(f"  Metric: {result.get('metric')}")
        print(f"  Value: {Colors.GREEN}{result.get('value')}{Colors.RESET}")


def test_valid_metrics():
    """
    Test metrics that should be valid and return actual values from Polygon.
    These use real API calls and should return live data.
    """
    print_section_header("VALID METRIC TESTS (Expected to return real values)")
    
    # Test 1: JPM market cap
    result = get_financial_metric("JPM", "market_cap")
    print_result("JPM market capitalization", result)
    
    # Test 2: JPM net income
    result = get_financial_metric("JPM", "net_income")
    print_result("JPM net income", result)
    
    # Test 3: MSFT revenue
    result = get_financial_metric("MSFT", "revenue")
    print_result("MSFT revenue", result)
    
    # Test 4: AAPL total employees
    result = get_financial_metric("AAPL", "total_employees")
    print_result("AAPL total employees", result)
    
    # Test 5: BAC name
    result = get_financial_metric("BAC", "name")
    print_result("BAC company name", result)


def test_invalid_metrics():
    """
    Test metrics that are invalid or use incorrect tickers.
    This tests error handling in the function.
    """
    print_section_header("INVALID METRIC / TICKER HANDLING")
    
    # Test 6: P/E ratio (may be unsupported in the current API response structure)
    result = get_financial_metric("AAPL", "pe_ratio")
    print_result("AAPL P/E ratio (potentially unsupported)", result)
    
    # Test 7: Invalid ticker
    result = get_financial_metric("XYZ", "market_cap")
    print_result("Invalid ticker (XYZ) market cap", result)
    
    # Test 8: Unknown metric
    result = get_financial_metric("MSFT", "unknown_metric")
    print_result("MSFT unknown metric", result)


def main():
    """Run all tests sequentially."""
    print(f"\n{Colors.BOLD}POLYGON FINANCIAL METRICS TEST{Colors.RESET}")
    print(f"Testing with live Polygon API data\n")
    
    try:
        # Test valid metrics
        test_valid_metrics()
        
        # Test invalid metrics
        test_invalid_metrics()
        
        print_separator()
        print(f"\n{Colors.GREEN}Tests completed.{Colors.RESET}")
        print("Note: Some 'valid' metrics may still return errors if:")
        print("  - The Polygon API doesn't provide that data")
        print("  - The path to the metric in the API response is incorrect")
        print("  - The API rate limit has been reached")
        
    except Exception as e:
        print(f"\n{Colors.RED}Error running tests: {str(e)}{Colors.RESET}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
