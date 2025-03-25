"""
Pfizer 10-K Keyword Analysis Test

This script tests the functionality of analyzing Pfizer's SEC filing:
1. Downloads Pfizer's latest 10-K filing using SEC API
2. Extracts text from the PDF
3. Searches for pharmaceuticals and healthcare-specific keywords
4. Generates a summary of the findings using GPT-4
5. Tightens the summary using a professional equity analyst tone
"""

import os
import sys
import time
import requests
from pathlib import Path

# Add the parent directory to the path to allow importing from tools
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the required functions
from tools.get_sec_filing import get_sec_filing
from tools.sec_preprocessor import extract_text_from_pdf
from tools.sec_keyword_searcher import search_filing_for_keywords
from tools.analyze_keyword_matches import summarize_keyword_matches
from tools.tighten_llm_insight import tighten_llm_insight


def download_pdf(url, save_path):
    """Download a PDF file from URL and save it to the specified path."""
    try:
        response = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        response.raise_for_status()
        
        with open(save_path, 'wb') as f:
            f.write(response.content)
        
        return True
    except Exception as e:
        print(f"Error downloading PDF: {str(e)}")
        return False


def format_pages_for_search(text_pages):
    """Format raw text pages into the structure expected by search_filing_for_keywords."""
    formatted_pages = []
    for i, text in enumerate(text_pages):
        formatted_pages.append({
            "page": i + 1,  # 1-indexed page numbers
            "text": text
        })
    return formatted_pages


def main():
    """Test summarizing keyword matches from a Pfizer 10-K filing using GPT-4."""
    ticker = "PFE"
    form_type = "10-K"
    
    # Create cache directory for PFE if it doesn't exist
    cache_dir = Path(f"cache/sec_filings/{ticker}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Known Pfizer 10-K information (2022, filed in February 2023)
    pdf_filename = f"{ticker}_FilingType.FORM_{form_type}_2023-02-23.pdf"
    pdf_path = cache_dir / pdf_filename
    
    # If PDF doesn't exist, download it from a direct SEC URL
    if not pdf_path.exists():
        print(f"Pfizer 10-K not found. Downloading from SEC...")
        
        # Direct URL to Pfizer's 2022 10-K (filed Feb 2023)
        # This is the SEC.gov URL for Pfizer's 10-K
        sec_url = "https://www.sec.gov/Archives/edgar/data/78003/000007800323000018/pfe-20221231.htm"
        
        print(f"Getting filing information for {ticker}...")
        
        # Attempt to get the filing using the API
        filing_result = get_sec_filing(ticker, form_type)
        
        if "error" in filing_result and filing_result["error"]:
            print(f"Warning: API retrieval error: {filing_result['error']}")
            print("Falling back to direct download method...")
            
            # Direct download URL for PDF (note: in production, you'd get this from SEC API)
            # For the test, we'll use a placeholder URL that should be replaced with actual URL
            pdf_url = "https://www.sec.gov/ix?doc=/Archives/edgar/data/78003/000007800323000018/pfe-20221231.htm"
            
            print(f"Manually downloading from {pdf_url}")
            success = download_pdf(pdf_url, pdf_path)
            
            if not success:
                print("Direct download failed. Please manually download the Pfizer 10-K PDF.")
                print(f"1. Visit: {sec_url}")
                print(f"2. Download the PDF and save it to: {pdf_path}")
                print("3. Run this script again once the PDF is in place.")
                return 1
        else:
            # Success getting the filing, save relevant information
            filing_date = filing_result.get("filing_date", "2023-02-23")  # Default if not found
            filing_text = filing_result.get("filing_text", "")
            
            # Since get_sec_filing returns text, we'd need to convert to PDF
            # For this test, we'll output the text to a PDF-named file
            if filing_text:
                pdf_filename = f"{ticker}_FilingType.FORM_{form_type}_{filing_date}.pdf"
                pdf_path = cache_dir / pdf_filename
                
                # For demonstration, just save as PDF (would need a HTML-to-PDF converter in production)
                # This will create a text file with a .pdf extension
                with open(pdf_path, 'w', encoding='utf-8') as f:
                    f.write(filing_text)
                
                print(f"Created text file mimicking PDF at: {pdf_path}")
                print("Note: In production, you would convert HTML/text to actual PDF format.")
    else:
        print(f"Found existing Pfizer 10-K: {pdf_path}")
    
    # Verify the file exists
    if not pdf_path.exists():
        print(f"Error: File {pdf_path} not found after attempted download.")
        print("Please manually download the Pfizer 10-K PDF and place it at the specified path.")
        return 1
    
    print(f"Processing file: {pdf_path}")
    print("Extracting text from pages...")
    
    # Extract text from the PDF or text file
    try:
        raw_pages = extract_text_from_pdf(str(pdf_path))
        pages = format_pages_for_search(raw_pages)
        print(f"Successfully extracted text from {len(pages)} pages.")
    except Exception as e:
        print(f"Error extracting text: {str(e)}")
        print("Attempting to read as text file instead...")
        
        try:
            with open(pdf_path, 'r', encoding='utf-8') as f:
                text = f.read()
            
            # Simulate pages by splitting text (every 3000 chars)
            text_chunks = [text[i:i+3000] for i in range(0, len(text), 3000)]
            pages = format_pages_for_search(text_chunks)
            print(f"Read text file and created {len(pages)} simulated pages.")
        except Exception as e2:
            print(f"Error reading as text file: {str(e2)}")
            return 1
    
    # Pfizer-specific keywords related to pharmaceuticals and healthcare
    keywords = [
        "revenue",
        "Comirnaty", 
        "Paxlovid",
        "vaccines",
        "R&D",
        "pipeline",
        "drug development",
        "clinical trials",
        "patents",
        "mRNA",
        "competition",
        "profit margin",
        "regulatory approval",
        "FDA"
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
        original_query="What does the filing reveal about Pfizer's revenue drivers, COVID-19 product performance, R&D pipeline, and key risks?"
    )
    
    print("\n--- INITIAL SUMMARY ---")
    print(summary)
    
    # Tighten the summary using professional equity analyst tone
    print("\nTightening summary with professional equity analyst tone...")
    tightened_summary = tighten_llm_insight(summary)
    
    print("\n--- TIGHTENED SUMMARY ---")
    print(tightened_summary)
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 