"""
api.py
------
FastAPI backend for the Text-to-SQL pipeline.
Run with: uvicorn api:app --reload
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import sqlite3

from txt_to_sql import build_graph, create_tables, insert_data, load_schema_once, DB_PATH

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Text-to-SQL AI Agent",
    description="Ask questions in plain English and get SQL + results back.",
    version="1.0.0"
)


# ---------------------------------------------------------------------------
# Init pipeline once on startup
# ---------------------------------------------------------------------------
create_tables()
insert_data()
load_schema_once()
# warm up the graph so first request isn't slow
app.state.graph = build_graph()
print("Pipeline ready.")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    sql:         Optional[str]
    result:      Optional[dict]
    explanation: Optional[str]
    error:       Optional[str]
    retries:     int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/")
def root():
    return {"message": "Text-to-SQL API is running. Visit /docs for the interactive UI."}


@app.post("/query", response_model=QueryResponse)
def run_query(payload: QueryRequest):
    """
    Run a natural language question through the LangGraph pipeline.
    Returns the generated SQL, raw results, business explanation, and any errors.
    """
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        state = app.state.graph.invoke({"query": payload.question.strip()})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # result may be a dict (raw rows) or a string (formatted by format_answer node)
    raw = state.get("result")
    result_payload = None
    if isinstance(raw, dict):
        # convert rows (list of tuples) to list of lists for JSON serialisation
        result_payload = {
            "columns": raw.get("columns", []),
            "rows":    [list(row) for row in raw.get("rows", [])]
        }
    elif isinstance(raw, str):
        result_payload = {"formatted": raw}

    return QueryResponse(
        sql=state.get("sql"),
        result=result_payload,
        explanation=state.get("explanation"),
        error=state.get("error") or None,
        retries=state.get("retry_count", 0)
    )


@app.get("/tables")
def get_tables():
    """Return all table names in the database."""
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [row[0] for row in cur.fetchall()]
    conn.close()
    return {"tables": tables}


@app.get("/schema/{table_name}")
def get_table_schema(table_name: str):
    """Return column info for a specific table."""
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    try:
        cur.execute(f"PRAGMA table_info({table_name});")
        columns = [
            {"cid": r[0], "name": r[1], "type": r[2], "notnull": bool(r[3]), "pk": bool(r[5])}
            for r in cur.fetchall()
        ]
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))
    conn.close()
    if not columns:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found.")
    return {"table": table_name, "columns": columns}


@app.get("/preview/{table_name}")
def preview_table(table_name: str, limit: int = 5):
    """Return the first N rows of a table (default 5)."""
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    try:
        cur.execute(f"SELECT * FROM {table_name} LIMIT ?;", (limit,))
        columns = [desc[0] for desc in cur.description]
        rows    = [list(row) for row in cur.fetchall()]
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))
    conn.close()
    return {"table": table_name, "columns": columns, "rows": rows}


@app.get("/health")
def health():
    """Simple health check."""
    return {"status": "ok"}