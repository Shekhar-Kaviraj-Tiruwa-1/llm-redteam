"""
Iteration 3 pipeline — quad evaluator on every response.

For each prompt:
  1. Send to target model via OpenRouter
  2. Run keyword, LLaMA Guard, LLM judge, and OpenAI Moderation in parallel (asyncio.gather)
  3. Compute evaluator agreement
  4. Save to SQLite + write JSONL

Usage:
    # Run all 488 prompts against gpt-4o-mini
    python pipeline.py

    # Quick test: 10 prompts from custom set only
    python pipeline.py --limit 10 --sources custom

    # Custom target and judge
    python pipeline.py --target meta-llama/llama-3.1-8b-instruct --judge anthropic/claude-haiku-4-5

    # Filter to one attack category
    python pipeline.py --limit 20 --category jailbreak
"""

import argparse
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime

# Add src/ to path so sibling modules resolve correctly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DEFAULT_TARGET_MODEL, DEFAULT_JUDGE_MODEL
from target_runner import get_response
from evaluators.keyword import KeywordEvaluator
from evaluators.llamaguard import LlamaGuardEvaluator
from evaluators.llm_judge import LLMJudgeEvaluator
from evaluators.openai_moderation import OpenAIModerationEvaluator
from evaluators.base import EvalResult
from database import init_db, save_run, save_evaluation, get_run_summary


# ---------------------------------------------------------------------------
# Agreement logic
# ---------------------------------------------------------------------------

def _compute_agreement(
    kw: EvalResult, lg: EvalResult, lj: EvalResult, om: EvalResult
) -> tuple[str, str]:
    """
    Returns (agreement_label, disagreement_pattern) across four evaluators.

    agreement_label:
      "all_agree"    — all four verdicts identical
      "majority"     — three same, one differs
      "split"        — two pairs (2+2)
      "all_disagree" — all three possible verdicts present

    disagreement_pattern: e.g. "kw=safe|lg=unsafe|lj=safe|om=safe"
    """
    verdicts = [kw.verdict, lg.verdict, lj.verdict, om.verdict]
    pattern  = f"kw={kw.verdict}|lg={lg.verdict}|lj={lj.verdict}|om={om.verdict}"
    unique   = set(verdicts)

    if len(unique) == 1:
        label = "all_agree"
    elif len(unique) == 3:
        # All three possible verdicts present across 4 evaluators
        label = "all_disagree"
    else:
        # len(unique) == 2: either 3+1 (majority) or 2+2 (split)
        counts = [verdicts.count(v) for v in unique]
        label  = "majority" if max(counts) == 3 else "split"

    return label, pattern


# ---------------------------------------------------------------------------
# Output path
# ---------------------------------------------------------------------------

def _make_output_path(target_model: str) -> str:
    date_str   = datetime.now().strftime("%y%m%d")
    model_slug = target_model.replace("/", "-")
    folder     = os.path.join(os.path.dirname(__file__), "..", "experiments", f"method3_{model_slug}_{date_str}")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "results.jsonl")


# ---------------------------------------------------------------------------
# Core async pipeline
# ---------------------------------------------------------------------------

async def run_pipeline(args: argparse.Namespace) -> None:
    # Resolve prompt sources
    sources = [s.strip() for s in args.sources.split(",")]

    # Lazy import loader from prompts/ at project root
    _prompts_dir = os.path.join(os.path.dirname(__file__), "..", "prompts")
    sys.path.insert(0, _prompts_dir)
    from loader import load_prompts
    prompts = load_prompts(sources=sources, category=args.category or None)

    if args.limit:
        prompts = prompts[: args.limit]

    # Evaluators
    keyword    = KeywordEvaluator()
    llamaguard = LlamaGuardEvaluator()
    llm_judge  = LLMJudgeEvaluator(judge_model=args.judge)
    openai_mod = OpenAIModerationEvaluator()

    # DB + run metadata
    init_db()
    run_id = str(uuid.uuid4())[:8]
    save_run(run_id, args.target, args.judge, sources, len(prompts))

    output_path = args.output or _make_output_path(args.target)

    print(f"\n{'='*55}")
    print(f"  Iteration 3 — Quad Evaluator Pipeline")
    print(f"{'='*55}")
    print(f"  Run ID      : {run_id}")
    print(f"  Target      : {args.target}")
    print(f"  Judge       : {args.judge}")
    print(f"  Sources     : {', '.join(sources)}")
    print(f"  Prompts     : {len(prompts)}")
    print(f"  Output      : {output_path}")
    print(f"{'='*55}\n")

    # Concurrency: N prompts run in parallel, each making 4 API calls
    # (1 target + 3 evaluators). Default 10 → ~10x faster than sequential.
    sem       = asyncio.Semaphore(args.concurrency)
    lock      = asyncio.Lock()
    completed = 0
    counts = {
        "kw":  {"safe": 0, "unsafe": 0, "inconclusive": 0},
        "lg":  {"safe": 0, "unsafe": 0, "inconclusive": 0},
        "lj":  {"safe": 0, "unsafe": 0, "inconclusive": 0},
        "om":  {"safe": 0, "unsafe": 0, "inconclusive": 0},
        "agreement": {"all_agree": 0, "majority": 0, "split": 0, "all_disagree": 0},
    }

    async def process_one(i: int, prompt_dict: dict, f) -> None:
        nonlocal completed
        prompt_text = prompt_dict["text"]
        category    = prompt_dict["category"]
        source      = prompt_dict["source"]

        async with sem:
            response = await get_response(prompt_text, model=args.target)
            if not response:
                async with lock:
                    completed += 1
                    print(f"[{completed:>4}/{len(prompts)}] SKIP (empty response)")
                return

            kw_result, lg_result, lj_result, om_result = await asyncio.gather(
                keyword.evaluate(prompt_text, response, category),
                llamaguard.evaluate(prompt_text, response, category),
                llm_judge.evaluate(prompt_text, response, category),
                openai_mod.evaluate(prompt_text, response, category),
            )

        agreement, pattern = _compute_agreement(kw_result, lg_result, lj_result, om_result)

        async with lock:
            completed += 1
            counts["kw"][kw_result.verdict]  += 1
            counts["lg"][lg_result.verdict]  += 1
            counts["lj"][lj_result.verdict]  += 1
            counts["om"][om_result.verdict]  += 1
            counts["agreement"][agreement]   += 1

            save_evaluation(
                run_id=run_id, prompt_idx=i,
                prompt_text=prompt_text, category=category, source=source,
                response=response,
                kw_verdict=kw_result.verdict, kw_score=kw_result.score, kw_summary=kw_result.summary,
                lg_verdict=lg_result.verdict, lg_score=lg_result.score, lg_summary=lg_result.summary,
                lj_verdict=lj_result.verdict, lj_score=lj_result.score,
                lj_reasoning=lj_result.reasoning, lj_summary=lj_result.summary,
                om_verdict=om_result.verdict, om_score=om_result.score, om_summary=om_result.summary,
                agreement=agreement, disagreement_pattern=pattern,
            )

            record = {
                "prompt_idx": i, "run_id": run_id,
                "prompt_text": prompt_text, "category": category, "source": source,
                "response": response,
                "keyword":            {"verdict": kw_result.verdict, "score": kw_result.score, "summary": kw_result.summary},
                "llamaguard":         {"verdict": lg_result.verdict, "score": lg_result.score, "summary": lg_result.summary},
                "llm_judge":          {"verdict": lj_result.verdict, "score": lj_result.score, "summary": lj_result.summary},
                "openai_moderation":  {"verdict": om_result.verdict, "score": om_result.score, "summary": om_result.summary},
                "agreement":  agreement,
                "disagreement_pattern": pattern,
            }
            f.write(json.dumps(record) + "\n")
            f.flush()

            flag = "=" if agreement == "all_agree" else ("!" if agreement == "all_disagree" else "~")
            print(
                f"[{completed:>4}/{len(prompts)}] [{flag}] "
                f"kw={kw_result.verdict:<12} lg={lg_result.verdict:<12} "
                f"lj={lj_result.verdict:<12} om={om_result.verdict:<12}"
                f" | {source} / {category}"
            )

    with open(output_path, "w") as f:
        await asyncio.gather(*[process_one(i, p, f) for i, p in enumerate(prompts, 1)])

    # Final summary
    get_run_summary(run_id)
    print(f"\n{'='*55}")
    print(f"  Summary  (run_id: {run_id})")
    print(f"{'='*55}")
    print(f"  {'Evaluator':<20} {'safe':>8} {'unsafe':>8} {'inconclusive':>14}")
    print(f"  {'-'*52}")
    for name, key in [("keyword", "kw"), ("llamaguard", "lg"), ("llm_judge", "lj"), ("openai_mod", "om")]:
        c = counts[key]
        print(f"  {name:<20} {c['safe']:>8} {c['unsafe']:>8} {c['inconclusive']:>14}")
    print(f"\n  Agreement breakdown:")
    for label, n in counts["agreement"].items():
        pct = n / len(prompts) * 100 if prompts else 0
        print(f"    {label:<16} {n:>5}  ({pct:.1f}%)")
    print(f"\n  Results → {output_path}")
    print(f"{'='*55}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Iteration 3 — Triple Evaluator Pipeline")
    parser.add_argument(
        "--target",   default=DEFAULT_TARGET_MODEL,
        help=f"Target model via OpenRouter (default: {DEFAULT_TARGET_MODEL})"
    )
    parser.add_argument(
        "--judge",    default=DEFAULT_JUDGE_MODEL,
        help=f"LLM judge model via OpenRouter (default: {DEFAULT_JUDGE_MODEL})"
    )
    parser.add_argument(
        "--sources",  default="custom,strongreject,jailbreakbench",
        help='Comma-separated prompt sources (default: "custom,strongreject,jailbreakbench")'
    )
    parser.add_argument(
        "--category", default=None,
        help="Filter prompts to a single category (default: all)"
    )
    parser.add_argument(
        "--limit",    type=int, default=None,
        help="Max prompts to run (default: all)"
    )
    parser.add_argument(
        "--output",      default=None,
        help="JSONL output path (default: auto-generated in experiments/)"
    )
    parser.add_argument(
        "--concurrency", type=int, default=10,
        help="Number of prompts to process in parallel (default: 10)"
    )
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(run_pipeline(parse_args()))
