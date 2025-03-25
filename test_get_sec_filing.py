"""
Test SEC Filing Retrieval Tool

This script tests the get_sec_filing function by retrieving a 10-K filing for JPM (JPMorgan Chase)
and displays the metadata and a preview of the filing text to verify functionality.

What this file does:
1. Imports the get_sec_filing function
2. Calls the function with JPM ticker and 10-K form type (or user-provided values)
3. Prints the metadata and a preview of the filing text (first 1000 characters)

Usage:
    python test_get_sec_filing.py
    python test_get_sec_filing.py AAPL
    python test_get_sec_filing.py MSFT 10-Q
"""

import os
import sys
from tools.get_sec_filing import get_sec_filing


def main():
    """Test the get_sec_filing function with the specified ticker and form type"""
    # Get ticker and form_type from command line arguments or use defaults
    ticker = sys.argv[1] if len(sys.argv) > 1 else "JPM"
    form_type = sys.argv[2] if len(sys.argv) > 2 else "10-K"
    
    print(f"Fetching {ticker} {form_type} filing...")
    
    # Call the function to get the filing
    result = get_sec_filing(ticker, form_type)
    
    # Print the metadata
    print("\n--- FILING METADATA ---")
    print(f"Ticker:       {result.get('ticker')}")
    print(f"Form Type:    {result.get('form_type')}")
    print(f"Filing Date:  {result.get('filing_date')}")
    print(f"Company Name: {result.get('company_name')}")
    print(f"CIK:          {result.get('cik')}")
    
    # Check if there was an error
    if "error" in result:
        print(f"\nERROR: {result.get('error')}")
        return 1
    
    # Print a preview of the filing text
    print("\n--- FILING TEXT PREVIEW (first 1000 characters) ---")
    filing_text = result.get('filing_text', '')
    preview = filing_text[:1000] + "..." if filing_text else "No text available"
    print(preview)
    
    # Print file path for reference
    filing_date = result.get('filing_date', '').replace('-', '')
    filename = f"sec_data/filings/{ticker}_{form_type}_{filing_date}.txt"
    if os.path.exists(filename):
        file_size = os.path.getsize(filename) / (1024 * 1024)  # Convert to MB
        print(f"\nFiling saved to: {filename} ({file_size:.2f} MB)")
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 