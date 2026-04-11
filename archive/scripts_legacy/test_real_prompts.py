# Quick smoke test — sends 2 prompts from each category to GPT and evaluates responses
# Uses the spike evaluator (not production evaluator.py) for lightweight local testing
# Run from project root: python scripts/test_real_prompts.py

import sys
import os

# Ensure both project root and scripts/ are on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from target import call_llm
from evaluator_spike import evaluate

from prompts.data_leakage import PROMPTS as DATA_LEAKAGE
from prompts.hallucination import PROMPTS as HALLUCINATION
from prompts.injections import PROMPTS as INJECTIONS
from prompts.jailbreaks import PROMPTS as JAILBREAKS
from prompts.role_play import PROMPTS as ROLE_PLAY

# Pick 2 prompts from each category
test_prompts = [
    ("data_leakage",  DATA_LEAKAGE[0]),
    ("data_leakage",  DATA_LEAKAGE[1]),
    ("hallucination", HALLUCINATION[0]),
    ("hallucination", HALLUCINATION[1]),
    ("injection",     INJECTIONS[0]),
    ("injection",     INJECTIONS[1]),
    ("jailbreak",     JAILBREAKS[0]),
    ("jailbreak",     JAILBREAKS[1]),
    ("role_play",     ROLE_PLAY[0]),
    ("role_play",     ROLE_PLAY[1]),
]

print("=== Real Prompt Test Against GPT ===\n")

results = {"passed": 0, "failed": 0, "inconclusive": 0}

for category, prompt in test_prompts:
    print(f"[{category.upper()}]")
    print(f"Prompt: {prompt}")

    response = call_llm(prompt)
    result = evaluate(response)

    print(f"Response: {response[:120]}...")
    print(f"Verdict:  passed={result['passed']} | {result['reason']}")
    print()

    if result["passed"] is True:
        results["passed"] += 1
    elif result["passed"] is False:
        results["failed"] += 1
    else:
        results["inconclusive"] += 1

print("=== Summary ===")
print(f"Passed (model refused):      {results['passed']}/10")
print(f"Failed (model complied):     {results['failed']}/10")
print(f"Inconclusive (no signal):    {results['inconclusive']}/10")
