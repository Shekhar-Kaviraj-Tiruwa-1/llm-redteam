# Experiments

Each evaluation run is saved in its own folder.

## Naming convention

```
experiments/YYMMDD_<model>/
    results.jsonl   ← one line per prompt result
```

Example: `experiments/260318_gpt-3.5-turbo/`

## JSONL format

Each line is a JSON object with these fields:

| Field | Type | Description |
|-------|------|-------------|
| `prompt_id` | int | Position in the prompt list (1-indexed) |
| `run_id` | str | Short unique ID for the run |
| `category` | str | Attack category (injection, jailbreak, etc.) |
| `prompt_text` | str | The exact prompt sent to the model |
| `response` | str | The model's full response |
| `passed` | bool or null | True=safe, False=unsafe, null=inconclusive |
| `failure_reason` | str or null | Why it failed (null if passed) |
| `model` | str | Model name used |

## How to run a new evaluation

```bash
# Full run (all 75 prompts)
python run_eval.py --target gpt-3.5-turbo

# Limited run for testing
python run_eval.py --target gpt-3.5-turbo --limit 10

# Custom output path
python run_eval.py --target gpt-4o --output experiments/my_run/results.jsonl
```
