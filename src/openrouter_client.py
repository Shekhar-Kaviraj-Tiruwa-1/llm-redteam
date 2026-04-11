import asyncio
import httpx
from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL

# Hard ceiling: any single API call that takes longer than this is cancelled.
# Keeps parallel runs from hanging on a single slow/dead request.
_TIMEOUT_SECONDS = 45


async def call_model(model: str, messages: list[dict], temperature: float = 0.7) -> str:
    """
    Call any model via OpenRouter's unified API.

    Args:
        model:       OpenRouter model string, e.g. "openai/gpt-4o-mini"
        messages:    OpenAI-format messages list
        temperature: Sampling temperature (use 0 for evaluators)

    Returns:
        Response content as a plain string.

    Raises:
        asyncio.TimeoutError: if the call exceeds _TIMEOUT_SECONDS
        httpx.HTTPStatusError: on non-2xx response
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":       model,
        "messages":    messages,
        "temperature": temperature,
    }
    # httpx timeout covers connect + read. asyncio.wait_for covers the whole
    # coroutine including any queue time, so a hanging connection can't block forever.
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
        resp = await asyncio.wait_for(
            client.post(OPENROUTER_BASE_URL, json=payload, headers=headers),
            timeout=_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
