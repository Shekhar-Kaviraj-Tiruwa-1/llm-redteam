"""
SQLite storage for Iteration 3 triple-evaluator results.

Schema:
  runs        — one row per pipeline run (metadata)
  evaluations — one row per prompt, with all three evaluator verdicts stored flat

WAL mode enabled for safe concurrent writes (same as database.py).
DB is stored at experiments/iteration3/results_v3.db by default.
"""

import json
import os
import sqlite3

_HERE   = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv("DB_PATH", os.path.join(_HERE, "..", "data", "results_method3.db"))


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist. Safe to call on every run."""
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id        TEXT PRIMARY KEY,
            target_model  TEXT NOT NULL,
            judge_model   TEXT NOT NULL,
            sources       TEXT NOT NULL,   -- JSON list: ["custom","strongreject",...]
            prompt_count  INTEGER,
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS evaluations (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id               TEXT    NOT NULL,
            prompt_idx           INTEGER NOT NULL,
            prompt_text          TEXT    NOT NULL,
            category             TEXT    NOT NULL,
            source               TEXT    NOT NULL,   -- custom / strongreject / jailbreakbench
            response             TEXT    NOT NULL,

            -- Keyword evaluator (v2)
            kw_verdict           TEXT,               -- safe / unsafe / inconclusive
            kw_score             REAL,
            kw_summary           TEXT,

            -- LLaMA Guard 3
            lg_verdict           TEXT,
            lg_score             REAL,
            lg_summary           TEXT,

            -- LLM Judge (StrongREJECT rubric)
            lj_verdict           TEXT,
            lj_score             REAL,
            lj_reasoning         TEXT,
            lj_summary           TEXT,

            -- OpenAI Moderation API (omni-moderation-latest)
            om_verdict           TEXT,               -- safe / unsafe / inconclusive
            om_score             REAL,
            om_summary           TEXT,

            -- Agreement across all four evaluators
            agreement            TEXT,               -- all_agree / majority / split / all_disagree
            disagreement_pattern TEXT,               -- e.g. "kw=safe|lg=unsafe|lj=safe|om=safe"

            created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (run_id) REFERENCES runs(run_id)
        );

        CREATE INDEX IF NOT EXISTS idx_evals_run   ON evaluations(run_id);
        CREATE INDEX IF NOT EXISTS idx_evals_cat   ON evaluations(category);
        CREATE INDEX IF NOT EXISTS idx_evals_agree ON evaluations(agreement);
    """)
    conn.commit()
    # Migrate existing databases that predate the om_* columns
    _migrate_add_om_columns(conn)
    conn.close()


def _migrate_add_om_columns(conn: sqlite3.Connection) -> None:
    """Add om_* columns to evaluations if they don't exist (safe to re-run)."""
    for col, coltype in [("om_verdict", "TEXT"), ("om_score", "REAL"), ("om_summary", "TEXT")]:
        try:
            conn.execute(f"ALTER TABLE evaluations ADD COLUMN {col} {coltype}")
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.commit()


def save_run(run_id: str, target_model: str, judge_model: str, sources: list[str], prompt_count: int) -> None:
    conn = _connect()
    conn.execute(
        "INSERT OR REPLACE INTO runs (run_id, target_model, judge_model, sources, prompt_count) VALUES (?,?,?,?,?)",
        (run_id, target_model, judge_model, json.dumps(sources), prompt_count),
    )
    conn.commit()
    conn.close()


def save_evaluation(
    run_id:       str,
    prompt_idx:   int,
    prompt_text:  str,
    category:     str,
    source:       str,
    response:     str,
    kw_verdict:   str, kw_score: float, kw_summary: str,
    lg_verdict:   str, lg_score: float, lg_summary: str,
    lj_verdict:   str, lj_score: float, lj_reasoning: str, lj_summary: str,
    om_verdict:   str, om_score: float, om_summary: str,
    agreement:    str,
    disagreement_pattern: str,
) -> None:
    conn = _connect()
    conn.execute("""
        INSERT INTO evaluations (
            run_id, prompt_idx, prompt_text, category, source, response,
            kw_verdict, kw_score, kw_summary,
            lg_verdict, lg_score, lg_summary,
            lj_verdict, lj_score, lj_reasoning, lj_summary,
            om_verdict, om_score, om_summary,
            agreement, disagreement_pattern
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        run_id, prompt_idx, prompt_text, category, source, response,
        kw_verdict, kw_score, kw_summary,
        lg_verdict, lg_score, lg_summary,
        lj_verdict, lj_score, lj_reasoning, lj_summary,
        om_verdict, om_score, om_summary,
        agreement, disagreement_pattern,
    ))
    conn.commit()
    conn.close()


def get_run_summary(run_id: str) -> dict:
    """Return verdict counts and disagreement stats for a run."""
    conn  = _connect()
    rows  = conn.execute(
        "SELECT * FROM evaluations WHERE run_id = ? ORDER BY prompt_idx", (run_id,)
    ).fetchall()
    conn.close()

    if not rows:
        return {}

    from collections import Counter
    kw_counts = Counter(r["kw_verdict"] for r in rows)
    lg_counts = Counter(r["lg_verdict"] for r in rows)
    lj_counts = Counter(r["lj_verdict"] for r in rows)
    om_counts = Counter(r["om_verdict"] for r in rows)
    ag_counts = Counter(r["agreement"]  for r in rows)

    return {
        "run_id":             run_id,
        "total":              len(rows),
        "keyword":            dict(kw_counts),
        "llamaguard":         dict(lg_counts),
        "llm_judge":          dict(lj_counts),
        "openai_moderation":  dict(om_counts),
        "agreement":          dict(ag_counts),
    }


def get_disagreements(run_id: str) -> list[dict]:
    """Return all rows where evaluators did not all agree."""
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM evaluations WHERE run_id = ? AND agreement != 'all_agree' ORDER BY prompt_idx",
        (run_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
