import os
import sys
import json
import logging
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from openai import AsyncOpenAI

# Set up logging to console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

async def test_openai_vision_api():
    """
    Test OpenAI's vision API with a sample PDF to simulate SEC filing analysis
    """
    try:
        # Get API key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("No OpenAI API key found in environment variables")
            return False
        
        logger.info(f"Testing OpenAI API with key: {api_key[:8]}...")
        
        # Initialize OpenAI client
        client = AsyncOpenAI(api_key=api_key)
        
        # Path to a test PDF - create a small test file if none exists
        test_pdf_path = Path("test_document.txt")
        if not test_pdf_path.exists():
            with open(test_pdf_path, "w") as f:
                f.write("This is a test document for OpenAI analysis.\n")
                f.write("It simulates a very basic SEC filing.\n")
                f.write("Revenue: $100 million\n")
                f.write("Net Income: $25 million\n")
        
        logger.info(f"Using test document: {test_pdf_path}")
        
        # Read test document
        with open(test_pdf_path, "r") as f:
            document_text = f.read()
        
        # Create analysis prompt
        prompt = """
        You are a financial analyst. Analyze this document and extract:
        1. Revenue
        2. Net Income
        
        Provide your analysis in a structured format.
        """
        
        # Send request to OpenAI
        logger.info("Sending request to OpenAI API...")
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a financial analyst."},
                {"role": "user", "content": f"{prompt}\n\nDocument:\n{document_text}"}
            ],
            temperature=0.2,
            max_tokens=1000
        )
        
        analysis_text = response.choices[0].message.content
        logger.info(f"OpenAI API response: {analysis_text}")
        
        # Try to parse the response
        try:
            # Create a simple structure with the sections
            sections = {}
            for line in analysis_text.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    sections[key.strip()] = value.strip()
            
            logger.info(f"Parsed sections: {sections}")
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
        
        return True
    except Exception as e:
        logger.error(f"Error testing OpenAI API: {e}")
        return False

async def check_cache_directories():
    """Check if cache directories exist and are writable"""
    try:
        # Check common cache directories
        cache_dirs = [
            Path("cache"),
            Path("cache/sec_analysis"),
            Path("cache/sec_filings")
        ]
        
        for directory in cache_dirs:
            if directory.exists():
                logger.info(f"Cache directory exists: {directory}")
                # Check if writable
                try:
                    test_file = directory / "test_write.tmp"
                    with open(test_file, "w") as f:
                        f.write("test")
                    test_file.unlink()  # Remove test file
                    logger.info(f"Cache directory is writable: {directory}")
                except Exception as e:
                    logger.error(f"Cache directory is not writable: {directory}, error: {e}")
            else:
                logger.warning(f"Cache directory does not exist: {directory}")
                # Try to create it
                try:
                    directory.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Created cache directory: {directory}")
                except Exception as e:
                    logger.error(f"Failed to create cache directory: {directory}, error: {e}")
        
        return True
    except Exception as e:
        logger.error(f"Error checking cache directories: {e}")
        return False

async def main():
    logger.info("Starting simplified SEC analyzer debug test...")
    
    # Check cache directories
    logger.info("Checking cache directories...")
    await check_cache_directories()
    
    # Test OpenAI API
    logger.info("Testing OpenAI API for document analysis...")
    await test_openai_vision_api()
    
    logger.info("Debug test completed")

if __name__ == "__main__":
    asyncio.run(main()) 