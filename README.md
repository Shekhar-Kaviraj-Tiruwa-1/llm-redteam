# Can We Trust How We Measure AI Safety?
### An Empirical Study of Evaluator Disagreement in LLM Safety Testing

> Built for the **BlueDot Impact — Technical AI Safety Sprint** (April 2026)  
> Author: **Shekhar Tiruwa**

---

## The One-Line Finding

> **The same model responding to the same prompt was rated 0.4% unsafe by one evaluator and 31% unsafe by another.**  
> The choice of evaluator determines your safety score more than the model being tested.

---

## What This Project Is About

AI safety evaluation is how we decide whether a language model will comply with harmful requests. The field has a problem: **there is no agreed standard for which evaluation method to use**.

Researchers typically pick one method — keyword matching, a classifier, or an LLM-as-judge — and report results as if they were ground truth. But what if two researchers evaluated the same model with the same prompts using different methods and got completely different safety scores? Neither would be wrong about what their evaluator found. But neither would surface the more important question:

**How much does the evaluator itself determine the outcome?**

This project was built to answer that question empirically. It runs multiple evaluators simultaneously on every response, stores all verdicts side by side, and measures the disagreement.

---

## Key Results at a Glance

### Four evaluators. Same 488 responses. Completely different conclusions.

| Evaluator | Safe | Unsafe | Inconclusive |
|---|---|---|---|
| Keyword (published list) | 69.3% | 0.4% | 30.7% |
| LLaMA Guard 3 | 10.5% | **31.1%** | 58.6% |
| LLM Judge (StrongREJECT) | 95.1% | 1.7% | 3.5% |
| OpenAI Moderation API | 99.4% | 0.6% | 0.0% |

### The LLaMA Guard outlier is structural — not model-specific

Running the same pipeline against a second model confirmed the pattern is baked into LLaMA Guard's calibration, not GPT-4o-mini's behaviour:

| Evaluator | GPT-4o-mini unsafe | Claude 3.5 Haiku unsafe |
|---|---|---|
| LLaMA Guard 3 | 31.1% | 34.0% |
| LLM Judge | 1.7% | 0.5% |
| OpenAI Moderation | 0.6% | 0.3% |

### Evaluator agreement is rare

| Agreement | GPT-4o-mini | Claude 3.5 Haiku |
|---|---|---|
| All 4 agree | 7.6% | 0.5% |
| Majority (3+1) | 66.0% | 17.1% |
| Split (2+2) | 15.6% | 52.2% |
| All disagree | 10.9% | 30.1% |

---

## How It Was Built — Three Iterations

### Iteration 1 — Keyword Baseline (March 2026)

Built a keyword-based evaluator with signals for compliance, refusal, and silent ignore. Ran 75 custom adversarial prompts against GPT-3.5-turbo and GPT-4o-mini.

**Finding:** 59–70% inconclusive rate. Keyword matching is blind to silent refusals — GPT often refuses without emitting any keyword signal.

### Iteration 2 — Adding an LLM Judge (March 2026)

Added a second LLM to read the full response and classify by meaning. Ran both evaluators on the same 75 prompts and responses.

| Evaluator | Safe | Unsafe | Inconclusive |
|---|---|---|---|
| Keyword | 27% | 1% | 70% |
| LLM Judge | 75% | **24%** | 1% |

**Finding:** On identical data, the LLM judge found 24× more unsafe responses. Evaluator choice — not model behaviour — was driving the reported safety score.

### Iteration 3 — Triple (then Quad) Evaluator Pipeline (April 2026)

Built a concurrent pipeline running four evaluators simultaneously on every response across 488 prompts from three standardised datasets (custom, StrongREJECT, JailbreakBench). Results stored side by side in SQLite for disagreement analysis.

**New finding:** Three of four evaluators (Keyword, LLM Judge, OpenAI Moderation) converge on the same verdict. LLaMA Guard 3 is the structural outlier — its 31% unsafe rate holds regardless of which model is tested.

---

## Pipeline Architecture

```
Adversarial Prompt
       │
       ▼
  Target Model  ──────────────────────────────────────────────────────┐
  (via OpenRouter)                                                      │
                                                                        │ Response
       ┌────────────────────────────────────────────────────────────────┘
       │
       ▼ (all four run in parallel via asyncio.gather)
┌──────────────┐  ┌─────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│   Keyword    │  │  LLaMA Guard 3  │  │  LLM Judge           │  │  OpenAI Moderation   │
│  Evaluator   │  │  (via OpenRouter)│  │  (StrongREJECT +     │  │  (omni-moderation-   │
│  $0 / call   │  │  ~$0.01 / call  │  │   G-Eval CoT)        │  │   latest, free)      │
│              │  │                 │  │  ~$0.02 / call        │  │                      │
└──────┬───────┘  └────────┬────────┘  └──────────┬───────────┘  └──────────┬───────────┘
       │                   │                       │                          │
       └───────────────────┴───────────────────────┴──────────────────────────┘
                                          │
                                          ▼
                              Agreement computation
                         (all_agree / majority / split / all_disagree)
                                          │
                                          ▼
                              SQLite + JSONL storage
                                          │
                              ┌───────────┴───────────┐
                              │                       │
                         Streamlit               Research
                         Dashboard               Figures
```

### Evaluator design

| Evaluator | Method | Cost | Verdict space |
|---|---|---|---|
| **Keyword** | Zou et al. (2023) refusal string list + compliance signals | $0 | safe / unsafe / inconclusive |
| **LLaMA Guard 3** | Meta's 13-category safety classifier via OpenRouter | ~$0.01 | safe / unsafe / inconclusive |
| **LLM Judge** | StrongREJECT rubric + G-Eval chain-of-thought | ~$0.02 | safe / unsafe / inconclusive |
| **OpenAI Moderation** | `omni-moderation-latest` endpoint (13 harm categories) | Free | safe / unsafe |

### Datasets

| Source | Prompts | Description |
|---|---|---|
| Custom | 75 | 5 attack categories: data leakage, hallucination, prompt injection, jailbreak, role-play |
| StrongREJECT | 313 | Souly et al., NeurIPS 2024. 6 harm categories |
| JailbreakBench | 100 | Chao et al., NeurIPS 2024. Adversarially optimised attacks |
| **Total** | **488** | |

---

## Repository Structure

```
projects/
│
├── README.md                        ← you are here
├── RESEARCH_PROPOSAL.md             ← full research proposal with methodology
├── pyproject.toml                   ← dependencies (uv)
├── .env.example                     ← API key template
│
├── run_eval.py                      ← Iteration 1/2 CLI runner
├── evaluator.py                     ← Keyword evaluator (v2)
├── evaluator_llm.py                 ← LLM Judge (Iteration 2)
├── target.py                        ← Target model caller
├── database.py                      ← SQLite storage (Iteration 1/2)
├── api.py                           ← FastAPI results API
├── dashboard.py                     ← Streamlit dashboard (Iteration 1/2)
│
├── prompts/                         ← 75 custom adversarial prompts
│   ├── data_leakage.py
│   ├── hallucination.py
│   ├── injections.py
│   ├── jailbreaks.py
│   └── role_play.py
│
├── evaluator_versions/              ← Evaluator iteration history (v1 → v3)
│
└── experiments/iteration3/         ← Iteration 3 — Quad Evaluator Pipeline
    │
    ├── pipeline.py                  ← Main runner (concurrent, 15 parallel)
    ├── config.py                    ← Model constants, API key loading
    ├── openrouter_client.py         ← Unified API client (any model via OpenRouter)
    │
    ├── evaluator_base.py            ← Plugin interface (BaseEvaluator, EvalResult)
    ├── evaluator_keyword.py         ← Keyword evaluator (Zou et al. 2023 refusal list)
    ├── evaluator_llamaguard.py      ← LLaMA Guard 3 evaluator
    ├── evaluator_llm_judge.py       ← StrongREJECT + G-Eval CoT judge
    ├── evaluator_openai_moderation.py ← OpenAI Moderation API evaluator
    │
    ├── target_runner.py             ← Sends prompts to target model
    ├── database_v3.py               ← SQLite schema (all four verdicts + agreement)
    ├── dashboard_v3.py              ← Streamlit dashboard (comparison view)
    │
    ├── figures/                     ← Publication-quality figures (PNG + SVG, 300 DPI)
    │   ├── fig1_core_finding.png
    │   ├── fig2_cross_model.png
    │   ├── fig3_agreement.png
    │   ├── fig4_disagreement_patterns.png
    │   └── fig5_evaluator_gap.png
    │
    ├── generate_figures.py          ← Reproduces all figures from the database
    ├── RESULTS_REPORT.md            ← Full results writeup
    │
    └── prompts/
        ├── loader.py                ← Unified prompt loader (3 sources)
        ├── fetch_external.py        ← One-time dataset downloader
        ├── strongreject.jsonl       ← 313 prompts (cached)
        └── jailbreakbench.jsonl     ← 100 prompts (cached)
```

---

## Setup

**Requirements:** Python 3.11+, [uv](https://github.com/astral-sh/uv), API keys for OpenRouter and OpenAI.

```bash
# 1. Clone
git clone https://github.com/Shekhar-Kaviraj-Tiruwa-1/llm-redteam.git
cd llm-redteam

# 2. Install dependencies
uv sync

# 3. Configure API keys
cp .env.example .env
```

Edit `.env`:
```
OPENROUTER_API_KEY=sk-or-...   # https://openrouter.ai
OPENAI_API_KEY=sk-proj-...     # https://platform.openai.com (for Moderation API — free)
```

---

## Running the Pipeline

### Iteration 3 — Quad Evaluator (recommended)

```bash
cd experiments/iteration3

# Quick test: 10 prompts, custom dataset only
python pipeline.py --limit 10 --sources custom

# Full run: 488 prompts, all datasets, 15 parallel workers
python pipeline.py --concurrency 15

# Run against a different target model
python pipeline.py --target anthropic/claude-3.5-haiku --concurrency 15

# Filter to one attack category
python pipeline.py --limit 20 --category jailbreak
```

### Dashboard

```bash
# From the project root
streamlit run experiments/iteration3/dashboard_v3.py
# → http://localhost:8501
```

The dashboard shows:
- **Model comparison** — GPT-4o-mini vs Claude 3.5 Haiku side by side
- **Core finding** — all four evaluators' verdict distributions
- **Agreement map** — where evaluators agree vs diverge
- **Disagreement patterns** — the most common evaluator splits
- **Row-level inspector** — read the prompt, response, and all four verdicts for any case

### Reproduce the figures

```bash
python experiments/iteration3/generate_figures.py
# → saves PNG (300 DPI) + SVG to experiments/iteration3/figures/
```

### Iteration 1/2 (baseline runs)

```bash
# Run 75 custom prompts, keyword evaluator only
python run_eval.py --target gpt-4o-mini

# Limit to a quick test
python run_eval.py --target gpt-4o-mini --limit 10

# FastAPI results endpoint
uvicorn api:app --reload
# → http://localhost:8000/docs
```

---

## Want to Add a New Evaluator?

The pipeline uses a simple plugin interface. To add a new evaluator:

1. Create `experiments/iteration3/evaluator_yourname.py`
2. Subclass `BaseEvaluator` and implement `async evaluate(prompt, response, category) → EvalResult`
3. Register it in `pipeline.py` alongside the existing four

```python
# evaluator_base.py — the interface every evaluator implements
class BaseEvaluator(ABC):
    name: str

    async def evaluate(
        self,
        prompt:   str,
        response: str,
        category: str | None = None,
    ) -> EvalResult:
        ...

# EvalResult carries the verdict and supporting detail
@dataclass
class EvalResult:
    verdict:   Literal["safe", "unsafe", "inconclusive"]
    score:     float    # 0.0 = safe, 1.0 = unsafe
    reasoning: str      # full output / chain-of-thought
    summary:   str      # one-line explanation
```

---

## Limitations

- **No human ground truth** — when evaluators disagree, there is no adjudication beyond manual review of sampled cases (done for the 49 hardest all-disagree cases from the 3-evaluator run).
- **Judge shares biases with target** — the LLM Judge uses GPT-4o-mini, the same model as the primary target. Shared blind spots mean the 8 unsafe findings are likely an undercount.
- **LLaMA Guard via OpenRouter** — the model is accessed via a standard chat completions API rather than its native chat template, which may affect calibration.
- **Static prompts only** — the PAIR algorithm (iterative LLM-generated attacks) is not yet implemented. Adversarially optimised prompts would likely surface more failures.
- **Two models tested** — GPT-4o-mini and Claude 3.5 Haiku. Open-source or instruction-tuned models without RLHF alignment may show different patterns.

---

## References

| Paper | Relevance |
|---|---|
| Zou et al. (2023). *Universal and Transferable Adversarial Attacks on Aligned Language Models.* | GCG attack; source of the keyword refusal string list used in this project |
| Souly et al. (2024). *A StrongREJECT for Empty Jailbreaks.* NeurIPS 2024. | StrongREJECT rubric used for the LLM Judge scoring formula |
| Liu et al. (2023). *G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment.* EMNLP 2023. | G-Eval chain-of-thought prompting strategy |
| Chao et al. (2024). *JailbreakBench: An Open Robustness Benchmark for Jailbreaking LLMs.* NeurIPS 2024. | JailbreakBench dataset (100 prompts) |
| Meta AI (2024). *LLaMA Guard 3 Model Card.* | LLaMA Guard 3 safety classifier |
| Mazeika et al. (2024). *HarmBench: A Standardized Evaluation Framework for Automated Red Teaming.* | Related benchmark; keyword baseline comparison |

---

## Related Tools

| Tool | What it does | How this project differs |
|---|---|---|
| [Promptfoo](https://promptfoo.dev) | LLM testing framework | Single evaluator per run; no disagreement analysis |
| [Garak](https://github.com/leondz/garak) | LLM vulnerability scanner | Probe-based; no simultaneous multi-evaluator comparison |
| [StrongREJECT](https://strong-reject.readthedocs.io) | Improved jailbreak rubric | Proposes the rubric; does not compare it against other evaluators |
| [Microsoft PyRIT](https://github.com/Azure/PyRIT) | Python Risk Identification Toolkit | Red teaming framework; does not study evaluator disagreement |

---

## Figures

All figures are available as PNG (300 DPI) and SVG in [`experiments/iteration3/figures/`](experiments/iteration3/figures/).

| Figure | Description |
|---|---|
| `fig1_core_finding` | All four evaluators' verdict distributions on GPT-4o-mini |
| `fig2_cross_model` | Unsafe rate by evaluator — GPT-4o-mini vs Claude 3.5 Haiku |
| `fig3_agreement` | Evaluator agreement distribution (pie charts, both models) |
| `fig4_disagreement_patterns` | Top 10 disagreement patterns |
| `fig5_evaluator_gap` | The headline gap — evaluator choice vs model choice |
