# Sends prompts to the OpenAI API and returns the response as a plain string

import openai
from dotenv import load_dotenv
import os

load_dotenv()


def call_llm(prompt, model="gpt-3.5-turbo"):
    """Send a prompt to an OpenAI model and return the response string."""
    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error calling LLM API: {e}")
        return ""


if __name__ == "__main__":
    result = call_llm("What is 2 + 2?")
    print(result)