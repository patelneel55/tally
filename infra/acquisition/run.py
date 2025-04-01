import asyncio
import sys
import logging
from infra.acquisition.sec_fetcher import EDGARFetcher, FilingType, DataFormat

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # sys.exit(main())
    
    async def fetch_aapl_8k():
        """Fetch AAPL 8-K filings using the SEC fetcher."""
        logger.info("Fetching AAPL 8-K filings")
        
        try:
            # Initialize the fetcher
            fetcher = EDGARFetcher()
            
            # Fetch 8-K filings for Apple
            filings = await fetcher.fetch(
                identifier="GOOG",
                filing_type=FilingType.ANNUAL_REPORT,
                data_format=DataFormat.HTML
            )
            
            # Print the results
            logger.info(f"Found {len(filings)} 8-K filings for AAPL")
            for filing in filings:
                logger.info(f"Filing: {filing.formType} - {filing.filing_date} - {filing.accessionNo}")
                
            # Print filings in pretty JSON format
            import json
            print(json.dumps([filing.model_dump() for filing in filings], indent=2, default=str))
            return None
        except Exception as e:
            logger.error(f"Error fetching AAPL 8-K filings: {e}")
            raise
    
    # Run the fetch operation
    sys.exit(asyncio.run(fetch_aapl_8k()))