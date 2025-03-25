"""
Starbucks 10-K Keyword Analysis Test

This script tests the functionality of retrieving and summarizing keyword matches from Starbucks' SEC filing
using GPT-4 to generate an analysis.

What this file does:
1. Downloads the latest Starbucks 10-K filing
2. Extracts text either from PDF or directly from the text file
3. Searches for specific retail, coffee industry, and financial keywords
4. Generates a summary of the findings using GPT-4
5. Tightens the summary using a professional equity analyst tone
"""

import os
import sys

# Add the parent directory to the path to allow importing from tools
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the required functions
from tools.get_sec_filing import get_sec_filing
from tools.sec_preprocessor import extract_text_from_pdf
from tools.sec_keyword_searcher import search_filing_for_keywords
from tools.analyze_keyword_matches import summarize_keyword_matches
from tools.tighten_llm_insight import tighten_llm_insight


def main():
    """Test summarizing keyword matches from a Starbucks 10-K filing using GPT-4."""
    # Download the latest Starbucks 10-K filing
    ticker = "SBUX"
    form_type = "10-K"
    
    print(f"Downloading the latest {form_type} filing for {ticker}...")
    filing_data = get_sec_filing(ticker=ticker, form_type=form_type)
    
    if "error" in filing_data and filing_data["error"]:
        print(f"Error getting SEC filing: {filing_data['error']}")
        return 1
    
    # Process either the PDF or the text file
    pages = []
    if filing_data.get("pdf_path"):
        pdf_path = filing_data["pdf_path"]
        print(f"Processing PDF: {pdf_path}")
        print("Extracting text from PDF pages...")
        
        # Extract text from the PDF
        try:
            pages = extract_text_from_pdf(pdf_path)
            print(f"Successfully extracted text from {len(pages)} pages.")
        except Exception as e:
            print(f"Error extracting text from PDF: {str(e)}")
            return 1
    elif filing_data.get("filing_text"):
        print("Using text directly from the SEC filing...")
        # Create a single page from the filing text
        filing_text = filing_data["filing_text"]
        pages = [{"page": 1, "text": filing_text}]
        print(f"Successfully loaded text ({len(filing_text)} characters).")
    else:
        print("No text or PDF available for analysis.")
        return 1
    
    # Starbucks-specific keywords
    keywords = [
        "coffee",
        "store growth",
        "China",
        "mobile app",
        "loyalty program", 
        "revenue",
        "operating margin",
        "food sales",
        "digital",
        "competition",
        "supply chain",
        "sustainability",
        "inflation"
    ]
    
    print(f"\nSearching for {len(keywords)} keywords: {', '.join(keywords)}")
    print("This may take a moment for large documents...\n")
    
    # Search for keywords in the extracted text
    matches = search_filing_for_keywords(pages, keywords, window=100)
    
    print(f"Found {len(matches)} keyword matches.")
    
    # Generate a summary of the keyword matches with a specific query
    print("\nGenerating summary with GPT-4...")
    summary = summarize_keyword_matches(
        matches, 
        original_query="What does the filing reveal about Starbucks' revenue drivers, store growth strategy, digital initiatives, and risks in its China business?"
    )
    
    print("\n--- INITIAL SUMMARY ---")
    print(summary)
    
    # Tighten the summary using professional equity analyst tone
    print("\nTightening summary with professional equity analyst tone...")
    tightened_summary = tighten_llm_insight(summary)
    
    print("\n--- TIGHTENED SUMMARY ---")
    print(tightened_summary)
    
    # Save the analysis to a file
    analysis_dir = os.path.join("cache", "sec_analysis", ticker)
    os.makedirs(analysis_dir, exist_ok=True)
    
    filing_date = filing_data.get("filing_date", "unknown_date")
    analysis_filename = f"{ticker}_{form_type}_{filing_date}_analysis.txt"
    analysis_path = os.path.join(analysis_dir, analysis_filename)
    
    with open(analysis_path, "w", encoding="utf-8") as f:
        f.write(f"Analysis of {ticker} {form_type} filed on {filing_date}\n\n")
        f.write("KEYWORDS ANALYZED:\n")
        f.write(", ".join(keywords) + "\n\n")
        f.write("TIGHTENED ANALYSIS:\n")
        f.write(tightened_summary)
    
    print(f"\nAnalysis saved to: {analysis_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 