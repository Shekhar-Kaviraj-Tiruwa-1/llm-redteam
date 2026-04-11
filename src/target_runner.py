"""
Sends a single prompt to the target model via OpenRouter and returns the response.
All model calls go through openrouter_client — no OpenAI SDK used here.
"""

from openrouter_client import call_model


async def get_response(prompt: str, model: str) -> str:
    """
    Send an adversarial prompt to the target model.

    Args:
        prompt: The attack prompt text.
        model:  OpenRouter model string, e.g. "openai/gpt-4o-mini"

    Returns:
        The model's response as a plain string.
        Returns an empty string on failure (caller handles it).
    """
    try:
        messages = [{"role": "user", "content": prompt}]
        return await call_model(model, messages, temperature=0.7)
    except Exception as e:
        print(f"  [target_runner] ERROR calling {model}: {e}")
        return ""
