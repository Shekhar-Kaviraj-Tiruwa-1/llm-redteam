from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal


@dataclass
class EvalResult:
    verdict:   Literal["safe", "unsafe", "inconclusive"]
    score:     float   # 0.0 = definitely safe, 1.0 = definitely unsafe
    reasoning: str     # full evaluator output / chain-of-thought
    summary:   str     # one-line plain English explanation


class BaseEvaluator(ABC):
    """
    Plugin interface every evaluator must implement.

    To add a new evaluator:
      1. Subclass BaseEvaluator
      2. Set a unique `name` class attribute
      3. Implement `evaluate()`
      4. Register it in pipeline.py
    """

    name: str  # unique identifier shown in results (e.g. "keyword", "llamaguard", "llm_judge")

    @abstractmethod
    async def evaluate(
        self,
        prompt:    str,
        response:  str,
        category:  str | None = None,
    ) -> EvalResult:
        """
        Score a single (prompt, response) pair.

        Args:
            prompt:   The adversarial attack prompt sent to the target model.
            response: The target model's response.
            category: Attack category (e.g. "jailbreak"), if known.

        Returns:
            EvalResult with verdict, score, full reasoning, and one-line summary.
        """
        ...
