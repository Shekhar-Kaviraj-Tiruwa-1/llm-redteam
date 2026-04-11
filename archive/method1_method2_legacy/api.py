# FastAPI server exposing evaluation results from the database
# Run: uvicorn api:app --reload

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from database import init_db, get_results


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise the database on startup."""
    init_db()
    yield


app = FastAPI(
    title="LLM Red Team API",
    description="Query adversarial evaluation results",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "LLM Red Team API is running"}


@app.get("/results")
def all_results():
    """Return all evaluation results across all runs."""
    rows = get_results()
    return {"count": len(rows), "results": rows}


@app.get("/results/{run_id}")
def results_by_run(run_id: str):
    """Return all results for a specific run_id."""
    rows = get_results(run_id=run_id)
    if not rows:
        raise HTTPException(status_code=404, detail=f"No results found for run_id: {run_id}")
    return {"run_id": run_id, "count": len(rows), "results": rows}


@app.get("/summary/{run_id}")
def summary_by_run(run_id: str):
    """Return a pass/fail/inconclusive summary for a specific run."""
    rows = get_results(run_id=run_id)
    if not rows:
        raise HTTPException(status_code=404, detail=f"No results found for run_id: {run_id}")

    passed = sum(1 for r in rows if r["passed"] == 1)
    failed = sum(1 for r in rows if r["passed"] == 0)
    inconclusive = sum(1 for r in rows if r["passed"] is None)
    total = len(rows)

    # Break down by category
    categories = {}
    for r in rows:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"passed": 0, "failed": 0, "inconclusive": 0}
        if r["passed"] == 1:
            categories[cat]["passed"] += 1
        elif r["passed"] == 0:
            categories[cat]["failed"] += 1
        else:
            categories[cat]["inconclusive"] += 1

    return {
        "run_id": run_id,
        "model": rows[0]["model"],
        "total": total,
        "passed": passed,
        "failed": failed,
        "inconclusive": inconclusive,
        "by_category": categories,
    }
