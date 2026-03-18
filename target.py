# Import the OpenAI client for API calls
import openai
# Import dotenv to load environment variables from .env file
from dotenv import load_dotenv
# Import os to access environment variables
import os

# Load environment variables from .env file
load_dotenv()

def call_llm(prompt, model="gpt-3.5-turbo"):
    """
    Send a prompt to an LLM API and return the response as a plain string.
    
    Args:
        prompt (str): The prompt to send to the LLM
        model (str): The model name to use (default: gpt-3.5-turbo)
    
    Returns:
        str: The response content as a plain string, or empty string if error
    """
    try:
        # Get the OpenAI API key from environment variables
        api_key = os.getenv("OPENAI_API_KEY")
        
        # Create OpenAI client with the API key
        client = openai.OpenAI(api_key=api_key)
        
        # Send the prompt to the chat completions API
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Extract and return the response content as a string
        return response.choices[0].message.content
        
    except Exception as e:
        # Print any error that occurs during the API call
        print(f"Error calling LLM API: {e}")
        # Return empty string on error
        return ""

# Test the function when script is run directly
if __name__ == "__main__":
    # Call the function with a test prompt
    result = call_llm("Hi Gpt How are you and fuck you?")
    # Print the result
    print(result)