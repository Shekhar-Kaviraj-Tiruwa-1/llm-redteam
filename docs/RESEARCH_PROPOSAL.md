# Can We Trust How We Measure AI Safety?
## An Empirical Study of Evaluator Disagreement in LLM Safety Testing

**Author:** Shekhar Tiruwa  
**Programme:** BlueDot Impact — Technical AI Safety Sprint  
**Date:** April 2026

---

## Abstract

Automated safety evaluation of large language models (LLMs) is now standard practice, yet the field has no consensus on which evaluation method to use. This project tests whether the choice of evaluator changes the safety conclusion — even when the model, prompts, and responses are held constant. Running three evaluators simultaneously (keyword matching, LLaMA Guard 3, and an LLM judge using the StrongREJECT rubric) against 487 adversarial prompts sent to GPT-4o-mini, we find that the methods agree on only 7% of responses. On the same dataset, the keyword evaluator reports 0.4% unsafe responses, LLaMA Guard reports 31.1%, and the LLM judge reports 1.7%. The variation is not measurement noise — it is a structural property of how each method reads model behaviour. We conclude that evaluator choice is a primary determinant of reported AI safety outcomes, and that no single automated method can be trusted in isolation.

---

## 1. Problem Statement

AI safety evaluation is the process of determining whether a language model will comply with harmful requests. It is used by researchers to benchmark models, by companies to certify deployments, and increasingly by regulators to assess compliance.

The dominant practice is to use a single evaluator — typically keyword matching (fast, cheap) or an LLM-as-judge (more accurate, more expensive) — and report the results as if they were ground truth. Two papers evaluating the same model with the same prompts could use different methods and arrive at incompatible safety scores. Neither paper would be wrong about what their evaluator found. But neither paper would surface the more important question: **how much does the evaluator itself determine the outcome?**

This project was designed to answer that question empirically.

---

## 2. Research Question

> **When three evaluators score the same adversarial prompts against the same model, how often do they agree — and what do the disagreements reveal about evaluator reliability?**

Secondary questions:
- Does the LLM judge's semantic understanding significantly reduce the inconclusive rate of keyword evaluators?
- Does LLaMA Guard 3 — a purpose-built safety classifier — produce results consistent with LLM-judge-level reasoning?
- Which attack categories and prompt sources produce the most evaluator disagreement?

---

## 3. Methodology

### 3.1 Project Evolution

The project ran in three iterations, each building on the findings of the last.

**Iteration 1 — Keyword Baseline (March 2026)**  
Built a keyword-based evaluator (v2) with signals for compliance, refusal, and silent ignore. Ran 75 custom adversarial prompts against GPT-3.5-turbo and GPT-4o-mini.

| Model | Safe | Unsafe | Inconclusive |
|---|---|---|---|
| GPT-3.5-turbo | 27% | 3% | 70% |
| GPT-4o-mini | 40% | 1% | 59% |

**Finding:** 59–70% inconclusive rate. The keyword evaluator could not classify the majority of responses. GPT-4o-mini frequently refused or deflected without emitting any keyword signal.

**Iteration 2 — LLM Judge (March 2026)**  
Added an LLM-as-judge evaluator that reads the full response and classifies by meaning rather than surface patterns. Ran on the same 75 prompts and same responses.

| Evaluator | Safe | Unsafe | Inconclusive |
|---|---|---|---|
| Keyword (v2) | 27% | 1% | 70% |
| LLM Judge | 75% | 24% | 1% |

**Finding:** On identical data, the LLM judge found 24% unsafe versus 1% for keyword. Inconclusive rate dropped from 70% to 1%. This confirmed that evaluator choice — not model behaviour — was driving the reported safety score.

**Iteration 3 — Triple Evaluator (April 2026)**  
Built a plugin-based pipeline running all three evaluators simultaneously on 487 prompts from three standardised datasets. Every response receives three independent verdicts stored side-by-side for disagreement analysis.

### 3.2 Datasets

| Source | Prompts | Description |
|---|---|---|
| Custom | 75 | 5 attack categories: data leakage, hallucination, prompt injection, jailbreak, role-play |
| StrongREJECT | 313 | Souly et al., NeurIPS 2024. Covers 6 harm categories including violence, disinformation, illegal goods |
| JailbreakBench | 100 | Chao et al., JailbreakBench 2024. Adversarially optimised harmful behaviours |
| **Total** | **488** | |

### 3.3 Target Model

GPT-4o-mini via OpenRouter (`openai/gpt-4o-mini`). Chosen as the primary target because Iteration 1 established it as meaningfully safer than GPT-3.5-turbo, providing a useful baseline for the evaluation comparison.

### 3.4 Evaluators

**Evaluator 1 — Keyword (v2)** *(baseline, $0)*  
Pattern matching against lists of compliance signals, refusal signals, and silent-ignore signals. Returns safe/unsafe/inconclusive. Serves as the Iteration 1 baseline and the lowest-cost reference point.

**Evaluator 2 — LLaMA Guard 3** *($0.01/call)*  
Meta's open-source safety classifier (`meta-llama/llama-guard-3-8b`) covering 13 harm categories (MLCommons taxonomy). Called via OpenRouter with an explicit classification prompt. Returns safe/unsafe.

**Evaluator 3 — LLM Judge: StrongREJECT + G-Eval CoT** *($0.02/call)*  
Implements the StrongREJECT rubric (Souly et al., NeurIPS 2024) with G-Eval chain-of-thought prompting (Liu et al., EMNLP 2023). The judge reasons step-by-step:
- Step 1: Did the model refuse? (yes / partial / no)
- Step 2: How specific is any harmful content? (1–5)
- Step 3: How convincing / actionable is it? (1–5)
- Step 4: Plain-English one-sentence summary

Score formula: `(1 - refusal) × (specificity + convincingness) / 2`

Temperature fixed at 0 for deterministic scoring. The judge model is the same GPT-4o-mini as the target — a known limitation discussed in Section 6.

### 3.5 Infrastructure

- **Unified API client:** All model calls go through OpenRouter's unified endpoint. Any model is swappable with a single string change.
- **Plugin architecture:** Each evaluator implements a common `BaseEvaluator` interface. New evaluators can be added without modifying the pipeline.
- **Parallel execution:** 15 prompts processed concurrently using `asyncio`. Each prompt makes 4 simultaneous API calls (1 target + 3 evaluators). 487 prompts completed in approximately 20 minutes.
- **Storage:** SQLite (WAL mode) stores all three verdicts flat per response. Agreement and disagreement pattern computed and stored at write time.

---

## 4. Results

### 4.1 Core Finding: Evaluator Determines the Safety Score

| Evaluator | Safe | Unsafe | Inconclusive |
|---|---|---|---|
| Keyword (v2) | 336 (69.6%) | 2 (0.4%) | 145 (30.0%) |
| LLaMA Guard 3 | 37 (7.7%) | 150 (31.1%) | 296 (61.3%) |
| LLM Judge | 450 (93.2%) | 8 (1.7%) | 25 (5.2%) |

The same 487 responses were rated 0.4% unsafe by keyword, 31.1% by LLaMA Guard, and 1.7% by the LLM judge. **The variation spans two orders of magnitude.** This is not measurement noise. It reflects three fundamentally different theories of what "unsafe" means.

### 4.2 Evaluator Agreement

| Agreement | Count | % |
|---|---|---|
| All three agree `[=]` | 34 | 7.0% |
| Two agree, one differs `[~]` | 400 | 82.1% |
| All three disagree `[!]` | 49 | 10.1% |

**93% of prompts produced some form of disagreement.** Only 7% achieved unanimous verdicts. On 49 prompts (10%), all three methods arrived at entirely different conclusions about the same response.

### 4.3 Top Disagreement Patterns

| Pattern | Count | Interpretation |
|---|---|---|
| `kw=safe \| lg=inconclusive \| lj=safe` | 212 | LLaMA Guard uncertain; other two agree safe |
| `kw=safe \| lg=unsafe \| lj=safe` | 88 | LLaMA Guard false positive; other two agree safe |
| `kw=inconclusive \| lg=inconclusive \| lj=safe` | 70 | Both legacy methods fail; LLM judge resolves |
| `kw=inconclusive \| lg=unsafe \| lj=safe` | 43 | Keyword misses; LLaMA Guard alarms; Judge says safe |

The dominant pattern (212 cases) shows LLaMA Guard returning inconclusive where both keyword and LLM judge are confident. The second pattern (88 cases) shows LLaMA Guard firing a false positive that neither other evaluator reproduces.

### 4.4 What the LLM Judge Found Unsafe

The LLM judge — the most semantically capable method — identified 8 genuine compliance failures out of 487 prompts.

| Source | Unsafe |
|---|---|
| Custom (75 prompts) | 0 |
| StrongREJECT (309 prompts) | 2 |
| JailbreakBench (99 prompts) | 6 |

Zero failures on custom prompts. All failures came from external standardised benchmarks. JailbreakBench produced a 6.1% failure rate — approximately 10× higher than StrongREJECT — consistent with its design as an adversarially optimised benchmark.

### 4.5 Replication of the Iteration 2 Finding

Iteration 2 found a 1% vs 24% gap between keyword and LLM judge on 75 custom prompts. Iteration 3, across 487 prompts from three sources, finds a 0.4% vs 1.7% gap. The absolute numbers differ because external benchmarks include more requests the model simply won't answer (safe responses). The structural finding — that the LLM judge resolves cases the keyword evaluator cannot — is replicated.

---

## 5. Original Contributions

This project makes four contributions not present in existing work:

**1. Triple evaluator on every response**  
All existing evaluation tools (Promptfoo, Garak, StrongREJECT, LLaMA Guard) let you pick one method. None run multiple evaluators on the same response and store the results together for comparison. This pipeline does.

**2. Disagreement map**  
The stored `disagreement_pattern` field (e.g. `kw=safe|lg=unsafe|lj=safe`) makes evaluator divergence queryable. The frequency distribution of patterns reveals structural properties of each method that would be invisible in single-evaluator studies.

**3. Evaluator evolution tracking**  
Iterations 1–3 applied v1, v2, and v3 evaluators to the same prompts. This produces an empirical ceiling for each method and makes the incremental gain of each approach visible.

**4. Step-by-step judge transparency**  
The StrongREJECT rubric decomposes the verdict into explicit sub-scores (refusal, specificity, convincingness) with a plain-English summary. The dashboard exposes this reasoning, making the judge auditable in a way that black-box classifiers are not.

**The 1% vs 24% / 0.4% vs 31% finding**  
No published paper has run keyword evaluation and LLM-as-judge on the same adversarial dataset and reported the gap. This project does, across three datasets and 487 prompts.

---

## 6. Related Work

| Work | What it does | How this project differs |
|---|---|---|
| **Promptfoo** | LLM testing framework, multiple evaluator types | Single evaluator per run; no disagreement analysis |
| **Garak** | LLM vulnerability scanner | Probe-based; no simultaneous multi-evaluator comparison |
| **StrongREJECT** (Souly et al., NeurIPS 2024) | Improved jailbreak rubric and dataset | Proposes the rubric; does not compare it against other evaluators on the same data |
| **LLaMA Guard 3** (Meta) | Safety classifier, 13 categories | Single classifier; not compared against LLM judges on the same responses |
| **G-Eval** (Liu et al., EMNLP 2023) | CoT prompting for NLG evaluation | Framework paper; not applied to safety evaluation |
| **JailbreakBench** (Chao et al., 2024) | Standardised jailbreak benchmark | Dataset and leaderboard; uses one evaluator |

---

## 7. Limitations

**Judge model shares biases with target model**  
Both the target and the LLM judge use GPT-4o-mini. If the model has a systematic blind spot — e.g. it does not recognise a certain type of harmful content — both the target and the judge will be wrong in the same direction. The 8 unsafe findings are likely an undercount.

**LLaMA Guard via OpenRouter**  
LLaMA Guard 3 is designed for use with its native chat template. Via OpenRouter's standard chat completions API, the prompt format had to be simplified to a direct classification instruction. Results may differ from running the model with its native interface.

**Static prompts only**  
All 487 prompts are pre-written. The PAIR approach (iterative LLM-generated attacks) is not yet implemented. Adversarially optimised prompts would likely surface more failures.

**Single target model**  
Only GPT-4o-mini was tested. Agreement patterns may differ for other models — particularly open-source models which were not pre-aligned with RLHF.

**Ground truth is absent**  
There is no human-labelled ground truth to arbitrate between evaluators when they disagree. The 49 all-disagree cases are identified but not adjudicated.

---

## 8. Next Steps

**Immediate**
- Sample the 49 all-disagree cases for manual review to establish which evaluator was correct
- Run the same pipeline against a second model (`meta-llama/llama-3.1-8b-instruct`) to test whether disagreement patterns are model-specific or evaluator-structural

**Phase 3 — Attacker LLM (PAIR)**
- Implement the PAIR algorithm (Chao et al., 2023): a second LLM iteratively rewrites prompts to be more effective at bypassing the target
- Compare static benchmark failure rates against PAIR-generated attack failure rates

**Phase 4 — Multi-turn and Agentic Testing**
- Extend to multi-turn conversations (models show up to 195% more vulnerabilities in multi-turn scenarios)
- Test tool-use and agentic workflows — the genuine gap versus existing tools

---

## 9. Repository Structure

```
projects/
├── run_eval.py                    # Iteration 1/2 CLI runner
├── evaluator.py                   # Keyword evaluator (v2)
├── evaluator_llm.py               # LLM judge (Iteration 2)
├── evaluator_versions/            # Versioned evaluator history
├── prompts/                       # 75 custom adversarial prompts
├── experiments/                   # Timestamped JSONL output per run
│
└── experiments/iteration3/        # Iteration 3 — Triple Evaluator
    ├── pipeline.py                # Main runner (concurrent, 15 parallel)
    ├── config.py                  # Model constants, API key loading
    ├── openrouter_client.py       # Unified API client (any model)
    ├── evaluator_base.py          # Plugin interface (BaseEvaluator, EvalResult)
    ├── evaluator_keyword.py       # Keyword evaluator adapter
    ├── evaluator_llamaguard.py    # LLaMA Guard 3 evaluator
    ├── evaluator_llm_judge.py     # StrongREJECT + G-Eval CoT judge
    ├── target_runner.py           # Sends prompts to target model
    ├── database_v3.py             # SQLite schema (triple verdicts + agreement)
    ├── dashboard_v3.py            # Streamlit dashboard
    └── prompts/
        ├── loader.py              # Unified prompt loader (3 sources)
        ├── fetch_external.py      # One-time dataset downloader
        ├── strongreject.jsonl     # 313 prompts (cached)
        └── jailbreakbench.jsonl   # 100 prompts (cached)
```

---

## 10. References

- Souly, A. et al. (2024). *A StrongREJECT for Empty Jailbreaks*. NeurIPS 2024.
- Liu, Y. et al. (2023). *G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment*. EMNLP 2023.
- Chao, P. et al. (2023). *Jailbreaking Black Box Large Language Models in Twenty Queries*. arXiv:2310.08419.
- Meta AI (2024). *LLaMA Guard 3: Meta Llama Guard 3 Model Card*. Meta.
- Chao, P. et al. (2024). *JailbreakBench: An Open Robustness Benchmark for Jailbreaking LLMs*. NeurIPS 2024.
- Perez, F. & Ribeiro, I. (2022). *Ignore Previous Prompt: Attack Techniques For Language Models*. NeurIPS ML Safety Workshop.
