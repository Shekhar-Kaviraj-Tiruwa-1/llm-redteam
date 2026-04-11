# Streamlit dashboard for visualising red team evaluation results
# Run: streamlit run dashboard.py

import streamlit as st
import pandas as pd
import plotly.express as px
from database import init_db, get_results

# ── Page config ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="LLM Red Team Dashboard",
    layout="wide",
)

init_db()

# ── Load & prepare data ────────────────────────────────────────────────────────

rows = get_results()

if not rows:
    st.warning("No results found. Run `python run_eval.py` first.")
    st.stop()

df = pd.DataFrame(rows)

VERDICT_COLOR = {
    "Safe":         "#2ecc71",
    "Unsafe":       "#e74c3c",
    "Inconclusive": "#f39c12",
}

VERDICT_BG = {
    "Safe":         "#d4edda",
    "Unsafe":       "#f8d7da",
    "Inconclusive": "#fff3cd",
}

def to_verdict(val):
    if val == 1:   return "Safe"
    if val == 0:   return "Unsafe"
    return "Inconclusive"

df["verdict"] = df["passed"].apply(to_verdict)

# ── Sidebar filters ────────────────────────────────────────────────────────────

st.sidebar.title("Filters")

run_options = ["All runs"] + sorted(df["run_id"].unique().tolist(), reverse=True)
selected_run = st.sidebar.selectbox("Run", run_options)

model_options = ["All models"] + sorted(df["model"].unique().tolist())
selected_model = st.sidebar.selectbox("Model", model_options)

if "evaluator_type" in df.columns:
    eval_options = ["All evaluators"] + sorted(df["evaluator_type"].unique().tolist())
    selected_eval = st.sidebar.selectbox("Evaluator", eval_options)
else:
    selected_eval = "All evaluators"

# Apply filters
view = df.copy()
if selected_run   != "All runs":       view = view[view["run_id"]         == selected_run]
if selected_model != "All models":     view = view[view["model"]           == selected_model]
if selected_eval  != "All evaluators": view = view[view["evaluator_type"]  == selected_eval]

# ── Title ──────────────────────────────────────────────────────────────────────

st.title("LLM Red Team Evaluation Dashboard")

if selected_run != "All runs":
    meta = df[df["run_id"] == selected_run].iloc[0]
    evaluator_label = meta.get("evaluator_type", "keyword")
    st.caption(
        f"Run: `{selected_run}` · Model: `{meta['model']}` · Evaluator: `{evaluator_label}`"
    )

st.divider()

# ── Section 1: Summary metrics ─────────────────────────────────────────────────

total    = len(view)
n_safe   = (view["verdict"] == "Safe").sum()
n_unsafe = (view["verdict"] == "Unsafe").sum()
n_inconc = (view["verdict"] == "Inconclusive").sum()

pct = lambda n: f"{n/total*100:.0f}%" if total else "0%"

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Prompts",  total)
col2.metric("Safe",           f"{n_safe} ({pct(n_safe)})")
col3.metric("Unsafe",         f"{n_unsafe} ({pct(n_unsafe)})",
            delta=f"-{n_unsafe}" if n_unsafe else None, delta_color="inverse")
col4.metric("Inconclusive",   f"{n_inconc} ({pct(n_inconc)})")

st.divider()

# ── Section 2: Verdict donut + category breakdown ──────────────────────────────

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Verdict Distribution")
    counts = view["verdict"].value_counts().reset_index()
    counts.columns = ["Verdict", "Count"]
    fig = px.pie(
        counts,
        names="Verdict",
        values="Count",
        color="Verdict",
        color_discrete_map=VERDICT_COLOR,
        hole=0.5,
    )
    fig.update_traces(textposition="outside", textinfo="percent+label")
    fig.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.subheader("Results by Category")
    cat = view.groupby(["category", "verdict"]).size().reset_index(name="count")
    fig = px.bar(
        cat,
        x="category", y="count",
        color="verdict",
        color_discrete_map=VERDICT_COLOR,
        barmode="stack",
        labels={"category": "Category", "count": "Prompts", "verdict": "Verdict"},
    )
    fig.update_layout(margin=dict(t=10, b=10), legend_title_text="",
                      xaxis_title="", yaxis_title="Prompts")
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Section 3: Evaluator comparison (only if both keyword + llm runs exist) ────

if "evaluator_type" in df.columns and df["evaluator_type"].nunique() > 1:
    st.subheader("Keyword Evaluator vs LLM Judge")

    comp = df.groupby(["evaluator_type", "verdict"]).size().reset_index(name="count")
    totals = df.groupby("evaluator_type").size().reset_index(name="total")
    comp = comp.merge(totals, on="evaluator_type")
    comp["pct"] = (comp["count"] / comp["total"] * 100).round(1)

    fig = px.bar(
        comp,
        x="evaluator_type", y="pct",
        color="verdict",
        color_discrete_map=VERDICT_COLOR,
        barmode="group",
        text="pct",
        labels={"evaluator_type": "Evaluator", "pct": "% of Prompts", "verdict": "Verdict"},
    )
    fig.update_traces(texttemplate="%{text}%", textposition="outside")
    fig.update_layout(
        margin=dict(t=10, b=10), legend_title_text="",
        yaxis=dict(title="% of Prompts", range=[0, 100]),
        xaxis_title="",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.divider()

# ── Section 4: Failure analysis ────────────────────────────────────────────────

failures = view[view["verdict"] == "Unsafe"]

if not failures.empty:
    st.subheader(f"Failure Analysis — {len(failures)} unsafe responses")

    fail_cat = failures["category"].value_counts().reset_index()
    fail_cat.columns = ["Category", "Failures"]

    fig = px.bar(
        fail_cat,
        x="Failures", y="Category",
        orientation="h",
        color="Failures",
        color_continuous_scale=["#f9c0c0", "#e74c3c"],
        text="Failures",
        labels={"Failures": "Number of Failures", "Category": ""},
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        margin=dict(t=10, b=10),
        coloraxis_showscale=False,
        yaxis=dict(categoryorder="total ascending"),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Failed Prompts — Detail")
    for _, row in failures.iterrows():
        with st.expander(f"[{row['category']}]  {row['prompt_text'][:80]}..."):
            st.markdown(f"**Prompt**")
            st.info(row["prompt_text"])
            st.markdown(f"**Response**")
            st.warning(row["response"])
            st.markdown(f"**Judge reason:** {row['reason']}")
            eval_type = row.get("evaluator_type", "keyword")
            st.caption(f"run_id: `{row['run_id']}` · model: `{row['model']}` · evaluator: `{eval_type}`")

    st.divider()

# ── Section 5: Full results table ──────────────────────────────────────────────

st.subheader("All Results")

display_cols  = ["run_id", "model", "evaluator_type", "category", "prompt_text", "verdict", "reason"]
available     = [c for c in display_cols if c in view.columns]

styled = (
    view[available]
    .style
    .map(lambda v: f"background-color: {VERDICT_BG.get(v, '')}", subset=["verdict"])
)
st.dataframe(styled, use_container_width=True)
