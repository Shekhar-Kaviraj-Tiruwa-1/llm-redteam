import os
import sys

# Import the legacy keyword evaluator from src/ (one level up from evaluators/)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import evaluator as _kw  # noqa: E402

from evaluators.base import BaseEvaluator, EvalResult

# Map the keyword evaluator's passed field to a 0–1 safety score.
# passed=True (safe)  → score 0.0   (no danger signal)
# passed=False (unsafe) → score 1.0 (compliance detected)
# passed=None (inconclusive) → score 0.5
_SCORE_MAP: dict = {True: 0.0, False: 1.0, None: 0.5}
_VERDICT_MAP: dict = {True: "safe", False: "unsafe", None: "inconclusive"}


class KeywordEvaluator(BaseEvaluator):
    """
    Wraps the existing keyword-based evaluator (evaluator.py v2) to match
    the plugin interface.  No logic is changed — this is a pure adapter.
    """

    name = "keyword"

    async def evaluate(
        self,
        prompt:   str,
        response: str,
        category: str | None = None,
    ) -> EvalResult:
        result  = _kw.evaluate(response, category=category, prompt_text=prompt)
        passed  = result["passed"]
        reason  = result["reason"]
        verdict = _VERDICT_MAP[passed]
        score   = _SCORE_MAP[passed]
        return EvalResult(
            verdict=verdict,
            score=score,
            reasoning=reason,
            summary=reason,
        )
