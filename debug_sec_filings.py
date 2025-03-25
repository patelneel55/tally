"""
Debug script for testing the SEC Filings endpoint
"""

import asyncio
import logging
import sys
from ai_analyst.app.services.sec_fetcher import sec_filing_fetcher

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

async def test_sec_filings():
    """Test the SEC filings endpoint directly."""
    try:
        # Test with Apple (AAPL)
        symbol = "AAPL"
        logger.info(f"Querying SEC filings for {symbol}")
        
        # Test _query_sec_filings method directly
        filings = await sec_filing_fetcher._query_sec_filings(
            symbol=symbol,
            form_type=None,  # Get all filing types
            limit=5
        )
        
        if filings:
            logger.info(f"Successfully retrieved {len(filings)} SEC filings for {symbol}")
            
            # Print the first filing details for debugging
            if len(filings) > 0:
                logger.info(f"First filing details: {filings[0]}")
        else:
            logger.error(f"No SEC filings found for {symbol} or API error occurred")
            
    except Exception as e:
        logger.error(f"Error testing SEC filings: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_sec_filings()) 