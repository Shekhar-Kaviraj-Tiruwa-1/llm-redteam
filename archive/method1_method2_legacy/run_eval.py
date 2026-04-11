# Main evaluation runner — wires target, evaluator, and database together
# Usage: python run_eval.py --target gpt-3.5-turbo --evaluator keyword --limit 10

import argparse
import json
import uuid
import os
from datetime import datetime

from target import call_llm
from database import init_db, save_result

from prompts.data_leakage import PROMPTS as DATA_LEAKAGE, CATEGORY as CAT_DL
from prompts.hallucination import PROMPTS as HALLUCINATION, CATEGORY as CAT_HL
from prompts.injections import PROMPTS as INJECTIONS, CATEGORY as CAT_INJ
from prompts.jailbreaks import PROMPTS as JAILBREAKS, CATEGORY as CAT_JB
from prompts.role_play import PROMPTS as ROLE_PLAY, CATEGORY as CAT_RP

# All prompts paired with their category label
ALL_PROMPTS = (
    [(CAT_DL,  p) for p in DATA_LEAKAGE] +
    [(CAT_HL,  p) for p in HALLUCINATION] +
    [(CAT_INJ, p) for p in INJECTIONS] +
    [(CAT_JB,  p) for p in JAILBREAKS] +
    [(CAT_RP,  p) for p in ROLE_PLAY]
)


def parse_args():
    parser = argparse.ArgumentParser(description="Run adversarial evaluation against an LLM")
    parser.add_argument("--target",    default="gpt-3.5-turbo", help="Model to test (default: gpt-3.5-turbo)")
    parser.add_argument("--evaluator", default="keyword", choices=["keyword", "llm"],
                        help="Evaluation strategy: 'keyword' (v2, fast) or 'llm' (v3, semantic). Default: keyword")
    parser.add_argument("--limit",     type=int, default=None, help="Max prompts to run (default: all)")
    parser.add_argument("--output",    default=None,           help="JSONL output path (default: experiments/YYMMDD_<model>/results.jsonl)")
    return parser.parse_args()


def load_evaluator(name: str):
    """Return the evaluate function for the chosen strategy."""
    if name == "llm":
        from evaluator_llm import evaluate
    else:
        from evaluator import evaluate
    return evaluate


def make_output_path(model: str) -> str:
    """Build a timestamped output path inside experiments/."""
    date_str   = datetime.now().strftime("%y%m%d")
    model_slug = model.replace("/", "-")
    folder     = os.path.join("experiments", f"{date_str}_{model_slug}")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "results.jsonl")


def run(args):
    """Run the full evaluation pipeline."""
    init_db()

    evaluate     = load_evaluator(args.evaluator)
    run_id       = str(uuid.uuid4())[:8]
    prompts      = ALL_PROMPTS[:args.limit] if args.limit else ALL_PROMPTS
    output_path  = args.output or make_output_path(args.target)

    print(f"\n=== Red Team Eval ===")
    print(f"Run ID    : {run_id}")
    print(f"Model     : {args.target}")
    print(f"Evaluator : {args.evaluator}")
    print(f"Prompts   : {len(prompts)}")
    print(f"Output    : {output_path}")
    print()

    counts = {"passed": 0, "failed": 0, "inconclusive": 0}

    with open(output_path, "w") as f:
        for i, (category, prompt_text) in enumerate(prompts, 1):
            print(f"[{i}/{len(prompts)}] {category} — {prompt_text[:60]}...")

            response = call_llm(prompt_text, model=args.target)
            result   = evaluate(response, category=category, prompt_text=prompt_text)

            passed = result["passed"]
            reason = result["reason"]

            save_result(
                run_id         = run_id,
                category       = category,
                prompt_text    = prompt_text,
                response       = response,
                passed         = None if passed is None else int(passed),
                reason         = reason,
                model          = args.target,
                evaluator_type = args.evaluator,
            )

            record = {
                "prompt_id":      i,
                "run_id":         run_id,
                "category":       category,
                "prompt_text":    prompt_text,
                "response":       response,
                "passed":         passed,
                "reason":         reason,
                "model":          args.target,
                "evaluator_type": args.evaluator,
            }
            f.write(json.dumps(record) + "\n")

            if passed is True:
                counts["passed"] += 1
            elif passed is False:
                counts["failed"] += 1
            else:
                counts["inconclusive"] += 1

            verdict = "PASS" if passed is True else ("FAIL" if passed is False else "????")
            print(f"         {verdict} — {reason}")

    total = len(prompts)
    print(f"\n=== Summary (run_id: {run_id}) ===")
    print(f"Passed (safe):       {counts['passed']}/{total}")
    print(f"Failed (unsafe):     {counts['failed']}/{total}")
    print(f"Inconclusive:        {counts['inconclusive']}/{total}")
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    run(parse_args())
