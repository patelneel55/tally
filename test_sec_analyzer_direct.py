import os
import sys
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Add project root to Python path
sys.path.insert(0, ".")

# Import from the app
from ai_analyst.app.models.company import SECFiling, FilingType
from ai_analyst.app.services.sec_analyzer import SECFilingAnalyzer
from ai_analyst.app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

async def test_sec_analyzer_direct():
    """Test the SEC analyzer directly with a test filing"""
    try:
        # Create a sample filing
        test_filing = SECFiling(
            symbol="AAPL",
            filing_type=FilingType.FORM_10K,
            filing_date=datetime(2022, 10, 28),
            filing_id="0000320193-22-000108",
            document_url="https://www.sec.gov/Archives/edgar/data/320193/000032019322000108/aapl-20220924.htm",
            filing_url="https://www.sec.gov/Archives/edgar/data/320193/000032019322000108/0000320193-22-000108-index.htm",
            company_name="APPLE INC"
        )
        
        logger.info(f"Testing SEC analyzer with filing: {test_filing.filing_id} for {test_filing.symbol}")
        
        # Create a test PDF file
        test_pdf_dir = Path("cache/test_pdf")
        test_pdf_dir.mkdir(parents=True, exist_ok=True)
        test_pdf_path = test_pdf_dir / "test_filing.txt"
        
        # Write sample content
        with open(test_pdf_path, "w") as f:
            f.write("APPLE INC\n")
            f.write("FORM 10-K\n")
            f.write("For the fiscal year ended September 24, 2022\n\n")
            f.write("Item 1. Business\n")
            f.write("Apple Inc. designs, manufactures and markets smartphones, personal computers, tablets, wearables and accessories.\n")
            f.write("The Company's products include iPhone, Mac, iPad and wearables, home and accessories.\n\n")
            f.write("Item 7. Management's Discussion and Analysis of Financial Condition and Results of Operations\n")
            f.write("The Company's net sales increased during 2022 compared to the same period in 2021 due to growth across all product categories.\n")
            f.write("Total revenue: $394.3 billion\n")
            f.write("Net income: $99.8 billion\n")
            f.write("Earnings per share: $6.11\n\n")
            f.write("Item 1A. Risk Factors\n")
            f.write("The Company's business, reputation, results of operations and financial condition depend on its ability to maintain customer trust.\n")
        
        logger.info(f"Created test PDF file at: {test_pdf_path}")
        
        # Create analyzer instance and test
        analyzer = SECFilingAnalyzer()
        logger.info(f"Created analyzer instance with OpenAI client: {analyzer.openai_client is not None}")
        
        # Run the analysis directly using internal method
        logger.info("Testing _analyze_with_ai method directly...")
        analysis_result = await analyzer._analyze_with_ai(test_filing, test_pdf_path)
        
        if analysis_result:
            logger.info(f"Analysis successful: {analysis_result.summary[:100]}...")
            logger.info(f"Analysis sections: {list(analysis_result.analysis.keys())}")
            return True
        else:
            logger.error("Analysis failed with None result")
            return False
            
    except Exception as e:
        logger.exception(f"Error during direct SEC analyzer test: {e}")
        return False

async def main():
    logger.info("Starting direct SEC analyzer test...")
    result = await test_sec_analyzer_direct()
    status = "PASSED" if result else "FAILED"
    logger.info(f"Direct SEC analyzer test {status}")

if __name__ == "__main__":
    asyncio.run(main()) 