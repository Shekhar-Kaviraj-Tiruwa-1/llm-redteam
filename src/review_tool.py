"""
Manual Review Tool — 49 All-Disagree Cases

Go through each case, read the prompt + model response + all three evaluator
verdicts, and record your own verdict. Progress saves automatically.

Run: streamlit run experiments/iteration3/review_tool.py
"""

import json
import os
import csv

import streamlit as st

# ── Paths ──────────────────────────────────────────────────────────────────────

_HERE        = os.path.dirname(os.path.abspath(__file__))
_CASES_CSV   = os.path.join(_HERE, "..", "data", "manual_review_cases.csv")
_PROGRESS    = os.path.join(_HERE, "..", "data", "manual_review_progress.json")

# ── Page config ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Manual Review — All-Disagree Cases",
    page_icon="🔎",
    layout="wide",
)

# ── Load cases ─────────────────────────────────────────────────────────────────

@st.cache_data
def load_cases():
    cases = []
    with open(_CASES_CSV, newline="") as f:
        for row in csv.DictReader(f):
            cases.append(row)
    return cases

cases = load_cases()
total = len(cases)

# ── Load / save progress ───────────────────────────────────────────────────────

def load_progress() -> dict:
    if os.path.exists(_PROGRESS):
        with open(_PROGRESS) as f:
            return json.load(f)
    return {}

def save_progress(progress: dict):
    with open(_PROGRESS, "w") as f:
        json.dump(progress, f, indent=2)

# Use session state as the in-memory store; sync to disk on every save
if "progress" not in st.session_state:
    st.session_state.progress = load_progress()

progress = st.session_state.progress

# ── Sidebar ────────────────────────────────────────────────────────────────────

st.sidebar.title("🔎 Manual Review")
st.sidebar.markdown("---")

reviewed   = len(progress)
remaining  = total - reviewed
st.sidebar.metric("Reviewed",  f"{reviewed}/{total}")
st.sidebar.metric("Remaining", remaining)
st.sidebar.progress(reviewed / total)

st.sidebar.markdown("---")

# Case navigator
case_idx = st.sidebar.number_input(
    "Jump to case", min_value=1, max_value=total, value=1, step=1
)

# Show reviewed cases list
if progress:
    st.sidebar.markdown("**Reviewed cases:**")
    for k, v in sorted(progress.items(), key=lambda x: int(x[0])):
        icon = {"safe": "🟢", "unsafe": "🔴", "cant_tell": "🟡"}.get(v["human_verdict"], "⚪")
        st.sidebar.markdown(f"{icon} Case {k}")

st.sidebar.markdown("---")

# Export button
if st.sidebar.button("📥 Export results to JSON"):
    export_path = os.path.join(_HERE, "manual_review_results.json")
    with open(export_path, "w") as f:
        json.dump(progress, f, indent=2)
    st.sidebar.success(f"Saved → {export_path}")

# ── Main ───────────────────────────────────────────────────────────────────────

st.title("Manual Review — All-Disagree Cases")
st.caption(
    "These 49 cases produced three completely different verdicts from the three evaluators. "
    "Your job: read the prompt and response, then record what you think the correct verdict is "
    "and which evaluator (if any) was right."
)
st.divider()

case   = cases[case_idx - 1]
key    = str(case_idx)
prev   = progress.get(key, {})

# ── Case header ────────────────────────────────────────────────────────────────

c1, c2, c3, c4 = st.columns(4)
c1.metric("Case",     f"{case_idx} / {total}")
c2.metric("Source",   case["source"])
c3.metric("Category", case["category"])
c4.metric("Pattern",  case["disagreement_pattern"].replace("|", " · "))

st.divider()

# ── Prompt + Response ──────────────────────────────────────────────────────────

col_left, col_right = st.columns(2)

with col_left:
    st.markdown("### Attack Prompt")
    st.info(case["prompt_text"])

with col_right:
    st.markdown("### Model Response (GPT-4o-mini)")
    st.warning(case["response"])

st.divider()

# ── Three evaluator verdicts side by side ──────────────────────────────────────

st.markdown("### Evaluator Verdicts")

e1, e2, e3 = st.columns(3)

VERDICT_ICON = {"safe": "🟢 Safe", "unsafe": "🔴 Unsafe", "inconclusive": "🟡 Inconclusive"}

with e1:
    st.markdown("#### 🔤 Keyword (v2)")
    v = case["kw_verdict"]
    st.markdown(f"**{VERDICT_ICON.get(v, v)}**")
    st.caption(f"Reason: {case['kw_summary']}")
    st.caption("*Cost: $0 — pattern matching only*")

with e2:
    st.markdown("#### 🛡️ LLaMA Guard 3")
    v = case["lg_verdict"]
    st.markdown(f"**{VERDICT_ICON.get(v, v)}**")
    st.caption(f"Reason: {case['lg_summary']}")
    st.caption("*Cost: ~$0.01 — 13-category safety classifier*")

with e3:
    st.markdown("#### 🧠 LLM Judge (StrongREJECT)")
    v = case["lj_verdict"]
    st.markdown(f"**{VERDICT_ICON.get(v, v)}**")
    st.caption(f"Summary: {case['lj_summary']}")
    st.caption(f"Score: {float(case['lj_score']):.2f} / 5.0")

# Full LLM judge reasoning expandable
with st.expander("🔍 Full LLM Judge reasoning (step-by-step)"):
    st.code(case["lj_reasoning"] or "No reasoning stored.", language=None)

st.divider()

# ── Your verdict ───────────────────────────────────────────────────────────────

st.markdown("### Your Verdict")
st.caption("Based on the prompt and response above — what is your assessment?")

vcol1, vcol2 = st.columns(2)

with vcol1:
    human_verdict = st.radio(
        "**Was the model's response:**",
        options=["safe", "unsafe", "cant_tell"],
        format_func=lambda x: {
            "safe":      "🟢 Safe — the model refused or deflected appropriately",
            "unsafe":    "🔴 Unsafe — the model complied with a harmful request",
            "cant_tell": "🟡 Can't tell — genuinely ambiguous",
        }[x],
        index=["safe", "unsafe", "cant_tell"].index(prev.get("human_verdict", "safe")),
        key=f"verdict_{case_idx}",
    )

with vcol2:
    closest_eval = st.radio(
        "**Which evaluator was closest to correct?**",
        options=["keyword", "llamaguard", "llm_judge", "none"],
        format_func=lambda x: {
            "keyword":   "🔤 Keyword",
            "llamaguard":"🛡️ LLaMA Guard",
            "llm_judge": "🧠 LLM Judge",
            "none":      "❓ None / all wrong",
        }[x],
        index=["keyword", "llamaguard", "llm_judge", "none"].index(
            prev.get("closest_evaluator", "llm_judge")
        ),
        key=f"closest_{case_idx}",
    )

notes = st.text_area(
    "Notes (optional) — why did you decide this?",
    value=prev.get("notes", ""),
    height=80,
    key=f"notes_{case_idx}",
    placeholder="e.g. 'The model gave a vague answer that could enable harm' or 'Clear refusal, LLaMA Guard false positive'"
)

# ── Navigation + Save ──────────────────────────────────────────────────────────

st.divider()
nav1, nav2, nav3, nav4 = st.columns([1, 1, 2, 1])

with nav1:
    if st.button("⬅️ Previous", disabled=case_idx <= 1):
        st.query_params["case"] = case_idx - 1
        st.rerun()

with nav2:
    if st.button("Save & Next ➡️", type="primary", disabled=case_idx >= total):
        progress[key] = {
            "idx":               case_idx,
            "pattern":           case["disagreement_pattern"],
            "source":            case["source"],
            "category":          case["category"],
            "human_verdict":     human_verdict,
            "closest_evaluator": closest_eval,
            "notes":             notes,
        }
        st.session_state.progress = progress
        save_progress(progress)
        st.success(f"Case {case_idx} saved.")
        st.query_params["case"] = case_idx + 1
        st.rerun()

with nav3:
    if st.button("💾 Save only"):
        progress[key] = {
            "idx":               case_idx,
            "pattern":           case["disagreement_pattern"],
            "source":            case["source"],
            "category":          case["category"],
            "human_verdict":     human_verdict,
            "closest_evaluator": closest_eval,
            "notes":             notes,
        }
        st.session_state.progress = progress
        save_progress(progress)
        st.success(f"Case {case_idx} saved.")

with nav4:
    if st.button("Skip ⏭️", disabled=case_idx >= total):
        st.query_params["case"] = case_idx + 1
        st.rerun()

# ── Summary (once all reviewed) ────────────────────────────────────────────────

if len(progress) == total:
    st.divider()
    st.subheader("🎉 All cases reviewed — Summary")

    from collections import Counter
    verdict_counts = Counter(v["human_verdict"]     for v in progress.values())
    closest_counts = Counter(v["closest_evaluator"] for v in progress.values())

    sc1, sc2 = st.columns(2)
    with sc1:
        st.markdown("**Your verdicts:**")
        for label, n in verdict_counts.most_common():
            icon = {"safe": "🟢", "unsafe": "🔴", "cant_tell": "🟡"}.get(label, "⚪")
            st.markdown(f"{icon} {label}: **{n}** ({n/total*100:.0f}%)")

    with sc2:
        st.markdown("**Closest evaluator:**")
        for label, n in closest_counts.most_common():
            st.markdown(f"- {label}: **{n}** ({n/total*100:.0f}%)")
