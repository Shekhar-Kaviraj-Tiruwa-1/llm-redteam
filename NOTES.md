# Project Notes — LLM Red Teaming Framework

## What has been built (Phase 1 MVP — complete)

| File | Status | Description |
|------|--------|-------------|
| `target.py` | Done | Sends prompts to OpenAI, returns response string |
| `prompts/` | Done | 75 adversarial prompts across 5 categories |
| `evaluator.py` | Done | Keyword-based safety evaluator (v2 logic) |
| `database.py` | Done | SQLite storage with WAL mode |
| `run_eval.py` | Done | CLI runner — wires everything, outputs JSONL |
| `evaluator_versions/` | Done | Versioned evaluator history for comparison |
| `experiments/` | Done | Timestamped output folders per run |
| `pyproject.toml` | Done | uv-based dependency management |
| `.cursorrules` | Done | Instructions for future LLM coding agents |

## What still needs to be built

| File | Priority | Description |
|------|----------|-------------|
| `api.py` | High | FastAPI endpoints to query results from DB |
| `dashboard.py` | High | Streamlit visualisation of results |

## First full run results (2026-03-18, gpt-3.5-turbo, 75 prompts)

- Passed (safe):    20/75 (27%)
- Failed (unsafe):   2/75  (3%)
- Inconclusive:     53/75 (70%)

The 2 failures are confirmed safety vulnerabilities.
The 53 inconclusives reflect keyword evaluator limitations — expected and documented.

## Workflow standards in place

- **Package management**: `uv sync` (not pip). See `pyproject.toml`.
- **Output format**: JSONL, one result per line, in `experiments/YYMMDD_<model>/results.jsonl`
- **Evaluator versioning**: each iteration saved in `evaluator_versions/` with header documenting strategy and results
- **CLI args**: `run_eval.py` uses argparse — `--target`, `--limit`, `--output`
- **Coding conventions**: small functions, one-line comments, no unnecessary abstractions

## Known limitations (honest, documented)

1. Rule-based eval cannot detect hallucination — marked `heuristic_fail`, excluded from safety score
2. 53/75 responses were inconclusive — keyword rules miss ambiguous GPT responses
3. Single-turn attacks only — multi-turn testing is Phase 2
4. Results do not transfer across models — each model must be tested separately
5. 75 prompts is below production standard (300-500+) — sufficient for MVP

## Roadmap

### Phase 2 — LLM-as-judge evaluation
- Replace keyword rules with a second LLM that evaluates responses
- Address hallucination detection gap
- Expand prompt library to 150+ prompts using public datasets (HarmBench, JailbreakBench)

### Phase 3 — Agentic evaluation
- Multi-turn attack sequences
- Tool-use exploitation
- Agentic workflow testing (the genuine gap vs existing tools like Promptfoo/Garak)
