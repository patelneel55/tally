"""
Simple SEC Filing Analysis Example
--------------------------------

This script demonstrates a basic real-world use case of the SEC filing analysis pipeline:
Analyzing a company's latest 10-K filing and extracting key insights.

Usage:
    python simple_sec_analysis.py
"""

import asyncio
import json
import logging
import os
from pathlib import Path

from app.services.sec_fetcher import sec_fetcher
from app.services.sec_analyzer import sec_filing_analyzer
from app.models.financial_statements import FilingType
from app.core.config import settings

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create output directory
output_dir = Path("analysis_results")
output_dir.mkdir(exist_ok=True)

async def analyze_company_filing():
    """
    Analyze the latest 10-K filing for Apple (AAPL).
    
    This demonstrates the complete pipeline:
    1. Fetch filing metadata from the SEC fetcher
    2. Download the filing as PDF using the SEC fetcher
    3. Analyze the filing using the SEC analyzer
    4. Extract and save key insights
    """
    # Company to analyze
    symbol = "AAPL"
    filing_type = FilingType.FORM_10K
    
    logger.info(f"Analyzing latest {filing_type} filing for {symbol}...")
    
    # Step 1: Fetch the latest filing metadata
    logger.info("Step 1: Fetching filing metadata...")
    filings_response = await sec_fetcher.get_sec_filings(
        symbol=symbol,
        filing_type=filing_type,
        limit=1
    )
    
    if not filings_response:
        logger.error(f"No response from sec_fetcher.get_sec_filings for {symbol}")
        return
    
    if not filings_response.filings:
        logger.error(f"No {filing_type} filings found for {symbol}")
        return
    
    filing = filings_response.filings[0]
    logger.info(f"Found filing from {filing.filing_date}: {filing.document_url}")
    
    # Step 2: Download the filing as PDF
    logger.info("Step 2: Downloading filing as PDF...")
    pdf_path = await sec_fetcher.get_filing_pdf(filing)
    
    if not pdf_path:
        logger.error(f"Failed to download PDF for {symbol}")
        return
    
    if not pdf_path.exists():
        logger.error(f"PDF file does not exist at path: {pdf_path}")
        return
    
    logger.info(f"PDF downloaded to: {pdf_path}")
    logger.info(f"File size: {pdf_path.stat().st_size / 1024:.1f} KB")
    
    # Step 3: Analyze the filing - Force fresh analysis by removing cache file
    logger.info("Step 3: Analyzing filing with AI (forcing fresh analysis)...")
    
    # Get the cache path and remove the file if it exists
    cache_dir = Path("cache/sec_analysis")
    cache_file = cache_dir / f"{filing.symbol}_{filing.filing_type}_{filing.filing_date.isoformat()}.json"
    
    if cache_file.exists():
        logger.info(f"Removing cached analysis file: {cache_file}")
        os.remove(cache_file)
    
    # Temporarily disable caching
    original_cache_setting = settings.ENABLE_CACHE
    settings.ENABLE_CACHE = False
    
    try:
        # Perform the analysis
        analysis_result = await sec_filing_analyzer.analyze_filing(filing)
        
        if not analysis_result:
            logger.error(f"Failed to analyze filing for {symbol}")
            return
        
        # Debug: Print the analysis result structure
        logger.info(f"Analysis result type: {type(analysis_result)}")
        logger.info(f"Analysis result attributes: {dir(analysis_result)}")
        logger.info(f"Summary length: {len(analysis_result.summary) if analysis_result.summary else 0}")
        logger.info(f"Analysis sections: {list(analysis_result.analysis.keys()) if analysis_result.analysis else []}")
        
        for section, content in analysis_result.analysis.items():
            logger.info(f"Section '{section}' length: {len(content) if content else 0}")
        
        # Step 4: Extract and save key insights
        logger.info("Step 4: Extracting and saving key insights...")
        
        # Create a more detailed result dictionary
        result = {
            "symbol": symbol,
            "filing_type": str(filing_type),
            "filing_date": filing.filing_date.isoformat(),
            "document_url": filing.document_url,
            "summary": analysis_result.summary,
            "analysis_date": analysis_result.analysis_date.isoformat(),
            "key_insights": {}
        }
        
        # Add each analysis section to the result
        for section, content in analysis_result.analysis.items():
            # Store the full content
            result["key_insights"][section] = content
        
        # Save the results
        output_file = output_dir / f"{symbol}_{filing_type}_{filing.filing_date.isoformat()}_fresh.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        logger.info(f"\nAnalysis completed! Results saved to: {output_file}")
        
        # Print a summary of the findings
        print("\nSummary of findings:")
        print("-" * 80)
        print(analysis_result.summary)
        
        if analysis_result.analysis.get("financial_metrics"):
            print("\nKey financial metrics:")
            print("-" * 80)
            print(analysis_result.analysis.get("financial_metrics")[:500] + "...")
        else:
            logger.warning("No financial metrics found in the analysis")
    
    finally:
        # Restore original cache setting
        settings.ENABLE_CACHE = original_cache_setting

if __name__ == "__main__":
    asyncio.run(analyze_company_filing()) 