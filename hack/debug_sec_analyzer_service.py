import os
import sys
import logging
import asyncio
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.insert(0, ".")

# Import from the app
from app.models.company import SECFiling, FilingType
from app.services.sec_analyzer import SECFilingAnalyzer, SECFilingAnalysisResult
from app.services.sec_fetcher import sec_filing_fetcher
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("sec_analyzer_debug.log")
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

async def test_sec_analyzer():
    """Test the SEC analyzer service with a real filing"""
    try:
        # Create a test filing
        test_filing = SECFiling(
            symbol="GS",
            filing_type=FilingType.FORM_10K,
            filing_date=datetime(2022, 2, 24),
            filing_id="0000886982-22-000017",
            document_url="https://www.sec.gov/Archives/edgar/data/886982/000088698222000017/gs-20211231.htm",
            filing_url="https://www.sec.gov/Archives/edgar/data/886982/000088698222000017/0000886982-22-000017-index.htm",
            company_name="GOLDMAN SACHS GROUP INC"
        )
        
        logger.info(f"Testing SEC analyzer with filing: {test_filing.filing_id} for {test_filing.symbol}")
        
        # Print OpenAI API key status
        api_key = os.getenv("OPENAI_API_KEY", "")
        logger.info(f"OpenAI API key present: {bool(api_key)}, first few chars: {api_key[:8] if api_key else 'None'}")
        
        # Check if API key is set in settings
        logger.info(f"OpenAI API key in settings: {bool(settings.OPENAI_API_KEY)}, first few chars: {settings.OPENAI_API_KEY[:8] if settings.OPENAI_API_KEY else 'None'}")
        
        # Create SEC analyzer instance
        analyzer = SECFilingAnalyzer()
        logger.info(f"Created SEC analyzer instance, OpenAI client initialized: {analyzer.openai_client is not None}")
        
        # Check cache directories
        cache_path = analyzer._get_cache_path(test_filing)
        logger.info(f"Cache path would be: {cache_path}")
        
        if cache_path.exists() and settings.ENABLE_CACHE:
            logger.info(f"Cache file exists, contents: {json.dumps(json.load(open(cache_path)))[:200]}...")
        else:
            logger.info(f"Cache file does not exist or caching disabled")
        
        # Test PDF fetching
        logger.info("Fetching SEC filing PDF...")
        pdf_path = await sec_filing_fetcher.get_filing_pdf(test_filing)
        
        if pdf_path:
            logger.info(f"Successfully fetched PDF: {pdf_path}, size: {pdf_path.stat().st_size / 1024:.2f} KB")
        else:
            logger.error("Failed to fetch PDF")
            return
        
        # Test analysis
        logger.info("Analyzing SEC filing with AI...")
        analysis_result = await analyzer.analyze_filing(test_filing)
        
        if analysis_result:
            logger.info(f"Successfully analyzed filing! Summary: {analysis_result.summary[:100]}...")
            logger.info(f"Analysis sections: {list(analysis_result.analysis.keys())}")
            
            # Save complete analysis to file for inspection
            with open("sec_analysis_debug_result.json", "w") as f:
                json.dump(analysis_result.to_dict(), f, indent=2, default=str)
            logger.info("Saved complete analysis to sec_analysis_debug_result.json")
        else:
            logger.error("Failed to analyze filing")
    
    except Exception as e:
        logger.exception(f"Error in SEC analyzer test: {e}")

async def main():
    logger.info("Starting SEC analyzer debug test...")
    await test_sec_analyzer()
    logger.info("SEC analyzer debug test completed")

if __name__ == "__main__":
    asyncio.run(main()) 