"""
txt_to_sql.py
-------------
Text-to-SQL pipeline using LangGraph, ChromaDB, OpenAI, and SQLite.
Rich sample data included to demonstrate complex JOINs and window functions.
"""

import os
import sqlite3
from typing import TypedDict

import chromadb
from chromadb.config import Settings
from langgraph.graph import StateGraph, END
from openai import OpenAI

# --------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
os.environ["OPENAI_API_KEY"] = "sk-..."  # Replace with your OpenAI API key

openai_client = OpenAI()

# Persistent Chroma DB (saved locally)
chroma_client = chromadb.Client(
    Settings(persist_directory="./chroma_db")
)

collection = chroma_client.get_or_create_collection(name="schema_collection")

DB_PATH = "txt_to_sql.db"


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------
def create_tables():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS customers (
        customer_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        name             TEXT,
        email            TEXT,
        phone            TEXT,
        city             TEXT,
        country          TEXT,
        signup_date      DATE,
        customer_segment TEXT
    );

    CREATE TABLE IF NOT EXISTS categories (
        category_id        INTEGER PRIMARY KEY AUTOINCREMENT,
        category_name      TEXT,
        parent_category_id INT
    );

    CREATE TABLE IF NOT EXISTS products (
        product_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        name          TEXT,
        category_id   INT,
        brand         TEXT,
        cost_price    NUMERIC,
        selling_price NUMERIC
    );

    CREATE TABLE IF NOT EXISTS orders (
        order_id     INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id  INT REFERENCES customers(customer_id),
        order_date   TIMESTAMP,
        status       TEXT,
        total_amount NUMERIC
    );

    CREATE TABLE IF NOT EXISTS order_items (
        order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id      INT REFERENCES orders(order_id),
        product_id    INT,
        quantity      INT,
        price         NUMERIC
    );

    CREATE TABLE IF NOT EXISTS payments (
        payment_id       INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id         INT,
        payment_method   TEXT,
        payment_status   TEXT,
        transaction_date TIMESTAMP,
        amount           NUMERIC
    );

    CREATE TABLE IF NOT EXISTS warehouses (
        warehouse_id INTEGER PRIMARY KEY AUTOINCREMENT,
        location     TEXT,
        capacity     INT
    );

    CREATE TABLE IF NOT EXISTS inventory (
        inventory_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id     INT,
        warehouse_id   INT,
        stock_quantity INT,
        reorder_level  INT,
        last_updated   TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS shipments (
        shipment_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id      INT,
        warehouse_id  INT,
        shipment_date TIMESTAMP,
        delivery_date TIMESTAMP,
        status        TEXT
    );

    CREATE TABLE IF NOT EXISTS reviews (
        review_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INT,
        product_id  INT,
        rating      INT,
        review_text TEXT,
        review_date TIMESTAMP
    );
    """)

    conn.commit()
    conn.close()
    print("Tables created")


# ---------------------------------------------------------------------------
# Rich sample data  — enough rows for JOINs, GROUP BY, and window functions
# ---------------------------------------------------------------------------
def insert_data():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # ── CUSTOMERS (15 rows) ────────────────────────────────────────────────
    cur.executemany(
        "INSERT INTO customers (name, email, phone, city, country, signup_date, customer_segment) VALUES (?,?,?,?,?,?,?)",
        [
            ("Rahul Sharma",     "rahul@gmail.com",     "9876543210",  "Delhi",      "India",     "2022-03-10", "Premium"),
            ("Ananya Verma",     "ananya@gmail.com",    "9123456780",  "Mumbai",     "India",     "2022-06-15", "Standard"),
            ("John Doe",         "john@example.com",    "1234567890",  "New York",   "USA",       "2021-11-20", "Premium"),
            ("Priya Nair",       "priya@yahoo.com",     "9988776655",  "Bangalore",  "India",     "2022-08-01", "Standard"),
            ("Carlos Mendez",    "carlos@mail.com",     "5551234567",  "Mexico City","Mexico",    "2023-01-05", "Gold"),
            ("Sophie Laurent",   "sophie@mail.fr",      "0612345678",  "Paris",      "France",    "2023-02-14", "Premium"),
            ("Aiko Tanaka",      "aiko@jp.com",         "0901234567",  "Tokyo",      "Japan",     "2022-12-20", "Gold"),
            ("Liam OBrien",      "liam@ie.com",         "0871234567",  "Dublin",     "Ireland",   "2023-03-30", "Standard"),
            ("Fatima Al-Hassan", "fatima@ae.com",       "0501234567",  "Dubai",      "UAE",       "2021-07-18", "Premium"),
            ("Chen Wei",         "chenwei@cn.com",      "1381234567",  "Shanghai",   "China",     "2022-04-22", "Gold"),
            ("Neha Joshi",       "neha@gmail.com",      "9871234560",  "Pune",       "India",     "2023-05-10", "Standard"),
            ("David Kim",        "dkim@us.com",         "2125550100",  "Los Angeles","USA",       "2022-09-09", "Premium"),
            ("Maria Gonzalez",   "maria@es.com",        "0034612345",  "Madrid",     "Spain",     "2023-07-07", "Standard"),
            ("Omar Farooq",      "omar@pk.com",         "03001234567", "Karachi",    "Pakistan",  "2022-01-25", "Gold"),
            ("Elena Ivanova",    "elena@ru.com",        "9161234567",  "Moscow",     "Russia",    "2021-10-30", "Premium"),
        ]
    )

    # ── CATEGORIES  (5 parent + 5 child) ──────────────────────────────────
    cur.executemany(
        "INSERT INTO categories (category_name, parent_category_id) VALUES (?,?)",
        [
            ("Electronics",    None),   # 1
            ("Clothing",       None),   # 2
            ("Home & Kitchen", None),   # 3
            ("Sports",         None),   # 4
            ("Books",          None),   # 5
            ("Smartphones",    1),      # 6  child of Electronics
            ("Laptops",        1),      # 7
            ("Accessories",    1),      # 8
            ("Mens Wear",      2),      # 9
            ("Womens Wear",    2),      # 10
        ]
    )

    # ── PRODUCTS (20 rows) ─────────────────────────────────────────────────
    cur.executemany(
        "INSERT INTO products (name, category_id, brand, cost_price, selling_price) VALUES (?,?,?,?,?)",
        [
            ("iPhone 15 Pro",       6,  "Apple",      85000, 95000),
            ("Samsung Galaxy S24",  6,  "Samsung",    70000, 80000),
            ("OnePlus 12",          6,  "OnePlus",    55000, 62000),
            ("MacBook Air M3",      7,  "Apple",     100000,120000),
            ("Dell XPS 15",         7,  "Dell",       90000,105000),
            ("Lenovo ThinkPad X1",  7,  "Lenovo",     85000, 98000),
            ("AirPods Pro",         8,  "Apple",      18000, 25000),
            ("Sony WH-1000XM5",     8,  "Sony",       22000, 30000),
            ("USB-C Hub",           8,  "Anker",       1500,  3000),
            ("Mens Polo T-Shirt",   9,  "Nike",          600,  1200),
            ("Mens Slim Jeans",     9,  "Levis",        1800,  3500),
            ("Womens Kurta",       10,  "Biba",         1200,  2400),
            ("Womens Jacket",      10,  "Zara",         3500,  7000),
            ("Instant Pot",         3,  "InstantPot",  6000,  9000),
            ("Air Fryer",           3,  "Philips",     5500,  8500),
            ("Yoga Mat",            4,  "Adidas",        800,  1800),
            ("Running Shoes",       4,  "Nike",         3500,  6500),
            ("Python Crash Course", 5,  "No Starch",     400,   700),
            ("Atomic Habits",       5,  "Avery",         300,   550),
            ("The Lean Startup",    5,  "Crown",         350,   600),
        ]
    )

    # ── ORDERS (30 rows) ───────────────────────────────────────────────────
    cur.executemany(
        "INSERT INTO orders (customer_id, order_date, status, total_amount) VALUES (?,?,?,?)",
        [
            ( 1, "2024-01-05", "Delivered",   95000),
            ( 2, "2024-04-10", "Shipped",      3500),
            ( 3, "2024-02-14", "Delivered",  120000),
            ( 3, "2024-05-01", "Processing",  25000),
            ( 4, "2024-02-28", "Delivered",    9000),
            ( 4, "2024-06-12", "Delivered",    2400),
            ( 5, "2024-03-03", "Delivered",   80000),
            ( 5, "2024-07-19", "Shipped",      6500),
            ( 6, "2024-01-11", "Delivered",   30000),
            ( 6, "2024-04-22", "Delivered",    7000),
            ( 7, "2024-05-15", "Delivered",    8500),
            ( 8, "2024-03-25", "Cancelled",    1800),
            ( 8, "2024-06-30", "Delivered",     700),
            ( 9, "2024-01-30", "Delivered",   98000),
            ( 9, "2024-04-05", "Delivered",    3000),
            (10, "2024-02-19", "Delivered",  105000),
            (10, "2024-07-01", "Shipped",      1800),
            (11, "2024-03-14", "Delivered",    2400),
            (12, "2024-01-08", "Delivered",   95000),
            (12, "2024-05-27", "Processing",  30000),
            (13, "2024-04-16", "Delivered",    1200),
            (14, "2024-02-02", "Delivered",   80000),
            (14, "2024-06-09", "Delivered",    9000),
            (15, "2024-01-22", "Delivered",  120000),
            (15, "2024-05-11", "Delivered",   25000),
            ( 3, "2024-07-20", "Delivered",     600),
        ]
    )

    # ── ORDER ITEMS (44 rows) ──────────────────────────────────────────────
    cur.executemany(
        "INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?,?,?,?)",
        [
            ( 1,  1, 1,  95000),
            ( 1,  7, 1,  25000),
            ( 1,  9, 1,   3000),
            ( 2,  7, 1,  25000),
            ( 2, 18, 2,    700),
            ( 3, 12, 1,   1200),
            ( 4, 11, 1,   3500),
            ( 5,  4, 1, 120000),
            ( 5,  9, 1,   3000),
            ( 6,  7, 1,  25000),
            ( 6, 19, 1,    550),
            ( 7, 14, 1,   9000),
            ( 8, 12, 1,   2400),
            ( 9,  2, 1,  80000),
            ( 9,  7, 1,  25000),
            (10, 17, 1,   6500),
            (11,  7, 1,  25000),
            (12, 13, 1,   7000),
            (13,  3, 1,  62000),
            (13,  7, 1,  25000),
            (14, 15, 1,   8500),
            (19,  5, 1, 105000),
            (19,  8, 1,  30000),
            (20, 10, 2,   1800),
            (21, 12, 1,   2400),
            (22, 19, 1,    550),
            (23,  1, 1,  95000),
            (23,  7, 1,  25000),
            (24,  8, 1,  30000),
            (25, 12, 1,   1200),
            (26,  2, 1,  80000),
            (27, 14, 1,   9000),
            (28,  4, 1, 120000),
            (28,  8, 1,  30000),
            (29,  7, 1,  25000),
            (30, 10, 1,    600),
            (10, 20, 1,    600),
        ]
    )

    # ── PAYMENTS (30 rows, one per order) ─────────────────────────────────
    cur.executemany(
        "INSERT INTO payments (order_id, payment_method, payment_status, transaction_date, amount) VALUES (?,?,?,datetime('now'),?)",
        [
            ( 1, "UPI",        "Completed",  95000),
            ( 2, "Card",       "Completed",  25000),
            ( 3, "UPI",        "Completed",   1200),
            ( 4, "NetBanking", "Pending",     3500),
            ( 5, "Card",       "Completed", 120000),
            ( 6, "UPI",        "Pending",    25000),
            ( 7, "Cash",       "Completed",   9000),
            ( 8, "UPI",        "Completed",   2400),
            ( 9, "Card",       "Completed",  80000),
            (10, "NetBanking", "Pending",     6500),
            (11, "Card",       "Completed",  30000),
            (12, "UPI",        "Completed",   7000),
            (13, "Card",       "Completed",  62000),
            (14, "UPI",        "Completed",   8500),
            (15, "NetBanking", "Failed",      1800),
            (16, "UPI",        "Completed",    700),
            (17, "Card",       "Completed",  98000),
            (18, "UPI",        "Completed",   3000),
            (19, "Card",       "Completed", 105000),
            (20, "NetBanking", "Pending",     1800),
        ]
    )

    # ── WAREHOUSES (4 rows) ────────────────────────────────────────────────
    cur.executemany(
        "INSERT INTO warehouses (location, capacity) VALUES (?,?)",
        [
            ("Delhi",     2000),
            ("Mumbai",    1500),
            ("Bangalore", 1200),
            ("Kolkata",    800),
        ]
    )

    # ── INVENTORY (20 rows) ────────────────────────────────────────────────
    cur.executemany(
        "INSERT INTO inventory (product_id, warehouse_id, stock_quantity, reorder_level, last_updated) VALUES (?,?,?,?,datetime('now'))",
        [
            ( 1, 1,  30,  5),
            ( 2, 1,  45,  5),
            ( 3, 2,  60, 10),
            ( 4, 1,  15,  3),
            ( 5, 2,  20,  3),
            ( 6, 3,  55, 10),
            ( 7, 1,  80, 20),
            ( 8, 2,  40, 10),
            ( 9, 3, 200, 50),
            (10, 4, 150, 30),
            (11, 2,  70, 15),
            (12, 3, 100, 25),
            (13, 1,  35, 10),
            (14, 2,  25,  5),
            (15, 3,  30,  5),
            (16, 4, 120, 20),
            (17, 1,  50, 10),
            (18, 2, 300, 50),
            (19, 3, 250, 50),
            (20, 4, 200, 50),
        ]
    )

    # ── SHIPMENTS (25 rows) ────────────────────────────────────────────────
    cur.executemany(
        "INSERT INTO shipments (order_id, warehouse_id, shipment_date, delivery_date, status) VALUES (?,?,?,?,?)",
        [
            ( 1, 1, "2024-01-06", "2024-01-09", "Delivered"),
            ( 2, 1, "2024-03-19", "2024-03-22", "Delivered"),
            ( 3, 2, "2024-01-21", "2024-01-24", "Delivered"),
            ( 5, 1, "2024-02-15", "2024-02-18", "Delivered"),
            ( 7, 2, "2024-03-01", "2024-03-04", "Delivered"),
            ( 8, 3, "2024-06-13", "2024-06-16", "Delivered"),
            ( 9, 1, "2024-03-04", "2024-03-07", "Delivered"),
            (10, 2, "2024-07-20", None,          "In Transit"),
            (11, 1, "2024-01-12", "2024-01-15", "Delivered"),
            (12, 2, "2024-04-23", "2024-04-26", "Delivered"),
            (13, 3, "2024-02-08", "2024-02-11", "Delivered"),
            (14, 2, "2024-05-16", "2024-05-19", "Delivered"),
            (16, 4, "2024-07-01", "2024-07-03", "Delivered"),
            (17, 1, "2024-01-31", "2024-02-03", "Delivered"),
            (18, 2, "2024-04-06", "2024-04-09", "Delivered"),
            (19, 1, "2024-02-20", "2024-02-23", "Delivered"),
            (21, 3, "2024-03-15", "2024-03-18", "Delivered"),
            (22, 3, "2024-06-19", "2024-06-22", "Delivered"),
            (23, 1, "2024-01-09", "2024-01-12", "Delivered"),
            (25, 2, "2024-04-17", "2024-04-20", "Delivered"),
            (26, 1, "2024-02-03", "2024-02-06", "Delivered"),
            (27, 2, "2024-06-10", "2024-06-13", "Delivered"),
            (28, 1, "2024-01-23", "2024-01-26", "Delivered"),
            (29, 2, "2024-05-12", "2024-05-15", "Delivered"),
            (30, 3, "2024-07-21", None,          "In Transit"),
        ]
    )

    # ── REVIEWS (20 rows) ─────────────────────────────────────────────────
    cur.executemany(
        "INSERT INTO reviews (customer_id, product_id, rating, review_text, review_date) VALUES (?,?,?,?,?)",
        [
            ( 1,  1, 5, "Absolutely love the iPhone 15 Pro!",      "2024-01-15"),
            ( 1,  7, 4, "AirPods are great but pricey.",           "2024-03-25"),
            ( 2, 12, 4, "Nice kurta, good quality.",               "2024-01-28"),
            ( 3,  4, 5, "MacBook Air M3 is blazing fast!",         "2024-02-20"),
            ( 3,  7, 5, "Best earbuds I have ever used.",          "2024-05-10"),
            ( 4, 14, 4, "Instant Pot changed my cooking.",         "2024-03-05"),
            ( 5,  2, 3, "Galaxy S24 is decent, not exceptional.",  "2024-03-10"),
            ( 6,  8, 5, "Sony headphones are outstanding.",        "2024-01-20"),
            ( 7,  3, 4, "OnePlus 12 great value for money.",       "2024-02-15"),
            ( 8, 18, 5, "Python Crash Course is a must-read!",     "2024-07-05"),
            ( 9,  6, 5, "Lenovo ThinkPad is rock-solid.",          "2024-02-08"),
            (10,  5, 4, "Dell XPS 15 excellent display.",          "2024-02-27"),
            (11, 12, 3, "Kurta colour faded after washing.",       "2024-03-22"),
            (12,  1, 5, "iPhone 15 Pro worth every penny.",        "2024-01-14"),
            (13, 12, 4, "Pretty good kurta for the price.",        "2024-04-20"),
            (14,  2, 4, "Samsung solid mid-range choice.",         "2024-02-09"),
            (15,  4, 5, "MacBook Air M3 best laptop ever!",        "2024-01-30"),
            ( 6, 13, 3, "Zara jacket quality has declined.",       "2024-05-01"),
            ( 9,  9, 4, "Anker USB-C hub works perfectly.",        "2024-04-12"),
            ( 3, 10, 5, "Nike polo super comfortable.",            "2024-07-25"),
        ]
    )

    conn.commit()
    conn.close()
    print("Data inserted")


def check_data():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT * FROM customers;")
    for row in cur.fetchall():
        print(row)
    conn.close()


# ---------------------------------------------------------------------------
# ChromaDB schema loader
# ---------------------------------------------------------------------------
def load_schema_once():
    existing = collection.count()

    if existing == 0:
        schema_docs = [
            "customers(customer_id, name, email, city, country, signup_date, customer_segment)",
            "orders(order_id, customer_id, order_date, status, total_amount)",
            "order_items(order_item_id, order_id, product_id, quantity, price)",
            "products(product_id, name, category_id, brand, cost_price, selling_price)",
            "categories(category_id, category_name, parent_category_id)",
            "inventory(product_id, warehouse_id, stock_quantity, reorder_level)",
            "payments(payment_id, order_id, payment_method, payment_status, amount)",
            "shipments(order_id, warehouse_id, shipment_date, delivery_date, status)",
            "reviews(customer_id, product_id, rating, review_date)",
            "warehouses(warehouse_id, location, capacity)",
        ]

        collection.add(
            documents=schema_docs,
            ids=[f"id_{i}" for i in range(len(schema_docs))]
        )
        print("Schema stored in ChromaDB")
    else:
        print("Schema already exists")


# ---------------------------------------------------------------------------
# LangGraph state
# ---------------------------------------------------------------------------
class GraphState(TypedDict, total=False):
    query: str
    schema: str
    sql: str
    result: dict
    explanation: str   # populated by explain_result node
    error: str
    retry_count: int


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------
def retrieve_schema(state: GraphState) -> GraphState:
    query = state["query"]

    if isinstance(query, dict):
        query = query.get("query", "")

    results = collection.query(
        query_texts=[query],
        n_results=3
    )

    docs = results["documents"][0]
    state["schema"] = " ".join(docs)
    return state


def generate_sql(state: GraphState) -> GraphState:
    query = state["query"]
    schema = state["schema"]

    prompt = f"""
You are an expert SQL developer working with SQLite.

Schema:
{schema}

Question:
{query}

Return ONLY the SQL query, no markdown fences, no explanation.
"""

    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )

    sql = response.choices[0].message.content.strip()
    # Strip markdown fences if model wraps the query
    if sql.startswith("```"):
        sql = "\n".join(
            line for line in sql.splitlines()
            if not line.strip().startswith("```")
        ).strip()

    state["sql"] = sql
    return state


def validate_sql(state: GraphState) -> GraphState:
    sql = state["sql"]

    if not isinstance(sql, str):
        state["error"] = "SQL is not a string"
        return state

    sql_clean = sql.strip().lower()
    banned = ["drop", "delete", "update", "insert", "alter", "truncate"]

    if any(word in sql_clean for word in banned):
        state["error"] = "Unsafe SQL detected"
        return state

    if not sql_clean.startswith("select"):
        state["error"] = "Only SELECT queries allowed"
        return state

    state["error"] = ""
    return state


def execute_sql(state: GraphState) -> GraphState:
    sql = state["sql"]

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(sql)

        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        conn.close()

        state["result"] = {"columns": columns, "rows": rows}
        state["error"] = ""

    except Exception as e:
        state["error"] = str(e)
        state["result"] = None

    return state


def fix_sql(state: GraphState) -> GraphState:
    state["retry_count"] = state.get("retry_count", 0) + 1

    prompt = f"""
    The following SQL failed:

    SQL:
    {state.get('sql', '')}

    Error:
    {state.get('error', '')}

    Return ONLY the corrected SQL query.
    """

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a SQL expert. Output only SQL."},
            {"role": "user", "content": prompt}
        ]
    )

    state["sql"] = response.choices[0].message.content.strip()
    return state


def format_answer(state: GraphState) -> GraphState:
    prompt = f"""
    Convert SQL result into readable answer.

    Question:
    {state['query']}

    Result:
    {state['result']}
    """

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    state["result"] = response.choices[0].message.content
    return state


def explain_result(state: GraphState) -> GraphState:
    """
    Explain the formatted result in plain business language.
    Runs after format_answer so state['result'] is already a readable string.
    The explanation is stored separately in state['explanation'].
    """
    prompt = f"""
User question: {state['query']}
SQL result: {state['result']}

Explain in simple business terms.
"""

    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )

    state["explanation"] = response.choices[0].message.content
    return state


# ---------------------------------------------------------------------------
# Build LangGraph
# ---------------------------------------------------------------------------
def build_graph():
    builder = StateGraph(GraphState)

    builder.add_node("retrieve_schema", retrieve_schema)
    builder.add_node("generate_sql",    generate_sql)
    builder.add_node("validate_sql",    validate_sql)
    builder.add_node("execute_sql",     execute_sql)
    builder.add_node("fix_sql",         fix_sql)
    builder.add_node("format_answer",   format_answer)
    builder.add_node("explain_result",  explain_result)   # ← new node

    builder.set_entry_point("retrieve_schema")

    builder.add_edge("retrieve_schema", "generate_sql")
    builder.add_edge("generate_sql",    "validate_sql")
    builder.add_edge("validate_sql",    "execute_sql")

    def check_error(state: GraphState) -> str:
        return "fix_sql" if state.get("error") else "format_answer"

    builder.add_conditional_edges(
        "execute_sql",
        check_error,
        {
            "fix_sql":       "fix_sql",
            "format_answer": "format_answer",
        }
    )

    builder.add_edge("fix_sql",       "execute_sql")
    builder.add_edge("format_answer", "explain_result")   # ← wire in new node
    builder.add_edge("explain_result", END)

    return builder.compile()


# ---------------------------------------------------------------------------
# Sample queries that showcase complex JOINs and window / ranking functions
# ---------------------------------------------------------------------------
# DEMO_QUERIES = [
#     "Which customers have placed orders containing products from more than one category?",
#     "For each product category show the top-selling product by total revenue using ROW_NUMBER()",
# ]

# # ── Complex multi-table JOINs ──────────────────────────────────────────
#     # "Show each customer's name, total number of orders, and total amount spent, sorted by total spend descending",
#     # "List all products with their parent category name, brand, selling price, and average review rating",
#     # "Show each order with the customer name, product names ordered, quantities, and payment status",
#     "Which customers have placed orders containing products from more than one category?",
#     # "For each warehouse, list the products stored there along with brand, stock quantity, and reorder level",
#     # "Show all shipments with order date, customer name, product name, shipment date, delivery date, and current status",

#     # ── Window / ranking functions ─────────────────────────────────────────

#      "Rank customers by total spend using RANK(). Show name, total spend, and rank",
# #     "For each product category show the top-selling product by total revenue using ROW_NUMBER()",
# #     "Show a running total of order amounts ordered by order_date using a window SUM",
# #     "Rank products by average review rating within each category using DENSE_RANK()",
# #     "Show each customer's order amounts along with the previous order amount using LAG()",
# #     "For each brand, rank their products by selling price using RANK() and show the top-ranked product per brand",
# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
# if __name__ == "__main__":
#     create_tables()
#     insert_data()
#     check_data()
#     load_schema_once()

#     graph = build_graph()

#     print("\n" + "=" * 60)
#     print("Running demo queries...")
#     print("=" * 60)

#     for q in DEMO_QUERIES[:2]:   # running first 2 to keep output short; 
#         print(f"\nQuery: {q}")
#         result = graph.invoke({"query": q})
#         print(f"Answer:\n{result.get('result')}\n")
#         print(f"Explanation:\n{result.get('explanation')}\n")
