"""
Publication-quality figures for the research paper.

Generates 5 key figures as high-resolution PNG (300 DPI) + SVG.
Output folder: experiments/iteration3/figures/

Run:
    python experiments/iteration3/generate_figures.py
"""

import os
import sys
import sqlite3
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── Paths ──────────────────────────────────────────────────────────────────────

_HERE      = os.path.dirname(os.path.abspath(__file__))
DB_PATH    = os.path.join(_HERE, "..", "data", "results_method3.db")
OUT_DIR    = os.path.join(_HERE, "..", "figures")
os.makedirs(OUT_DIR, exist_ok=True)

sys.path.insert(0, _HERE)

# ── Run IDs ───────────────────────────────────────────────────────────────────

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

runs = conn.execute(
    "SELECT run_id, target_model, prompt_count FROM runs ORDER BY created_at"
).fetchall()

GPT_RUN_ID   = None
HAIKU_RUN_ID = None
for r in runs:
    if r["prompt_count"] == 488 and "gpt-4o-mini" in r["target_model"] and GPT_RUN_ID is None:
        GPT_RUN_ID = r["run_id"]
    if r["prompt_count"] == 488 and "claude-3.5-haiku" in r["target_model"] and HAIKU_RUN_ID is None:
        HAIKU_RUN_ID = r["run_id"]

assert GPT_RUN_ID,   "GPT-4o-mini full run not found"
assert HAIKU_RUN_ID, "Claude 3.5 Haiku full run not found"

def load(run_id):
    rows = conn.execute(
        "SELECT * FROM evaluations WHERE run_id=?", (run_id,)
    ).fetchall()
    return [dict(r) for r in rows]

gpt_rows   = load(GPT_RUN_ID)
haiku_rows = load(HAIKU_RUN_ID)

N = 488

# ── Design tokens ─────────────────────────────────────────────────────────────

# Colorblind-safe palette (Okabe-Ito)
C_SAFE   = "#009E73"   # green
C_UNSAFE = "#D55E00"   # vermillion
C_INCL   = "#E69F00"   # amber
C_BLUE   = "#0072B2"
C_ORANGE = "#E69F00"

VERDICT_COLORS = [C_SAFE, C_UNSAFE, C_INCL]
VERDICTS       = ["safe", "unsafe", "inconclusive"]

EVAL_KEYS    = ["kw", "lg", "lj", "om"]
EVAL_LABELS  = ["Keyword", "LLaMA Guard 3", "LLM Judge\n(StrongREJECT)", "OpenAI\nModeration"]
EVAL_LABELS_SHORT = ["Keyword", "LLaMA Guard 3", "LLM Judge", "OpenAI Moderation"]

# Global matplotlib style — clean, academic
plt.rcParams.update({
    "font.family":       "DejaVu Sans",
    "font.size":         11,
    "axes.titlesize":    13,
    "axes.labelsize":    11,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.grid":         True,
    "axes.grid.axis":    "y",
    "grid.color":        "#e0e0e0",
    "grid.linewidth":    0.8,
    "legend.frameon":    False,
    "figure.dpi":        150,
})

def save(fig, name):
    png_path = os.path.join(OUT_DIR, f"{name}.png")
    svg_path = os.path.join(OUT_DIR, f"{name}.svg")
    fig.savefig(png_path, dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(svg_path,           bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  saved → {name}.png + .svg")


def verdict_pcts(rows, key):
    col    = f"{key}_verdict"
    counts = Counter(r[col] for r in rows if r.get(col))
    total  = len(rows)
    return {v: counts.get(v, 0) / total * 100 for v in VERDICTS}


# ══════════════════════════════════════════════════════════════════════════════
# Figure 1 — The Core Finding: evaluator verdict distributions (GPT-4o-mini)
# ══════════════════════════════════════════════════════════════════════════════
print("Generating Figure 1 — Core Finding …")

fig, ax = plt.subplots(figsize=(9, 5))

x    = np.arange(len(EVAL_KEYS))
w    = 0.22
offsets = [-w, 0, w]

bars_meta = [
    ("safe",         C_SAFE,   "Safe"),
    ("unsafe",       C_UNSAFE, "Unsafe"),
    ("inconclusive", C_INCL,   "Inconclusive"),
]

for offset, (verdict, color, label) in zip(offsets, bars_meta):
    pcts = [verdict_pcts(gpt_rows, k)[verdict] for k in EVAL_KEYS]
    rects = ax.bar(x + offset, pcts, w, color=color, label=label,
                   edgecolor="white", linewidth=0.5)
    for rect, p in zip(rects, pcts):
        if p > 2:
            ax.text(
                rect.get_x() + rect.get_width() / 2,
                rect.get_height() + 1,
                f"{p:.0f}%", ha="center", va="bottom", fontsize=9, color="#333333"
            )

ax.set_xticks(x)
ax.set_xticklabels(EVAL_LABELS, fontsize=11)
ax.set_ylabel("% of Responses")
ax.set_ylim(0, 115)
ax.set_title(
    "Figure 1 — Evaluator Verdict Distribution on 488 Adversarial Prompts\n"
    "Target model: GPT-4o-mini",
    pad=12, fontsize=13
)
ax.legend(loc="upper right", fontsize=10)

# Annotation: highlight the LLaMA Guard bar
ax.annotate(
    "LLaMA Guard 3 flags\n31% as unsafe while\nothers report <2%",
    xy=(1 + 0, 31), xytext=(2.3, 65),
    fontsize=9, color="#D55E00",
    arrowprops=dict(arrowstyle="->", color="#D55E00", lw=1.2),
    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#D55E00", lw=1),
)

save(fig, "fig1_core_finding")


# ══════════════════════════════════════════════════════════════════════════════
# Figure 2 — Cross-Model Validation: unsafe rate by evaluator × model
# ══════════════════════════════════════════════════════════════════════════════
print("Generating Figure 2 — Cross-Model Validation …")

fig, ax = plt.subplots(figsize=(9, 5))

x = np.arange(len(EVAL_KEYS))
w = 0.32

gpt_unsafe   = [verdict_pcts(gpt_rows,   k)["unsafe"] for k in EVAL_KEYS]
haiku_unsafe = [verdict_pcts(haiku_rows, k)["unsafe"] for k in EVAL_KEYS]

r1 = ax.bar(x - w/2, gpt_unsafe,   w, color=C_BLUE,   label="GPT-4o-mini",      edgecolor="white")
r2 = ax.bar(x + w/2, haiku_unsafe, w, color=C_ORANGE,  label="Claude 3.5 Haiku", edgecolor="white")

for rects, vals in [(r1, gpt_unsafe), (r2, haiku_unsafe)]:
    for rect, p in zip(rects, vals):
        ax.text(
            rect.get_x() + rect.get_width() / 2,
            rect.get_height() + 0.4,
            f"{p:.1f}%", ha="center", va="bottom", fontsize=9, color="#333333"
        )

ax.set_xticks(x)
ax.set_xticklabels(EVAL_LABELS_SHORT, fontsize=11)
ax.set_ylabel("% Classified as Unsafe")
ax.set_ylim(0, 45)
ax.set_title(
    "Figure 2 — LLaMA Guard Outlier Pattern Holds Across Both Target Models\n"
    "Same 488 prompts, same evaluators, different target models",
    pad=12, fontsize=13
)
ax.legend(loc="upper right", fontsize=10)

# Horizontal reference line at LLM judge level
ax.axhline(1.4, color="#009E73", linewidth=1, linestyle="--", alpha=0.7)
ax.text(3.55, 1.8, "LLM Judge\nlevel (≈1%)", fontsize=8.5, color="#009E73", va="bottom")

save(fig, "fig2_cross_model")


# ══════════════════════════════════════════════════════════════════════════════
# Figure 3 — Evaluator Agreement Distribution (both models, side by side)
# ══════════════════════════════════════════════════════════════════════════════
print("Generating Figure 3 — Agreement Distribution …")

AG_LABELS  = ["all_agree", "majority", "split", "all_disagree"]
AG_DISPLAY = ["All agree\n(4/4)", "Majority\n(3+1)", "Split\n(2+2)", "All disagree\n(3 verdicts)"]
AG_COLORS  = ["#009E73", "#0072B2", "#CC79A7", "#D55E00"]

def ag_pcts(rows):
    counts = Counter(r["agreement"] for r in rows)
    total  = len(rows)
    return [counts.get(lbl, 0) / total * 100 for lbl in AG_LABELS]

gpt_ag   = ag_pcts(gpt_rows)
haiku_ag = ag_pcts(haiku_rows)

fig, axes = plt.subplots(1, 2, figsize=(11, 5))

for ax, ag, title in [
    (axes[0], gpt_ag,   "GPT-4o-mini"),
    (axes[1], haiku_ag, "Claude 3.5 Haiku"),
]:
    wedges, texts, autotexts = ax.pie(
        ag, labels=None, colors=AG_COLORS,
        autopct=lambda p: f"{p:.1f}%" if p > 2 else "",
        startangle=90, pctdistance=0.75,
        wedgeprops=dict(edgecolor="white", linewidth=1.5),
    )
    for at in autotexts:
        at.set_fontsize(10)
    ax.set_title(title, fontsize=12, pad=10)

# Shared legend
patches = [mpatches.Patch(color=c, label=l) for c, l in zip(AG_COLORS, AG_DISPLAY)]
fig.legend(handles=patches, loc="lower center", ncol=4, fontsize=10,
           bbox_to_anchor=(0.5, -0.04))
fig.suptitle(
    "Figure 3 — Evaluator Agreement Across 488 Prompts (4-evaluator pipeline)",
    fontsize=13, y=1.01
)

save(fig, "fig3_agreement")


# ══════════════════════════════════════════════════════════════════════════════
# Figure 4 — Top Disagreement Patterns (GPT-4o-mini)
# ══════════════════════════════════════════════════════════════════════════════
print("Generating Figure 4 — Top Disagreement Patterns …")

patterns = Counter(
    r["disagreement_pattern"] for r in gpt_rows
    if r.get("agreement") != "all_agree" and r.get("disagreement_pattern")
)
top10 = patterns.most_common(10)
labels = [p for p, _ in top10]
counts = [c for _, c in top10]

fig, ax = plt.subplots(figsize=(10, 5.5))

colors = [C_UNSAFE if "unsafe" in l.split("|")[1] else C_INCL for l in labels]
bars   = ax.barh(labels[::-1], counts[::-1], color=colors[::-1],
                 edgecolor="white", height=0.6)

for bar, cnt in zip(bars, counts[::-1]):
    ax.text(bar.get_width() + 2, bar.get_y() + bar.get_height() / 2,
            str(cnt), va="center", ha="left", fontsize=10)

ax.set_xlabel("Number of Prompts")
ax.set_xlim(0, max(counts) * 1.15)
ax.set_title(
    "Figure 4 — Top 10 Disagreement Patterns (GPT-4o-mini, 488 prompts)\n"
    "Format: kw=keyword | lg=LLaMA Guard | lj=LLM Judge | om=OpenAI Moderation",
    pad=12, fontsize=12
)

# Color legend
lg_patch  = mpatches.Patch(color=C_UNSAFE, label="LLaMA Guard flags unsafe")
inc_patch = mpatches.Patch(color=C_INCL,   label="LLaMA Guard inconclusive")
ax.legend(handles=[lg_patch, inc_patch], fontsize=9, loc="lower right")

save(fig, "fig4_disagreement_patterns")


# ══════════════════════════════════════════════════════════════════════════════
# Figure 5 — The Gap: evaluator unsafe rates across iterations + both models
# ══════════════════════════════════════════════════════════════════════════════
print("Generating Figure 5 — The Evaluator Gap …")

# Data points from the paper (including Iteration 1 and 2 results)
evaluators = ["Keyword", "LLaMA Guard 3", "LLM Judge\n(StrongREJECT)", "OpenAI\nModeration"]

gpt_vals   = [
    verdict_pcts(gpt_rows,   "kw")["unsafe"],
    verdict_pcts(gpt_rows,   "lg")["unsafe"],
    verdict_pcts(gpt_rows,   "lj")["unsafe"],
    verdict_pcts(gpt_rows,   "om")["unsafe"],
]
haiku_vals = [
    verdict_pcts(haiku_rows, "kw")["unsafe"],
    verdict_pcts(haiku_rows, "lg")["unsafe"],
    verdict_pcts(haiku_rows, "lj")["unsafe"],
    verdict_pcts(haiku_rows, "om")["unsafe"],
]

fig, ax = plt.subplots(figsize=(9, 5))

x  = np.arange(4)
w  = 0.32
r1 = ax.bar(x - w/2, gpt_vals,   w, color=C_BLUE,   label="GPT-4o-mini",      zorder=3)
r2 = ax.bar(x + w/2, haiku_vals, w, color=C_ORANGE,  label="Claude 3.5 Haiku", zorder=3)

for rects, vals in [(r1, gpt_vals), (r2, haiku_vals)]:
    for rect, p in zip(rects, vals):
        ax.text(
            rect.get_x() + rect.get_width() / 2,
            rect.get_height() + 0.3,
            f"{p:.1f}%", ha="center", va="bottom", fontsize=9.5
        )

ax.set_xticks(x)
ax.set_xticklabels(evaluators, fontsize=11)
ax.set_ylabel("% Classified as Unsafe")
ax.set_ylim(0, 42)
ax.set_title(
    "Figure 5 — Unsafe Rate by Evaluator and Target Model\n"
    "Evaluator choice drives reported safety outcomes more than model choice",
    pad=12, fontsize=13
)
ax.legend(loc="upper left", fontsize=10)
ax.set_axisbelow(True)

# Bracket annotation: span of LLaMA Guard
ax.annotate(
    "", xy=(1 + w/2, haiku_vals[1]), xytext=(1 + w/2, gpt_vals[3] + 1),
    arrowprops=dict(arrowstyle="<->", color="#555", lw=1.2)
)
ax.text(1 + w/2 + 0.07, (haiku_vals[1] + gpt_vals[3]) / 2 + 1,
        f"LLaMA Guard\n≈31–34%\nvs ≈0.3–1.4%\nfor others",
        fontsize=8.5, color="#555")

save(fig, "fig5_evaluator_gap")


# ══════════════════════════════════════════════════════════════════════════════
print(f"\nAll figures saved to: {OUT_DIR}/")
print("Files: fig1_core_finding, fig2_cross_model, fig3_agreement,")
print("       fig4_disagreement_patterns, fig5_evaluator_gap")
print("Formats: .png (300 DPI) and .svg (vector)")
