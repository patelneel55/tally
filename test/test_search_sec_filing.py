"""
SEC Filing Keyword Search Test

This script tests the functionality of extracting text from a PDF SEC filing
and searching for specific keywords with context.

What this file does:
1. Loads a JPM 10-K filing from PDF
2. Extracts text from all pages
3. Searches for specific financial keywords
4. Prints matching snippets with context
"""

import os
import sys
import json
from pprint import pprint

# Add the parent directory to the path to allow importing from tools
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the required functions
from tools.sec_preprocessor import extract_text_from_pdf
from tools.sec_keyword_searcher import search_filing_for_keywords


def main():
    """Test searching for keywords in a JPM 10-K filing."""
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
    
    # Process and display the results
    print(f"Found {len(matches)} keyword matches:")
    
    # Group matches by keyword for better readability
    grouped_matches = {}
    for match in matches:
        keyword = match["keyword"]
        if keyword not in grouped_matches:
            grouped_matches[keyword] = []
        grouped_matches[keyword].append(match)
    
    # Print a sample of matches for each keyword
    for keyword, matches_list in grouped_matches.items():
        print(f"\n--- {keyword.upper()} ({len(matches_list)} matches) ---")
        # Show just the first 3 matches per keyword to avoid overwhelming output
        for match in matches_list[:3]:
            print(f"Page {match['page']}:")
            # Format the context for better readability
            context = match['context'].replace('\n', ' ').strip()
            # Bold the keyword within the context
            highlighted = context.replace(
                keyword, 
                f"\033[1m{keyword}\033[0m"
            ).replace(
                keyword.upper(), 
                f"\033[1m{keyword.upper()}\033[0m"
            ).replace(
                keyword.capitalize(), 
                f"\033[1m{keyword.capitalize()}\033[0m"
            )
            print(f"  {highlighted}")
            print()
    
    # Save the full results to a JSON file
    output_dir = "sec_data/analysis"
    os.makedirs(output_dir, exist_ok=True)
    output_file = f"{output_dir}/JPM_10K_keyword_analysis.json"
    
    with open(output_file, 'w') as f:
        json.dump(matches, f, indent=2)
    
    print(f"\nFull keyword analysis saved to: {output_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main()) 