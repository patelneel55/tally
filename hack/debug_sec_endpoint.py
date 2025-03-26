import os
import sys
import json
import logging
import asyncio
import httpx
import argparse
from dotenv import load_dotenv
from urllib.parse import quote

# Set up logging to console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Parse command line arguments
parser = argparse.ArgumentParser(description="Test SEC API endpoints")
parser.add_argument("--symbol", type=str, default="GS", help="Company symbol to test with (default: GS)")
args = parser.parse_args()

async def test_sec_analysis_endpoint(symbol):
    """
    Test the SEC analysis endpoint directly with API requests
    """
    # Base URL for the API
    base_url = "http://localhost:8000"
    
    # Test different endpoints
    endpoints = [
        f"/api/v1/sec/{symbol}/analyze",  # Latest filing analysis
        # f"/api/v1/sec/{symbol}/analyze?filing_type=10-K",  # Latest 10-K analysis
        # f"/api/v1/sec/{symbol}/analyze/0000886982-22-000017"  # Specific filing analysis
    ]
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        for endpoint in endpoints:
            url = f"{base_url}{endpoint}"
            logger.info(f"Testing endpoint: {url}")
            
            try:
                # Make the request
                response = await client.get(url)
                
                # Log the response status
                logger.info(f"Response status: {response.status_code}")
                
                # If successful, log the response content
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Response data summary:")
                    logger.info(f"  Symbol: {data.get('symbol')}")
                    logger.info(f"  Filing Type: {data.get('filing_type')}")
                    logger.info(f"  Filing Date: {data.get('filing_date')}")
                    logger.info(f"  Summary: {data.get('summary', '')[:100]}...")
                    
                    # Check if analysis is null/empty
                    analysis = data.get('analysis', {})
                    if not analysis:
                        logger.error("Analysis is empty or null!")
                    else:
                        logger.info(f"  Analysis sections: {list(analysis.keys())}")
                    
                    # Save the complete response to a file
                    filename = f"sec_analysis_response_{symbol}_{endpoint.split('/')[-1]}.json"
                    with open(filename, "w") as f:
                        json.dump(data, f, indent=2)
                    logger.info(f"Saved complete response to {filename}")
                else:
                    # If failed, log the error content
                    logger.error(f"Error response: {response.text}")
            except Exception as e:
                logger.error(f"Error testing endpoint {url}: {e}")

async def test_other_endpoints(symbol):
    """
    Test other API endpoints to compare behavior
    """
    # Base URL for the API
    base_url = "http://localhost:8000"
    
    # Test different endpoints
    endpoints = [
        f"/api/v1/company/{symbol}/profile",  # Company profile
        f"/api/v1/sec-data/{symbol}/filings",  # Updated SEC filings endpoint
        f"/api/v1/sec/{symbol}/filings",  # Old SEC filings endpoint (should redirect with notice)
        f"/api/v1/financial-modeling/{symbol}/quick-model"  # Financial modeling
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for endpoint in endpoints:
            url = f"{base_url}{endpoint}"
            logger.info(f"Testing endpoint: {url}")
            
            try:
                # Make the request
                response = await client.get(url)
                
                # Log the response status
                logger.info(f"Response status: {response.status_code}")
                
                # If successful, log a summary of the response
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Response keys: {list(data.keys() if isinstance(data, dict) else ['array'])}")
                    
                    # Check if this is the SEC filings endpoint (new or old)
                    if "filings" in endpoint:
                        if "filings" in data and isinstance(data["filings"], list):
                            logger.info(f"SEC Filings count: {len(data['filings'])}")
                            if data["filings"] and len(data["filings"]) > 0:
                                logger.info(f"First filing: {data['filings'][0]}")
                        
                        # Check if this contains a notice about endpoint change
                        if "notice" in data:
                            logger.info(f"Notice: {data['notice']}")
                    
                    # Save the complete response to a file
                    endpoint_name = endpoint.split('/')[-1]
                    filename = f"api_response_{symbol}_{endpoint_name}.json"
                    with open(filename, "w") as f:
                        json.dump(data, f, indent=2)
                    logger.info(f"Saved complete response to {filename}")
                else:
                    # If failed, log the error content
                    logger.error(f"Error response: {response.text}")
            except Exception as e:
                logger.error(f"Error testing endpoint {url}: {e}")

async def inspect_running_server():
    """
    Check if the server is running and get process info
    """
    try:
        # Get process info
        logger.info("Checking for running server instances:")
        os.system("ps aux | grep -i 'python -m .app.main' | grep -v grep")
        
        # Try a basic connection
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/api/v1")
            logger.info(f"Server root endpoint response: {response.status_code}")
            if response.status_code == 200:
                logger.info(f"Server info: {response.json()}")
    except Exception as e:
        logger.error(f"Error checking server: {e}")

async def main():
    symbol = args.symbol
    logger.info(f"Starting SEC analysis endpoint debug test for symbol: {symbol}...")
    
    # Check if server is running
    await inspect_running_server()
    
    # Test other endpoints first
    logger.info(f"Testing other API endpoints for {symbol}...")
    await test_other_endpoints(symbol)
    
    # Test SEC analysis endpoint
    logger.info(f"Testing SEC analysis endpoint for {symbol}...")
    await test_sec_analysis_endpoint(symbol)
    
    logger.info("Debug test completed")

if __name__ == "__main__":
    asyncio.run(main()) 