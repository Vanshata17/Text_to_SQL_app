"""
Streamlit Frontend - Text-to-SQL AI Agent Interface
====================================================
A web-based interface for querying databases using natural language. This module
provides a Streamlit UI that communicates with a FastAPI backend to convert
plain English questions into SQL queries and display results.
Architecture:
    - Streamlit frontend: Interactive UI for user queries and schema exploration
    - FastAPI backend: Processes queries and executes SQL (runs separately)
    - Communication: HTTP REST API calls to /tables, /schema, /preview, /query, /health endpoints
Key Features:
    1. Natural Language Query Input
       - Users ask questions in plain English
       - Submitted via POST to /query endpoint
       - Results cached in session state
    2. Schema Browser (Sidebar)
       - Lists all available database tables (/tables endpoint)
       - Shows column definitions, types, and constraints for selected table (/schema endpoint)
       - Provides preview of table data (/preview endpoint)
       - Cached using @st.cache_data to reduce API calls
    3. Query Suggestions
       - Sidebar presents example queries for inspiration
       - Clicking examples pre-fills the query input field
       - Uses session state to maintain input value
    4. Results Display
       - Metrics: row count, column count, retry attempts
       - Generated SQL code block for transparency
       - Results table as interactive DataFrame
       - Business explanation of results
       - Error messages if query fails
    5. API Health Monitoring
       - Real-time backend status check (/health endpoint)
       - User-friendly status indicators (success/error)
       - Displays API endpoint URL for debugging
Dependencies:
    - streamlit: Web UI framework
    - pandas: Data manipulation and display
    - requests: HTTP client for API communication
Configuration:
    - Page title: "Text-to-SQL AI Agent"
    - Page icon: 🧠
    - Layout: wide
    - API base URL: http://localhost:8000
Prerequisites:
    - FastAPI backend must be running: uvicorn api:app --reload
    - Backend must implement endpoints: /tables, /schema/{table}, /preview/{table}, /query, /health
Usage:
    1. Start FastAPI backend in separate terminal
    2. Run: streamlit run app.py
    3. Access UI in browser (default: http://localhost:8501)
    4. Enter questions or select example queries from sidebar
app.py
------
Streamlit frontend — calls FastAPI backend instead of pipeline directly.
Start backend first:  uvicorn api:app --reload
Then run:             streamlit run app.py
"""

import os

import streamlit as st
import pandas as pd
import requests

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Text-to-SQL AI Agent",
    page_icon="🧠",
    layout="wide"
)

# ---------------------------------------------------------------------------
# Helper — fetch table list from API
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def fetch_tables():
    try:
        res = requests.get(f"{API_BASE}/tables", timeout=5)
        return res.json().get("tables", [])
    except Exception:
        return []

@st.cache_data(show_spinner=False)
def fetch_schema(table: str):
    try:
        res = requests.get(f"{API_BASE}/schema/{table}", timeout=5)
        return res.json().get("columns", [])
    except Exception:
        return []

@st.cache_data(show_spinner=False)
def fetch_preview(table: str):
    try:
        res = requests.get(f"{API_BASE}/preview/{table}", timeout=5)
        data = res.json()
        return data.get("columns", []), data.get("rows", [])
    except Exception:
        return [], []

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("💡 Example Queries")
    examples = [
        "Show each customer's name, total orders, and total spend",
        "Rank customers by total spend using RANK()",
        "Top-selling product per category by revenue",
        "Show running total of orders by date",
        "Customers who ordered from more than one category",
        "Rank products by average review rating per category",
        "Show all shipments with customer name and status",
        "Each customer's order amounts with previous order using LAG()",
    ]
    for ex in examples:
        if st.button(ex, use_container_width=True, key=ex):
            st.session_state.query_input = ex

    st.divider()

    # Live schema browser powered by the API
    st.header("📋 Schema Browser")
    tables = fetch_tables()
    if tables:
        selected_table = st.selectbox("Choose a table", tables)
        if selected_table:
            cols = fetch_schema(selected_table)
            if cols:
                col_df = pd.DataFrame(cols)[["name", "type", "pk", "notnull"]]
                col_df.columns = ["Column", "Type", "PK", "Not Null"]
                st.dataframe(col_df, use_container_width=True, hide_index=True)

            if st.button("Preview rows", use_container_width=True):
                columns, rows = fetch_preview(selected_table)
                if rows:
                    st.dataframe(
                        pd.DataFrame(rows, columns=columns),
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("No rows found.")
    else:
        st.warning("API not reachable. Start the backend first.")

    st.divider()

    # API health indicator
    st.header("🔌 API Status")
    try:
        health = requests.get(f"{API_BASE}/health", timeout=3)
        if health.status_code == 200:
            st.success("Backend is running")
        else:
            st.error("Backend returned an error")
    except Exception:
        st.error("Backend not reachable")
    st.caption(f"Endpoint: `{API_BASE}`")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
st.title("🧠 Text-to-SQL AI Agent")
st.caption("Ask a question in plain English — FastAPI runs the pipeline and returns the results.")
st.divider()

# ---------------------------------------------------------------------------
# Query input
# ---------------------------------------------------------------------------
query = st.text_input(
    "Ask your database:",
    placeholder="e.g. Which customers spent the most in 2024?",
    key="query_input"
)

col_run, col_clear, _ = st.columns([1, 1, 6])
with col_run:
    run = st.button("▶ Run Query", type="primary", use_container_width=True)
with col_clear:
    if st.button("✕ Clear", use_container_width=True):
        st.session_state.query_input = ""
        st.session_state.pop("last_result", None)
        st.rerun()

# ---------------------------------------------------------------------------
# Call FastAPI
# ---------------------------------------------------------------------------
if run and query.strip():
    with st.spinner("Calling API..."):
        try:
            response = requests.post(
                f"{API_BASE}/query",
                json={"question": query.strip()},
                timeout=60
            )
            if response.status_code == 200:
                st.session_state.last_result = response.json()
            else:
                st.error(f"API error {response.status_code}: {response.json().get('detail')}")
        except requests.exceptions.ConnectionError:
            st.error("Cannot reach the API. Make sure you ran: `uvicorn api:app --reload`")
        except Exception as e:
            st.error(f"Unexpected error: {e}")

# ---------------------------------------------------------------------------
# Display results
# ---------------------------------------------------------------------------
if "last_result" in st.session_state:
    data = st.session_state.last_result

    st.divider()

    # ── Metrics ──────────────────────────────────────────────────────────
    raw       = data.get("result") or {}
    rows      = raw.get("rows", [])
    columns   = raw.get("columns", [])
    row_count = len(rows) if rows else "—"
    col_count = len(columns) if columns else "—"
    retries   = data.get("retries", 0)

    m1, m2, m3 = st.columns(3)
    m1.metric("Rows returned", row_count)
    m2.metric("Columns", col_count)
    m3.metric("SQL retries", retries)

    st.divider()

    # ── Generated SQL ─────────────────────────────────────────────────────
    sql = data.get("sql", "")
    if sql:
        st.subheader("🔧 Generated SQL")
        st.code(sql, language="sql")

    # ── Error ─────────────────────────────────────────────────────────────
    error = data.get("error")
    if error:
        st.error(f"⚠ {error}")

    # ── Results table ─────────────────────────────────────────────────────
    if rows and columns:
        st.subheader("📊 Query Results")
        df = pd.DataFrame(rows, columns=columns)
        st.dataframe(df, use_container_width=True, hide_index=True)
    elif raw.get("formatted"):
        st.subheader("📊 Formatted Answer")
        st.info(raw["formatted"])
    elif not error:
        st.warning("No results found.")

    # ── Business explanation ──────────────────────────────────────────────
    explanation = data.get("explanation", "")
    if explanation:
        st.subheader("💼 Business Explanation")
        st.success(explanation)
