"""
app.py
------
Streamlit frontend for the Text-to-SQL pipeline.
Run with: streamlit run app.py
"""

import streamlit as st
import pandas as pd
from txt_to_sql import build_graph, create_tables, insert_data, load_schema_once

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Text-to-SQL AI Agent",
    page_icon="🧠",
    layout="wide"
)

# ---------------------------------------------------------------------------
# Init pipeline once per session
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner="Setting up database and pipeline...")
def init_pipeline():
    create_tables()
    insert_data()
    load_schema_once()
    return build_graph()

graph = init_pipeline()

# ---------------------------------------------------------------------------
# Sidebar — example queries + schema
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

    st.header("📋 Schema Tables")
    for table in ["customers", "orders", "order_items", "products",
                  "categories", "inventory", "payments", "shipments",
                  "reviews", "warehouses"]:
        st.code(table)

# ---------------------------------------------------------------------------
# Main — title
# ---------------------------------------------------------------------------
st.title("🧠 Text-to-SQL AI Agent")
st.caption("Ask a question in plain English and get SQL, results, and a business explanation.")
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
# Run pipeline
# ---------------------------------------------------------------------------
if run and query.strip():
    with st.spinner("Running pipeline..."):
        try:
            state = graph.invoke({"query": query.strip()})
            st.session_state.last_result = state
        except Exception as e:
            st.error(f"Pipeline error: {e}")

# ---------------------------------------------------------------------------
# Display results
# ---------------------------------------------------------------------------
if "last_result" in st.session_state:
    state = st.session_state.last_result

    st.divider()

    # ── Metrics ──────────────────────────────────────────────────────────
    raw = state.get("result")
    row_count = len(raw["rows"]) if isinstance(raw, dict) else "—"
    col_count = len(raw["columns"]) if isinstance(raw, dict) else "—"
    retries   = state.get("retry_count", 0)

    m1, m2, m3 = st.columns(3)
    m1.metric("Rows returned", row_count)
    m2.metric("Columns", col_count)
    m3.metric("SQL retries", retries)

    st.divider()

    # ── Generated SQL ─────────────────────────────────────────────────────
    sql = state.get("sql", "")
    if sql:
        st.subheader("🔧 Generated SQL")
        st.code(sql, language="sql")

    # ── Error ─────────────────────────────────────────────────────────────
    error = state.get("error", "")
    if error:
        st.error(f"⚠ {error}")

    # ── Results table ─────────────────────────────────────────────────────
    if isinstance(raw, dict) and raw.get("rows"):
        st.subheader("📊 Query Results")
        df = pd.DataFrame(raw["rows"], columns=raw["columns"])
        st.dataframe(df, use_container_width=True, hide_index=True)
    elif isinstance(raw, str):
        st.subheader("📊 Formatted Answer")
        st.info(raw)
    elif not error:
        st.warning("No results found.")

    # ── Business explanation ──────────────────────────────────────────────
    explanation = state.get("explanation", "")
    if explanation:
        st.subheader("💼 Business Explanation")
        st.success(explanation)
