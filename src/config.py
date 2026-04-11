import os
from dotenv import load_dotenv

# Load from project root .env (one level up from src/)
_root = os.path.join(os.path.dirname(__file__), "..")
load_dotenv(os.path.join(_root, ".env"))

OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1/chat/completions"

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

DEFAULT_TARGET_MODEL: str = "openai/gpt-4o-mini"
DEFAULT_JUDGE_MODEL: str  = "openai/gpt-4o-mini"
LLAMAGUARD_MODEL: str     = "meta-llama/llama-guard-3-8b"
