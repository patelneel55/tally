"""
SEC Filing Keyword Analysis Test

This script tests the functionality of summarizing keyword matches from a SEC filing
using GPT-4 to generate an analysis.

What this file does:
1. Loads a JPM 10-K filing from PDF
2. Extracts text from all pages
3. Searches for specific financial keywords
4. Generates a summary of the findings using GPT-4
"""

import os
import sys

# Add the parent directory to the path to allow importing from tools
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the required functions
from tools.sec_preprocessor import extract_text_from_pdf
from tools.sec_keyword_searcher import search_filing_for_keywords
from tools.analyze_keyword_matches import summarize_keyword_matches


def main():
    """Test summarizing keyword matches from a JPM 10-K filing using GPT-4."""
    # Path to the JPM 10-K PDF
    pdf_path = "cache/sec_filings/JPM/JPM 10K 2024.pdf"
    
    print(f"Processing PDF: {pdf_path}")
    print("Extracting text from PDF pages...")
    
    # Extract text from the PDF
    try:
        pages = extract_text_from_pdf(pdf_path)
        print(f"Successfully extracted text from {len(pages)} pages.")
    except Exception as e:
        print(f"Error extracting text from PDF: {str(e)}")
        return 1
    
    # Banking and capital-specific keywords
    keywords = [
        "CET1",
        "office loan",
        "CRE", 
        "commercial real estate",
        "Tier 1 capital",
        "unrealized losses",
        "loan risk"
    ]
    
    print(f"\nSearching for {len(keywords)} keywords: {', '.join(keywords)}")
    print("This may take a moment for large PDFs...\n")
    
    # Search for keywords in the extracted text
    matches = search_filing_for_keywords(pages, keywords, window=100)
    
    print(f"Found {len(matches)} keyword matches.")
    
    # Generate a summary of the keyword matches with a specific query
    print("\nGenerating summary with GPT-4...")
    summary = summarize_keyword_matches(
        matches, 
        original_query="What does the filing say about commercial real estate exposure and capital strength?"
    )
    
    print("\n--- SUMMARY ---")
    print(summary)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())