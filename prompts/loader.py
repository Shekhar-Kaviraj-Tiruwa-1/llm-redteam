"""
Unified prompt loader for Iteration 3.

Returns all prompts as a list of dicts:
    {"text": str, "category": str, "source": str}

Sources:
    "custom"         — 75 prompts from our Iteration 1/2 prompt files
    "strongreject"   — 313 prompts (Souly et al., NeurIPS 2024)
    "jailbreakbench" — 100 prompts (Chao et al., JailbreakBench 2024)

Usage:
    from prompts.loader import load_prompts

    all_prompts   = load_prompts()
    custom_only   = load_prompts(sources=["custom"])
    external_only = load_prompts(sources=["strongreject", "jailbreakbench"])
    by_category   = load_prompts(category="jailbreak")
"""

import json
import os
import sys
from typing import Optional

# Add prompts/ to path so custom.X resolves to prompts/custom/X.py
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

_CUSTOM_MODULES = [
    "custom.data_leakage",
    "custom.hallucination",
    "custom.injections",
    "custom.jailbreaks",
    "custom.role_play",
]

_EXTERNAL_FILES = {
    "strongreject":   os.path.join(_HERE, "strongreject.jsonl"),
    "jailbreakbench": os.path.join(_HERE, "jailbreakbench.jsonl"),
}


def _load_custom() -> list[dict]:
    records = []
    for module_name in _CUSTOM_MODULES:
        mod = __import__(module_name, fromlist=["CATEGORY", "PROMPTS"])
        for text in mod.PROMPTS:
            records.append({
                "text":     text.strip(),
                "category": mod.CATEGORY,
                "source":   "custom",
            })
    return records


def _load_jsonl(source: str) -> list[dict]:
    path = _EXTERNAL_FILES[source]
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{source}.jsonl not found. Run fetch_external.py first:\n"
            f"  cd experiments/iteration3/prompts && python fetch_external.py"
        )
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def load_prompts(
    sources:  Optional[list[str]] = None,
    category: Optional[str]       = None,
) -> list[dict]:
    """
    Load and return prompts from the requested sources.

    Args:
        sources:  Which sources to include. Defaults to all three.
                  Options: "custom", "strongreject", "jailbreakbench"
        category: If set, filter to only prompts matching this category string.

    Returns:
        List of {"text": str, "category": str, "source": str} dicts.
    """
    if sources is None:
        sources = ["custom", "strongreject", "jailbreakbench"]

    records: list[dict] = []

    for source in sources:
        if source == "custom":
            records.extend(_load_custom())
        elif source in _EXTERNAL_FILES:
            records.extend(_load_jsonl(source))
        else:
            raise ValueError(f"Unknown source '{source}'. Valid: custom, strongreject, jailbreakbench")

    if category:
        records = [r for r in records if r["category"] == category]

    return records


def summary(prompts: list[dict]) -> str:
    """Return a human-readable breakdown by source and category."""
    from collections import Counter
    by_source   = Counter(r["source"]   for r in prompts)
    by_category = Counter(r["category"] for r in prompts)
    lines = [f"Total: {len(prompts)} prompts"]
    lines.append("\nBy source:")
    for src, n in sorted(by_source.items()):
        lines.append(f"  {src:<16} {n}")
    lines.append("\nBy category (top 10):")
    for cat, n in by_category.most_common(10):
        lines.append(f"  {cat:<24} {n}")
    return "\n".join(lines)


if __name__ == "__main__":
    # Quick smoke-test: load custom prompts only (no network needed)
    custom = load_prompts(sources=["custom"])
    print(summary(custom))
    print()

    # Try external datasets if they've been fetched
    try:
        all_prompts = load_prompts()
        print(summary(all_prompts))
    except FileNotFoundError as e:
        print(f"External datasets not yet fetched:\n  {e}")
