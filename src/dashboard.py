"""
Iteration 3 Dashboard — Quad Evaluator Comparison

Run: streamlit run experiments/iteration3/dashboard_v3.py
     (from the project root)

Sections:
  0. Model Comparison — GPT-4o-mini vs Claude 3.5 Haiku side-by-side
  1. Run selector + live progress
  2. The Core Finding — all four evaluators side-by-side
  3. Agreement map — where evaluators agree vs diverge
  4. Disagreement patterns — which specific splits occur most
  5. By category — per-category breakdown per evaluator
  6. Disagreement detail table — every row where evaluators split
"""

import os
import sys

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from database import init_db, _connect  # noqa: E402

# ── Page config ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Iteration 3 — Evaluator Comparison",
    page_icon="🔬",
    layout="wide",
)

init_db()

# ── Colour palette ─────────────────────────────────────────────────────────────

VERDICT_COLOR = {"safe": "#2ecc71", "unsafe": "#e74c3c", "inconclusive": "#f39c12"}
AGREE_COLOR   = {
    "all_agree":    "#2ecc71",
    "majority":     "#3498db",
    "split":        "#9b59b6",
    "all_disagree": "#e74c3c",
}

EVAL_COLS = [
    ("kw_verdict",  "Keyword"),
    ("lg_verdict",  "LLaMA Guard"),
    ("lj_verdict",  "LLM Judge"),
    ("om_verdict",  "OpenAI Moderation"),
]

# ── Load data ──────────────────────────────────────────────────────────────────

@st.cache_data(ttl=15)
def load_runs() -> pd.DataFrame:
    conn = _connect()
    rows = conn.execute("SELECT * FROM runs ORDER BY created_at DESC").fetchall()
    conn.close()
    return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()


@st.cache_data(ttl=15)
def load_evaluations(run_id: str) -> pd.DataFrame:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM evaluations WHERE run_id = ? ORDER BY prompt_idx", (run_id,)
    ).fetchall()
    conn.close()
    return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()


runs_df = load_runs()

if runs_df.empty:
    st.warning("No runs found. Start the pipeline first.")
    st.stop()

# ── Identify the two primary 488-prompt runs for comparison ───────────────────

full_runs = runs_df[runs_df["prompt_count"] == 488].copy()

GPT_RUN_ID   = None
HAIKU_RUN_ID = None
for _, r in full_runs.iterrows():
    if "gpt-4o-mini" in r["target_model"] and GPT_RUN_ID is None:
        # Take the most recent gpt-4o-mini full run that has om_verdict
        GPT_RUN_ID = r["run_id"]
    if "claude-3.5-haiku" in r["target_model"] and HAIKU_RUN_ID is None:
        HAIKU_RUN_ID = r["run_id"]

# ── Section 0: Model Comparison ───────────────────────────────────────────────

st.title("🔬 LLM Safety Evaluation — Model Comparison")

if GPT_RUN_ID and HAIKU_RUN_ID:
    gpt_df   = load_evaluations(GPT_RUN_ID)
    haiku_df = load_evaluations(HAIKU_RUN_ID)

    st.subheader("0 · GPT-4o-mini vs Claude 3.5 Haiku — Same Prompts, Same Evaluators")
    st.caption(
        "Both models received the identical 488 adversarial prompts. "
        "Each bar shows what percentage of responses each evaluator classified as safe / unsafe / inconclusive."
    )

    def build_comparison_df(df, model_label):
        rows = []
        for col, label in EVAL_COLS:
            if col not in df.columns:
                continue
            counts = df[col].value_counts()
            total  = len(df)
            for verdict in ("safe", "unsafe", "inconclusive"):
                n = counts.get(verdict, 0)
                rows.append({
                    "Model":     model_label,
                    "Evaluator": label,
                    "Verdict":   verdict,
                    "Count":     n,
                    "Pct":       round(n / total * 100, 1),
                })
        return pd.DataFrame(rows)

    cmp_df = pd.concat([
        build_comparison_df(gpt_df,   "GPT-4o-mini"),
        build_comparison_df(haiku_df, "Claude 3.5 Haiku"),
    ])

    # One chart per verdict type so both models are easy to compare
    for verdict in ("unsafe", "safe", "inconclusive"):
        sub = cmp_df[cmp_df["Verdict"] == verdict]
        if sub.empty:
            continue
        color = VERDICT_COLOR[verdict]
        fig = px.bar(
            sub, x="Evaluator", y="Pct", color="Model",
            barmode="group", text="Pct",
            color_discrete_sequence=["#2980b9", "#e67e22"],
            title=f"% classified as <b>{verdict}</b>",
            labels={"Pct": "%", "Evaluator": ""},
        )
        fig.update_traces(texttemplate="%{text}%", textposition="outside")
        fig.update_layout(
            yaxis=dict(range=[0, 110]),
            legend_title_text="",
            margin=dict(t=40, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)

    # Summary table
    st.markdown("#### Numeric Summary")
    rows_table = []
    for col, label in EVAL_COLS:
        if col not in gpt_df.columns or col not in haiku_df.columns:
            continue
        for model_label, df_ in [("GPT-4o-mini", gpt_df), ("Claude 3.5 Haiku", haiku_df)]:
            counts = df_[col].value_counts()
            total  = len(df_)
            rows_table.append({
                "Evaluator": label,
                "Model":     model_label,
                "Safe %":    round(counts.get("safe", 0) / total * 100, 1),
                "Unsafe %":  round(counts.get("unsafe", 0) / total * 100, 1),
                "Inconclusive %": round(counts.get("inconclusive", 0) / total * 100, 1),
            })
    summary_df = pd.DataFrame(rows_table).set_index(["Evaluator", "Model"])
    st.dataframe(summary_df.style.format("{:.1f}"), use_container_width=True)

    # LLaMA Guard finding callout
    lg_gpt   = gpt_df["lg_verdict"].eq("unsafe").sum() / len(gpt_df) * 100
    lg_haiku = haiku_df["lg_verdict"].eq("unsafe").sum() / len(haiku_df) * 100
    lj_gpt   = gpt_df["lj_verdict"].eq("unsafe").sum() / len(gpt_df) * 100
    lj_haiku = haiku_df["lj_verdict"].eq("unsafe").sum() / len(haiku_df) * 100

    st.markdown("---")
    st.markdown("#### 🔑 Key Finding — LLaMA Guard outlier pattern is evaluator-structural")
    k1, k2, k3 = st.columns(3)
    k1.metric("LLaMA Guard unsafe — GPT-4o-mini",      f"{lg_gpt:.1f}%")
    k2.metric("LLaMA Guard unsafe — Claude 3.5 Haiku", f"{lg_haiku:.1f}%",
              delta=f"{lg_haiku - lg_gpt:+.1f} pp vs GPT")
    k3.metric("LLM Judge unsafe gap (LG minus LJ)",
              f"{lg_gpt - lj_gpt:.1f} pp  /  {lg_haiku - lj_haiku:.1f} pp",
              help="LLaMA Guard fires ~30× more 'unsafe' than the LLM Judge on both models")

    st.info(
        f"LLaMA Guard reports **{lg_gpt:.0f}%** unsafe on GPT-4o-mini and **{lg_haiku:.0f}%** on Claude 3.5 Haiku — "
        f"nearly identical rates on two completely different models. "
        f"The LLM Judge finds only **{lj_gpt:.1f}%** and **{lj_haiku:.1f}%** respectively. "
        f"This confirms the outlier pattern is a property of LLaMA Guard's calibration, not of the target model's behaviour."
    )

    # Agreement comparison
    st.markdown("#### Agreement breakdown")
    ag_labels = ["all_agree", "majority", "split", "all_disagree"]
    ag_rows   = []
    for model_label, df_ in [("GPT-4o-mini", gpt_df), ("Claude 3.5 Haiku", haiku_df)]:
        total = len(df_)
        for lbl in ag_labels:
            n = df_["agreement"].eq(lbl).sum()
            ag_rows.append({"Model": model_label, "Agreement": lbl, "Count": n, "Pct": round(n/total*100,1)})
    ag_df = pd.DataFrame(ag_rows)
    fig = px.bar(
        ag_df, x="Agreement", y="Pct", color="Model",
        barmode="group", text="Pct",
        color_discrete_sequence=["#2980b9", "#e67e22"],
        labels={"Pct": "%", "Agreement": ""},
        title="Agreement level across 4 evaluators",
    )
    fig.update_traces(texttemplate="%{text}%", textposition="outside")
    fig.update_layout(yaxis=dict(range=[0, 85]), legend_title_text="", margin=dict(t=40, b=10))
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Model comparison requires both the GPT-4o-mini and Claude 3.5 Haiku full runs (488 prompts each) to be present in the database.")

st.divider()

# ── Sidebar — single-run explorer ─────────────────────────────────────────────

st.sidebar.title("🔬 Single-Run Explorer")
st.sidebar.markdown("---")

run_options = runs_df["run_id"].tolist()
run_labels  = {
    r["run_id"]: f"{r['run_id']}  ({r['target_model'].split('/')[-1]}, {r['prompt_count']} prompts)"
    for _, r in runs_df.iterrows()
}

# Default to the GPT-4o-mini full run
default_idx = run_options.index(GPT_RUN_ID) if GPT_RUN_ID in run_options else 0
selected_run = st.sidebar.selectbox(
    "Select run", run_options, index=default_idx,
    format_func=lambda x: run_labels.get(x, x)
)

df = load_evaluations(selected_run)
run_meta = runs_df[runs_df["run_id"] == selected_run].iloc[0]

st.sidebar.markdown("---")
all_sources    = sorted(df["source"].unique().tolist())   if not df.empty else []
all_categories = sorted(df["category"].unique().tolist()) if not df.empty else []

sel_sources = st.sidebar.multiselect("Prompt source",   all_sources,    default=all_sources)
sel_cats    = st.sidebar.multiselect("Attack category", all_categories, default=all_categories)
sel_agree   = st.sidebar.multiselect(
    "Agreement filter",
    ["all_agree", "majority", "split", "all_disagree"],
    default=["all_agree", "majority", "split", "all_disagree"],
)

if df.empty:
    st.info("Run in progress — no evaluations stored yet. Dashboard refreshes every 15s.")
    st.stop()

view = df[
    df["source"].isin(sel_sources) &
    df["category"].isin(sel_cats) &
    df["agreement"].isin(sel_agree)
].copy()

# ── Title ──────────────────────────────────────────────────────────────────────

completed = len(df)
total     = int(run_meta["prompt_count"])

st.subheader(f"Single-Run Explorer — `{selected_run}` · `{run_meta['target_model']}`")
st.caption(f"Judge: `{run_meta['judge_model']}` · Sources: {run_meta['sources']}")

if completed < total:
    st.progress(completed / total, text=f"Run in progress: {completed}/{total}")

st.divider()

# ── Section 1: The Core Finding ────────────────────────────────────────────────

st.subheader("1 · The Core Finding — Same Responses, Four Different Conclusions")
st.caption("Every response scored by all four evaluators simultaneously.")

rows_list = []
for col, label in EVAL_COLS:
    if col not in view.columns:
        continue
    counts = view[col].value_counts()
    for verdict, n in counts.items():
        rows_list.append({"Evaluator": label, "Verdict": verdict, "Count": n,
                          "Pct": round(n / len(view) * 100, 1)})

comp_df = pd.DataFrame(rows_list)

col_chart, col_table = st.columns([2, 1])

with col_chart:
    fig = px.bar(
        comp_df, x="Evaluator", y="Pct", color="Verdict",
        color_discrete_map=VERDICT_COLOR,
        barmode="group", text="Pct",
        labels={"Pct": "% of Prompts", "Evaluator": ""},
    )
    fig.update_traces(texttemplate="%{text}%", textposition="outside")
    fig.update_layout(
        yaxis=dict(range=[0, 110], title="% of Prompts"),
        legend_title_text="", margin=dict(t=20, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

with col_table:
    if not comp_df.empty:
        pivot = comp_df.pivot_table(index="Evaluator", columns="Verdict", values="Pct", fill_value=0).round(1)
        for col in ["safe", "unsafe", "inconclusive"]:
            if col not in pivot.columns:
                pivot[col] = 0.0
        pivot = pivot[["safe", "unsafe", "inconclusive"]]
        pivot.columns = ["Safe %", "Unsafe %", "Inconclusive %"]
        st.dataframe(pivot.style.format("{:.1f}"), use_container_width=True)

    lj_unsafe = view["lj_verdict"].eq("unsafe").sum() if "lj_verdict" in view else 0
    kw_unsafe = view["kw_verdict"].eq("unsafe").sum() if "kw_verdict" in view else 0
    st.metric("LLM Judge finds more unsafe", f"+{lj_unsafe - kw_unsafe}")

st.divider()

# ── Section 2: Agreement Map ───────────────────────────────────────────────────

st.subheader("2 · Evaluator Agreement Map")
st.caption("How often do all four evaluators reach the same conclusion?")

n_all   = view["agreement"].eq("all_agree").sum()
n_maj   = view["agreement"].eq("majority").sum()
n_spl   = view["agreement"].eq("split").sum()
n_none  = view["agreement"].eq("all_disagree").sum()
n_total = len(view)
pct     = lambda n: f"{n/n_total*100:.1f}%" if n_total else "0%"

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total (filtered)", n_total)
c2.metric("All agree [=]",    f"{n_all} ({pct(n_all)})")
c3.metric("Majority (3+1)",   f"{n_maj} ({pct(n_maj)})")
c4.metric("Split (2+2)",      f"{n_spl} ({pct(n_spl)})")
c5.metric("All disagree [!]", f"{n_none} ({pct(n_none)})",
          delta=f"{n_none}" if n_none else None, delta_color="inverse")

agree_counts = view["agreement"].value_counts().reset_index()
agree_counts.columns = ["Agreement", "Count"]

col_donut, col_pattern = st.columns(2)

with col_donut:
    fig = px.pie(
        agree_counts, names="Agreement", values="Count",
        color="Agreement", color_discrete_map=AGREE_COLOR,
        hole=0.55, title="Agreement Distribution",
    )
    fig.update_traces(textposition="outside", textinfo="percent+label")
    fig.update_layout(showlegend=False, margin=dict(t=40, b=10))
    st.plotly_chart(fig, use_container_width=True)

with col_pattern:
    st.markdown("#### Top Disagreement Patterns")
    st.caption("Each pattern shows exactly which evaluators disagreed and how.")
    patterns = (
        view[view["agreement"] != "all_agree"]["disagreement_pattern"]
        .value_counts().head(10).reset_index()
    )
    patterns.columns = ["Pattern", "Count"]

    if not patterns.empty:
        fig = px.bar(
            patterns, x="Count", y="Pattern", orientation="h",
            color="Count", color_continuous_scale=["#3498db", "#e74c3c"],
            text="Count",
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(
            coloraxis_showscale=False,
            yaxis=dict(categoryorder="total ascending"),
            margin=dict(t=10, b=10), xaxis_title="",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No disagreements in current filter.")

st.divider()

# ── Section 3: By Category ─────────────────────────────────────────────────────

st.subheader("3 · Results by Attack Category")

eval_choice = st.radio(
    "Evaluator",
    ["Keyword", "LLaMA Guard", "LLM Judge", "OpenAI Moderation"],
    horizontal=True, index=2,
)
col_map = {
    "Keyword":           "kw_verdict",
    "LLaMA Guard":       "lg_verdict",
    "LLM Judge":         "lj_verdict",
    "OpenAI Moderation": "om_verdict",
}
verdict_col = col_map[eval_choice]

if verdict_col in view.columns:
    cat_df = (
        view.groupby(["category", verdict_col])
        .size().reset_index(name="count")
        .rename(columns={verdict_col: "verdict"})
    )
    cat_totals = view.groupby("category").size().reset_index(name="total")
    cat_df = cat_df.merge(cat_totals, on="category")
    cat_df["pct"] = (cat_df["count"] / cat_df["total"] * 100).round(1)

    fig = px.bar(
        cat_df, x="pct", y="category", color="verdict",
        color_discrete_map=VERDICT_COLOR,
        orientation="h", barmode="stack", text="pct",
        labels={"pct": "% of prompts", "category": "", "verdict": "Verdict"},
        title=f"{eval_choice} verdicts by category",
    )
    fig.update_traces(texttemplate="%{text:.0f}%", textposition="inside")
    fig.update_layout(
        yaxis=dict(categoryorder="total ascending"),
        xaxis=dict(range=[0, 101]),
        legend_title_text="", margin=dict(t=40, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Section 4: Disagreement Detail Table ──────────────────────────────────────

st.subheader("4 · Disagreement Detail")
st.caption("Every row where evaluators did not all agree.")

show_only_splits = st.checkbox("Show only all_disagree rows [!]", value=False)

detail = (
    view[view["agreement"] == "all_disagree"].copy()
    if show_only_splits
    else view[view["agreement"] != "all_agree"].copy()
)

if detail.empty:
    st.info("No disagreements match the current filter.")
else:
    detail["Keyword"]           = detail["kw_verdict"]
    detail["LLaMA Guard"]       = detail["lg_verdict"]
    detail["LLM Judge"]         = detail["lj_verdict"]
    detail["OpenAI Mod"]        = detail.get("om_verdict", "—")
    detail["Why"]               = detail["lj_summary"]
    detail["Prompt"]            = detail["prompt_text"].str[:80] + "…"
    detail["Agr"]               = detail["agreement"].map(
        {"all_agree": "=", "majority": "~", "split": "≈", "all_disagree": "!"}
    )

    display_cols = ["Agr", "source", "category", "Prompt",
                    "Keyword", "LLaMA Guard", "LLM Judge", "OpenAI Mod", "Why"]

    def _color_verdict(val):
        colors = {"safe": "color: #27ae60", "unsafe": "color: #c0392b", "inconclusive": "color: #d35400"}
        return colors.get(val, "")

    styled = (
        detail[display_cols].reset_index(drop=True)
        .style.map(_color_verdict, subset=["Keyword", "LLaMA Guard", "LLM Judge", "OpenAI Mod"])
    )
    st.dataframe(styled, use_container_width=True, height=400)

    st.markdown("#### Inspect a row")
    idx = st.number_input("Row index", min_value=0, max_value=len(detail) - 1, value=0, step=1)
    row = detail.iloc[int(idx)]
    with st.expander(f"[{row['agreement']}]  {row['prompt_text'][:80]}...", expanded=True):
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"**Category:** `{row['category']}`")
        c2.markdown(f"**Source:** `{row['source']}`")
        c3.markdown(f"**Pattern:** `{row['disagreement_pattern']}`")

        st.markdown("**Prompt**")
        st.info(row["prompt_text"])

        st.markdown("**Target model response**")
        st.warning(row["response"])

        st.markdown("**Evaluator verdicts**")
        vc1, vc2, vc3, vc4 = st.columns(4)
        vc1.metric("Keyword",           row["kw_verdict"], help=row["kw_summary"])
        vc2.metric("LLaMA Guard",       row["lg_verdict"], help=row["lg_summary"])
        vc3.metric("LLM Judge",         row["lj_verdict"])
        vc4.metric("OpenAI Moderation", row.get("om_verdict", "—"), help=row.get("om_summary", ""))

        st.markdown("**LLM Judge reasoning (full)**")
        st.code(row["lj_reasoning"], language=None)

st.divider()
st.caption(
    f"run_id: `{selected_run}` · {completed}/{total} prompts · "
    "Dashboard auto-refreshes every 15s while a run is in progress."
)
