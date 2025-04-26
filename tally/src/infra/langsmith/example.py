"""Example usage of LangSmith integration.

This module demonstrates how to use the LangSmith logging and tracing utilities.
"""
from typing import Any

from .logging import get_langsmith_logger, traceable_with_metadata


@traceable_with_metadata(component="example", version="1.0")
def process_prompt(prompt: str) -> str:
    """Process a prompt and return a response.
    
    This is an example function that demonstrates how to use LangSmith
    tracing and logging.
    
    Args:
        prompt: The input prompt
        
    Returns:
        str: The processed response
    """
    logger = get_langsmith_logger()
    
    # Add some metadata about the processing
    logger.update_metadata(
        prompt_length=len(prompt),
        processing_time_ms=100,  # Example metric
    )
    
    # Process the prompt (example implementation)
    response = f"Processed: {prompt}"
    
    # Log the prompt and response
    logger.log_prompt(
        prompt=prompt,
        response=response,
        metadata={"additional_info": "example"},
        tags=["example", "demo"],
    )
    
    return response


def main() -> None:
    """Run the example."""
    # Example usage
    result = process_prompt("Hello, world!")
    print(f"Result: {result}")


if __name__ == "__main__":
    main() 