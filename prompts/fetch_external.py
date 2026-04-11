"""
One-time script to download and cache the StrongREJECT and JailbreakBench datasets.

Run once before using loader.py:
    cd experiments/iteration3/prompts
    python fetch_external.py

Produces:
    strongreject.jsonl   — 313 prompts (Souly et al., NeurIPS 2024)
    jailbreakbench.jsonl — 100 prompts (Chao et al., JailbreakBench 2024)
"""

import json
import os

import httpx
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))

_STRONGREJECT_URL = (
    "https://raw.githubusercontent.com/alexandrasouly/strongreject/"
    "main/strongreject_dataset/strongreject_dataset.csv"
)


def _fetch_strongreject() -> None:
    out_path = os.path.join(_HERE, "strongreject.jsonl")
    print("Downloading StrongREJECT dataset ...", flush=True)
    try:
        resp = httpx.get(_STRONGREJECT_URL, timeout=30, follow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        print(f"  ERROR: could not download StrongREJECT — {e}")
        print(f"  Manual download: {_STRONGREJECT_URL}")
        return

    # Parse CSV from the response text
    import io
    df = pd.read_csv(io.StringIO(resp.text))

    required = {"forbidden_prompt", "category"}
    if not required.issubset(df.columns):
        print(f"  ERROR: unexpected columns {list(df.columns)}, expected {required}")
        return

    records = []
    for _, row in df.iterrows():
        records.append({
            "text":     str(row["forbidden_prompt"]).strip(),
            "category": str(row["category"]).strip(),
            "source":   "strongreject",
        })

    with open(out_path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    print(f"  Saved {len(records)} prompts → {out_path}")


def _fetch_jailbreakbench() -> None:
    # JailbreakBench behaviors are hosted on HuggingFace: dedeswim/JBB-Behaviors
    # split="harmful" gives the 100 adversarial goal prompts
    out_path = os.path.join(_HERE, "jailbreakbench.jsonl")
    print("Downloading JailbreakBench dataset (HuggingFace: dedeswim/JBB-Behaviors) ...", flush=True)
    try:
        from datasets import load_dataset
        ds = load_dataset("dedeswim/JBB-Behaviors", "behaviors", split="harmful")
        df = ds.to_pandas()
    except ImportError:
        print("  ERROR: 'datasets' package not installed. Run: uv sync")
        return
    except Exception as e:
        print(f"  ERROR: could not load JailbreakBench — {e}")
        return

    df.columns = [c.lower() for c in df.columns]

    if "goal" not in df.columns:
        print(f"  ERROR: unexpected columns {list(df.columns)}, expected 'goal'")
        return

    records = []
    for _, row in df.iterrows():
        records.append({
            "text":     str(row["goal"]).strip(),
            "category": str(row.get("category", "unknown")).strip(),
            "source":   "jailbreakbench",
        })

    with open(out_path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    print(f"  Saved {len(records)} prompts → {out_path}")


if __name__ == "__main__":
    _fetch_strongreject()
    _fetch_jailbreakbench()
    print("\nDone. Run loader.py to verify totals.")
