import os

def get_sec_api_key() -> str:
    """
    Get the SEC API key from environment variables.
    
    Returns:
        The SEC API key as a string
        
    Raises:
        ValueError: If SEC_API_KEY is not set in environment variables
    """
    key = os.getenv("SEC_API_KEY")
    if not key:
        raise ValueError("SEC_API_KEY is not set in environment variables.")
    return key 