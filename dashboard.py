# Streamlit dashboard for visualising red team evaluation results
# Run: streamlit run dashboard.py

import streamlit as st
import pandas as pd
from database import init_db, get_results

init_db()

st.set_page_config(page_title="LLM Red Team Dashboard", layout="wide")
st.title("LLM Red Team Evaluation Dashboard")

# Load all results from DB
rows = get_results()

if not rows:
    st.warning("No results found. Run `python run_eval.py` first.")
    st.stop()

df = pd.DataFrame(rows)

# Sidebar — filter by run
run_ids = ["All"] + sorted(df["run_id"].unique().tolist())
selected_run = st.sidebar.selectbox("Select Run", run_ids)

if selected_run != "All":
    df = df[df["run_id"] == selected_run]

# Map passed values for display
def verdict_label(val):
    if val == 1:
        return "Passed"
    elif val == 0:
        return "Failed"
    return "Inconclusive"

df["verdict"] = df["passed"].apply(verdict_label)

# --- Summary metrics ---
st.subheader("Summary")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Prompts", len(df))
col2.metric("Passed (Safe)", len(df[df["verdict"] == "Passed"]))
col3.metric("Failed (Unsafe)", len(df[df["verdict"] == "Failed"]))
col4.metric("Inconclusive", len(df[df["verdict"] == "Inconclusive"]))

# --- Verdict breakdown by category ---
st.subheader("Results by Category")
category_counts = df.groupby(["category", "verdict"]).size().unstack(fill_value=0)

# Ensure all columns exist
for col in ["Passed", "Failed", "Inconclusive"]:
    if col not in category_counts.columns:
        category_counts[col] = 0

st.bar_chart(category_counts[["Passed", "Failed", "Inconclusive"]])

# --- Full results table ---
st.subheader("All Results")

# Colour-code verdict column
def colour_verdict(val):
    if val == "Passed":
        return "background-color: #d4edda"
    elif val == "Failed":
        return "background-color: #f8d7da"
    return "background-color: #fff3cd"

display_cols = ["run_id", "category", "prompt_text", "response", "verdict", "reason"]
available_cols = [c for c in display_cols if c in df.columns]

styled = df[available_cols].style.applymap(colour_verdict, subset=["verdict"])
st.dataframe(styled, use_container_width=True)

# --- Failed prompts detail ---
failures = df[df["verdict"] == "Failed"]
if not failures.empty:
    st.subheader(f"Failed Prompts ({len(failures)})")
    for _, row in failures.iterrows():
        with st.expander(f"[{row['category']}] {row['prompt_text'][:80]}..."):
            st.markdown(f"**Prompt:** {row['prompt_text']}")
            st.markdown(f"**Response:** {row['response']}")
            st.markdown(f"**Reason:** {row['reason']}")
