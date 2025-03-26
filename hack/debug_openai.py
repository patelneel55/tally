import os
import logging
from dotenv import load_dotenv
from openai import OpenAI
import asyncio
from openai import AsyncOpenAI

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

async def test_openai_async():
    """Test async OpenAI API connection"""
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY not found in environment variables")
            return False
            
        logger.info(f"Testing OpenAI API connection with key: {api_key[:8]}...")
        client = AsyncOpenAI(api_key=api_key)
        
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello, are you working?"}
            ],
            max_tokens=50
        )
        
        logger.info(f"OpenAI API response: {response.choices[0].message.content}")
        return True
    except Exception as e:
        logger.error(f"Error testing OpenAI API: {e}")
        return False

def test_openai_sync():
    """Test synchronous OpenAI API connection"""
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY not found in environment variables")
            return False
            
        logger.info(f"Testing OpenAI API connection with key: {api_key[:8]}...")
        client = OpenAI(api_key=api_key)
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello, are you working?"}
            ],
            max_tokens=50
        )
        
        logger.info(f"OpenAI API response: {response.choices[0].message.content}")
        return True
    except Exception as e:
        logger.error(f"Error testing OpenAI API: {e}")
        return False

async def main():
    logger.info("Testing OpenAI API connections...")
    
    # Test async client
    logger.info("Testing AsyncOpenAI client...")
    async_result = await test_openai_async()
    
    # Test sync client
    logger.info("Testing synchronous OpenAI client...")
    sync_result = test_openai_sync()
    
    if async_result and sync_result:
        logger.info("All OpenAI API tests passed successfully!")
    else:
        logger.error("Some OpenAI API tests failed. Check the logs for details.")

if __name__ == "__main__":
    asyncio.run(main()) 