"""
Simple test script for the OpenAI API.
"""
import json
import os
from openai import OpenAI

# Initialize the OpenAI client with API key from environment
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def test_openai_call():
    """Test a simple call to the OpenAI API."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Return the following JSON: {\"test\": \"success\"}"}
            ],
            temperature=0
        )
        
        # Print the raw response
        print(f"Response content: {response.choices[0].message.content}")
        
        # Try to parse as JSON
        try:
            result = json.loads(response.choices[0].message.content)
            print(f"Parsed JSON: {result}")
        except json.JSONDecodeError:
            print("Response is not valid JSON")
            
        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False


if __name__ == "__main__":
    print("Testing OpenAI API call...")
    success = test_openai_call()
    print(f"Test completed. Success: {success}") 