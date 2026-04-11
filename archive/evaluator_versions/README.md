# Evaluator Versions

Each file is a self-contained iteration of the evaluator logic.
Run any version directly with `python evaluator_versions/evaluator_vX.py`.

| Version | Strategy | Real GPT Results | Key Limitation |
|---------|----------|------------------|----------------|
| v1 | Fixed keyword lists (failure + refusal signals) | 2 passed, 1 failed, 7 inconclusive | GPT silently ignores attacks — no keyword emitted. 0% hallucination detection. |
| v2 | Expanded signals + silent ignore detection + hallucination hedging heuristic | 4 passed, 1 failed, 5 inconclusive | Hallucination still 0% reliable. Some role_play responses still inconclusive. |
| v3 | LLM-as-judge — judge LLM reads full response and classifies by meaning | pending first run | Judge adds cost (1 extra API call per prompt). Judge can be wrong. |

## Naming convention
`evaluator_vN.py` — increment N for each new iteration.
Each file has a header block summarising: strategy, test results, and known limitations.
