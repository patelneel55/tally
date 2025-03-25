"""
Debug SEC Analyzer
-----------------

This script directly analyzes a SEC filing and prints the raw response
from the AI model to help diagnose issues with the analysis.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from datetime import date

from openai import AsyncOpenAI

from ai_analyst.app.services.sec_fetcher import sec_filing_fetcher
from ai_analyst.app.models.company import SECFiling, FilingType
from ai_analyst.app.core.config import settings

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create output directory
output_dir = Path("analysis_results")
output_dir.mkdir(exist_ok=True)

async def analyze_filing_directly():
    """
    Directly analyze a SEC filing using OpenAI and print the raw response.
    """
    # Create a test filing
    filing = SECFiling(
        symbol='AAPL',
        filing_type=FilingType.FORM_10K,
        filing_date=date(2023, 10, 27),
        document_url='https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm',
        filing_id='123456'
    )
    
    logger.info(f"Analyzing {filing.filing_type} filing for {filing.symbol} from {filing.filing_date}")
    
    # Step 1: Download the filing as PDF
    logger.info("Downloading filing as PDF...")
    pdf_path = await sec_filing_fetcher.get_filing_pdf(filing)
    
    if not pdf_path:
        logger.error("Failed to download PDF")
        return
    
    logger.info(f"PDF downloaded to: {pdf_path}")
    
    # Step 2: Initialize OpenAI client
    logger.info("Initializing OpenAI client...")
    openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    
    # Step 3: Upload the PDF file to OpenAI
    logger.info(f"Uploading PDF file to OpenAI: {pdf_path}")
    with open(pdf_path, 'rb') as file:
        file_response = await openai_client.files.create(
            file=file,
            purpose="user_data"
        )
        file_id = file_response.id
        logger.info(f"File uploaded successfully with ID: {file_id}")
    
    # Step 4: Create the analysis prompt
    prompt = """
    You are a financial analyst specializing in SEC filings analysis. 
    I'm providing you with the complete text of a 10-K annual report filing.
    
    Please analyze this filing and provide a comprehensive analysis with the following sections:
    
    1. EXECUTIVE SUMMARY: A brief overview of the company's performance and key highlights
    2. FINANCIAL METRICS: Key financial metrics and their trends
    3. RISK FACTORS: Major risks identified in the filing
    4. BUSINESS OPERATIONS: Overview of the company's business operations
    5. FUTURE OUTLOOK: The company's future plans and outlook
    
    Format your response with clear section headers in ALL CAPS followed by a colon.
    """
    
    # Step 5: Analyze the filing
    logger.info(f"Analyzing filing using file_id: {file_id}")
    response = await openai_client.chat.completions.create(
        model=settings.SEC_ANALYSIS_MODEL,
        messages=[
            {"role": "system", "content": "You are a financial analyst specializing in SEC filings analysis."},
            {"role": "user", "content": [
                {
                    "type": "file",
                    "file": {
                        "file_id": file_id
                    }
                },
                {
                    "type": "text", 
                    "text": prompt
                }
            ]}
        ],
        temperature=0.2,  # Low temperature for more factual responses
        max_tokens=settings.SEC_ANALYSIS_MAX_TOKENS
    )
    
    # Step 6: Get the raw response
    raw_response = response.choices[0].message.content
    
    # Step 7: Save the raw response to a file
    output_file = output_dir / f"{filing.symbol}_{filing.filing_type}_{filing.filing_date.isoformat()}_raw.txt"
    with open(output_file, 'w') as f:
        f.write(raw_response)
    
    logger.info(f"Raw response saved to: {output_file}")
    
    # Step 8: Print the first 1000 characters of the response
    print("\nFirst 1000 characters of the raw response:")
    print("-" * 80)
    print(raw_response[:1000])
    print("\n...")
    
    # Step 9: Try to parse the sections manually
    print("\nAttempting to parse sections manually:")
    print("-" * 80)
    
    sections = {}
    current_section = None
    current_content = []
    
    # Simple section parser - looks for capitalized headers
    for line in raw_response.split('\n'):
        # Check if this line is a section header (all caps with colon)
        if ':' in line and line.split(':')[0].isupper() and len(line.split(':')[0]) > 3:
            # If we were already building a section, save it
            if current_section:
                sections[current_section] = '\n'.join(current_content).strip()
                print(f"Found section: {current_section} ({len(sections[current_section])} chars)")
            
            # Start a new section
            parts = line.split(':', 1)
            current_section = parts[0].strip()
            current_content = [parts[1].strip()] if len(parts) > 1 and parts[1].strip() else []
        elif current_section:
            # Continue building the current section
            current_content.append(line)
    
    # Save the last section
    if current_section and current_content:
        sections[current_section] = '\n'.join(current_content).strip()
        print(f"Found section: {current_section} ({len(sections[current_section])} chars)")
    
    # Step 10: Save the parsed sections to a file
    output_file = output_dir / f"{filing.symbol}_{filing.filing_type}_{filing.filing_date.isoformat()}_parsed.json"
    with open(output_file, 'w') as f:
        json.dump(sections, f, indent=2)
    
    logger.info(f"Parsed sections saved to: {output_file}")
    
    # Print section names
    print(f"\nFound {len(sections)} sections: {list(sections.keys())}")

if __name__ == "__main__":
    asyncio.run(analyze_filing_directly()) 