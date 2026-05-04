# Text-to-SQL AI Agent — Complete Project Notes
### Stack: LangGraph · OpenAI · ChromaDB · FastAPI · Streamlit · Docker · AWS ECS/ECR · GitHub Actions

---

> **How to export as PDF:** Open this file in VS Code → right-click → "Open Preview" → then File > Print > Save as PDF.
> Or use any Markdown-to-PDF tool (e.g. Pandoc, `markdown-pdf` npm package, or the VS Code "Markdown PDF" extension).

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Full System Architecture](#2-full-system-architecture)
3. [Database Layer — SQLite](#3-database-layer--sqlite)
4. [Vector Database Layer — ChromaDB](#4-vector-database-layer--chromadb)
5. [AI Pipeline — LangGraph (txt_to_sql.py)](#5-ai-pipeline--langgraph)
6. [FastAPI Backend (api.py)](#6-fastapi-backend)
7. [Streamlit Frontend (app.py)](#7-streamlit-frontend)
8. [Containerization — Docker](#8-containerization--docker)
9. [CI/CD Pipeline — GitHub Actions → AWS](#9-cicd-pipeline--github-actions--aws)
10. [Key Concepts Explained](#10-key-concepts-explained)
11. [FAANG-Level Interview Questions](#11-faang-level-interview-questions)

---

## 1. Project Overview

### What is this project?

A production-grade **AI Agent** that takes a **plain English question** (e.g. "Which customers spent the most in 2024?"), converts it into a valid **SQL query**, runs it against a real database, and returns structured results with a business explanation — all without the user knowing any SQL.

### Real-world Use Case

This solves "data democratisation" — non-technical business users (marketing, finance, operations) can query their own databases without a data analyst or SQL knowledge.

### Tech Stack at a Glance

| Layer | Technology | Why |
|---|---|---|
| AI Orchestration | LangGraph | Stateful, graph-based multi-step agent |
| LLM | OpenAI GPT-4o / GPT-4o-mini | SQL generation and explanation |
| Schema Memory | ChromaDB (Vector DB) | Semantic schema retrieval (RAG) |
| Database | SQLite | Lightweight, file-based relational DB |
| API Backend | FastAPI + Uvicorn | High-performance async REST API |
| Frontend | Streamlit | Rapid interactive data UI |
| Containerization | Docker + Docker Compose | Isolated, reproducible environments |
| Container Registry | Amazon ECR | Cloud Docker image storage |
| Deployment | Amazon ECS (Fargate) | Serverless container orchestration |
| CI/CD | GitHub Actions | Automated build-push-deploy on `git push` |

---

## 2. Full System Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                        USER (Browser)                         │
│                      Streamlit UI :8501                        │
└─────────────────────────┬─────────────────────────────────────┘
                          │  HTTP POST /query
                          ▼
┌───────────────────────────────────────────────────────────────┐
│                    FastAPI Backend :8000                        │
│   Endpoints: /query  /tables  /schema  /preview  /health      │
└─────────────────────────┬─────────────────────────────────────┘
                          │  graph.invoke({"query": ...})
                          ▼
┌───────────────────────────────────────────────────────────────┐
│                    LangGraph Pipeline                          │
│                                                               │
│  retrieve_schema → generate_sql → validate_sql → execute_sql  │
│        ↑                                    │                 │
│        │                    error?          │                 │
│      fix_sql ←─────────────────────────────┘                 │
│                                    │                          │
│                             format_answer → explain_result    │
└────────┬──────────────────────────┬───────────────────────────┘
         │                          │
         ▼                          ▼
  ┌─────────────┐           ┌──────────────┐
  │  ChromaDB   │           │   SQLite DB  │
  │ (Schema RAG)│           │  (Data Store)│
  └─────────────┘           └──────────────┘
         │
         ▼
  ┌─────────────┐
  │  OpenAI API │
  │  GPT-4o     │
  └─────────────┘
```

**Data Flow (step by step):**

1. User types question in Streamlit UI
2. Streamlit sends `POST /query {"question": "..."}` to FastAPI
3. FastAPI calls `graph.invoke()` which triggers the LangGraph pipeline
4. **Node 1:** `retrieve_schema` queries ChromaDB to find the 3 most relevant table schemas
5. **Node 2:** `generate_sql` sends the question + schema to GPT-4o → gets raw SQL back
6. **Node 3:** `validate_sql` checks for dangerous keywords (DROP, DELETE, etc.)
7. **Node 4:** `execute_sql` runs the SQL against SQLite
8. **If error:** `fix_sql` asks GPT-4o-mini to correct the SQL → loops back to execute
9. **Node 5:** `format_answer` converts raw rows to a readable answer
10. **Node 6:** `explain_result` adds business context in plain English
11. FastAPI serializes and returns JSON to Streamlit
12. Streamlit renders the SQL, table, and explanation

---

## 3. Database Layer — SQLite

### Why SQLite?

- Zero-configuration file-based database (no server needed)
- Ships as a single `.db` file (`txt_to_sql.db`)
- Perfect for demos, prototyping, and lightweight production workloads
- Python has built-in `sqlite3` module — no extra driver needed
- Trade-off: not suitable for concurrent writes at high scale (use PostgreSQL for production)

### Schema Design — 10 Tables (E-commerce Domain)

```
customers ─────┐
               ├── orders ─────┬── order_items ──── products ──── categories
payments ──────┘               │                        │
                               └── shipments       inventory ──── warehouses
                                                   reviews
```

**Table Descriptions:**

| Table | Purpose | Key Columns |
|---|---|---|
| `customers` | End users | customer_id, name, city, country, customer_segment |
| `categories` | Product hierarchy | category_id, parent_category_id (self-referencing) |
| `products` | Catalog | product_id, category_id, cost_price, selling_price |
| `orders` | Purchase events | order_id, customer_id, order_date, status, total_amount |
| `order_items` | Line items per order | order_item_id, order_id, product_id, quantity, price |
| `payments` | Payment records | payment_id, order_id, payment_method, payment_status |
| `warehouses` | Storage locations | warehouse_id, location, capacity |
| `inventory` | Stock levels | product_id, warehouse_id, stock_quantity, reorder_level |
| `shipments` | Delivery tracking | shipment_id, order_id, shipment_date, delivery_date, status |
| `reviews` | Customer feedback | review_id, customer_id, product_id, rating, review_text |

### Key Design Patterns

**Self-referencing Foreign Key** (`categories.parent_category_id`):
- Electronics (parent=NULL) → Smartphones, Laptops, Accessories (parent=1)
- Enables hierarchical category trees with a single table
- Queried with recursive CTEs or self-JOINs

**Idempotent seeding** (`INSERT ... IF NOT EXISTS` pattern):
- `create_tables()` uses `CREATE TABLE IF NOT EXISTS` — safe to call multiple times
- `insert_data()` doesn't check for existing data — in production you'd add a guard

**Sample data designed for SQL complexity:**
- 15 customers, 20 products, 30 orders, 44 order_items
- Enough rows to demonstrate JOINs, GROUP BY, and window functions (RANK, LAG, ROW_NUMBER)

---

## 4. Vector Database Layer — ChromaDB

### What is a Vector Database?

Traditional databases store structured data and search by exact match or range.  
A vector database stores **embeddings** (numerical representations of text/images) and searches by **semantic similarity** (cosine distance, dot product).

```
"Show customer purchases"  ──► [0.23, -0.81, 0.44, ...]  (embedding)
                                         ↓
                              Find nearest embeddings
                                         ↓
               "orders(order_id, customer_id, total_amount, ...)"  ← most relevant schema
```

### How ChromaDB is Used Here (RAG)

This is **Retrieval-Augmented Generation (RAG)** applied to database schema:

1. On startup, `load_schema_once()` stores 10 schema strings into ChromaDB (one per table)
2. When a user asks a question, `retrieve_schema()` queries ChromaDB for the **3 most relevant tables**
3. Only those 3 schemas are sent to GPT-4o → reduces tokens, improves SQL accuracy, reduces cost

**Without RAG:** You'd send all 10 table schemas to GPT every time → expensive, noisy, slower  
**With RAG:** You send only the 3 most relevant schemas → cheaper, focused, more accurate

### ChromaDB Config

```python
chroma_client = chromadb.Client(
    Settings(persist_directory="./chroma_db")
)
collection = chroma_client.get_or_create_collection(name="schema_collection")
```

- `persist_directory` saves the index to disk (not lost on restart)
- `get_or_create_collection` is idempotent — safe to call on every startup
- `collection.count() == 0` guard prevents duplicate inserts

### Embedding Model

ChromaDB uses its default embedding model (sentence-transformers `all-MiniLM-L6-v2`) automatically when no model is specified. It converts text to 384-dimensional vectors locally without an API call.

---

## 5. AI Pipeline — LangGraph

### What is LangGraph?

LangGraph is a framework for building **stateful, graph-based AI agents**. Unlike a simple LLM call or a sequential LangChain chain, LangGraph lets you:
- Define **nodes** (processing steps) and **edges** (transitions between steps)
- Share **state** across all nodes
- Add **conditional edges** (branches, loops, retries)
- Handle complex multi-step reasoning with error recovery

**LangGraph vs LangChain:**

| Feature | LangChain | LangGraph |
|---|---|---|
| Execution | Sequential chain | Directed graph with cycles |
| State | Passed as dict | TypedDict shared across nodes |
| Loops/Retries | Manual, messy | First-class conditional edges |
| Use case | Simple pipelines | Multi-step agents with retry logic |

### State Definition

```python
class GraphState(TypedDict, total=False):
    query:       str    # original user question
    schema:      str    # retrieved table schemas from ChromaDB
    sql:         str    # generated SQL
    result:      dict   # query results {columns, rows}
    explanation: str    # business explanation
    error:       str    # error message (empty string = no error)
    retry_count: int    # number of fix_sql retries
```

`total=False` means all keys are optional — nodes only update the keys they care about.

### Node-by-Node Explanation

#### Node 1: `retrieve_schema`
```python
results = collection.query(query_texts=[query], n_results=3)
state["schema"] = " ".join(docs)
```
- Embeds the user query and finds the 3 most semantically similar table schemas
- Converts them to a single string for the prompt
- **Why n_results=3?** Balance between context richness and token efficiency

#### Node 2: `generate_sql`
```python
prompt = f"""You are an expert SQL developer...
Schema: {schema}
Question: {query}
Return ONLY the SQL query, no markdown fences, no explanation."""
```
- Calls GPT-4o (most capable model) for SQL generation
- Strict prompt engineering: "Return ONLY the SQL" prevents markdown code blocks
- Has a fallback strip for ``` fences in case the model wraps output anyway
- Uses GPT-4o (not 4o-mini) because SQL accuracy is critical here

#### Node 3: `validate_sql`
```python
banned = ["drop", "delete", "update", "insert", "alter", "truncate"]
if any(word in sql_clean for word in banned): state["error"] = "Unsafe SQL"
if not sql_clean.startswith("select"): state["error"] = "Only SELECT allowed"
```
- **Security layer:** prevents the LLM from generating destructive queries
- Real-world risk: prompt injection attacks could make GPT generate `DROP TABLE` if no validation
- Limitation: this is keyword matching — a more robust approach uses SQL parsers (e.g. `sqlglot`)

#### Node 4: `execute_sql`
```python
conn = sqlite3.connect(DB_PATH)
cursor.execute(sql)
columns = [desc[0] for desc in cursor.description]
rows = cursor.fetchall()
state["result"] = {"columns": columns, "rows": rows}
```
- Opens a new connection per request (safe for SQLite's single-writer model)
- `cursor.description` gives column names from the result set
- On exception, sets `state["error"]` to trigger the retry branch

#### Node 5: `fix_sql` (Retry Node)
```python
state["retry_count"] = state.get("retry_count", 0) + 1
# Ask GPT-4o-mini to fix the broken SQL
```
- Uses **GPT-4o-mini** (cheaper) for the retry — acceptable quality for error correction
- Increments `retry_count` (tracked for observability — shown in the UI)
- Risk: infinite loops if the SQL is fundamentally unfixable → production systems add `if retry_count >= 3: raise`

#### Node 6: `format_answer`
```python
# Converts raw {columns, rows} dict to human-readable text
state["result"] = response.choices[0].message.content
```
- Reformats database results into natural language
- Note: this overwrites `state["result"]` with a string — the API handles both cases

#### Node 7: `explain_result`
```python
# Explains formatted result in plain business terms
state["explanation"] = response.choices[0].message.content
```
- Produces a business-level summary separate from the raw result
- Stored in `state["explanation"]` so it's a distinct API response field

### Graph Topology

```
retrieve_schema
      │
generate_sql
      │
validate_sql
      │
execute_sql ──── error? ──yes──► fix_sql ──► (back to execute_sql)
      │
     no
      │
format_answer
      │
explain_result
      │
     END
```

The `fix_sql → execute_sql` cycle is a **loop** — something impossible with simple sequential chains. LangGraph makes this natural with `add_conditional_edges`.

### Conditional Edge Logic

```python
def check_error(state: GraphState) -> str:
    return "fix_sql" if state.get("error") else "format_answer"

builder.add_conditional_edges("execute_sql", check_error, {
    "fix_sql":       "fix_sql",
    "format_answer": "format_answer",
})
```

The routing function returns a string key; LangGraph maps that to the next node.

---

## 6. FastAPI Backend

### Why FastAPI?

- **Async by design** — handles multiple requests concurrently with ASGI (Uvicorn)
- **Auto-documentation** — `/docs` gives a free Swagger UI
- **Pydantic integration** — request/response validation is declarative
- **Type hints** — IDE auto-complete + runtime validation

### Startup Lifecycle

```python
# Runs ONCE when the server starts — not on every request
create_tables()    # create SQLite tables
insert_data()      # seed demo data
load_schema_once() # populate ChromaDB
app.state.graph = build_graph()  # compile LangGraph once (warm-up)
```

**Why warm up the graph?** LangGraph compilation parses the graph topology. If done on the first request, it adds latency for the first user. Done at startup, all requests hit the pre-compiled graph.

### Pydantic Models

```python
class QueryRequest(BaseModel):
    question: str  # validated — must be a string

class QueryResponse(BaseModel):
    sql:         Optional[str]
    result:      Optional[dict]
    explanation: Optional[str]
    error:       Optional[str]
    retries:     int
```

Pydantic automatically:
- Parses incoming JSON to Python objects
- Validates types (raises 422 if `question` is missing)
- Serializes Python objects back to JSON for the response

### Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/` | Health check / welcome message |
| POST | `/query` | Main: NL question → SQL → result |
| GET | `/tables` | List all table names in SQLite |
| GET | `/schema/{table_name}` | Column info for a specific table |
| GET | `/preview/{table_name}` | First N rows of a table |
| GET | `/health` | Simple `{"status": "ok"}` for load balancers |

### Security Note — SQL Injection Risk

The `/schema` and `/preview` endpoints have a potential **SQL injection vulnerability**:

```python
# RISKY — table_name is interpolated directly into SQL:
cur.execute(f"PRAGMA table_info({table_name});")
cur.execute(f"SELECT * FROM {table_name} LIMIT ?;", (limit,))
```

`PRAGMA` statements don't support parameterised binding in SQLite, but `table_name` should be **whitelist-validated** against known table names before use. In production, validate that `table_name` is in the list returned by `sqlite_master`.

### Error Handling Strategy

| Scenario | HTTP Status | Behaviour |
|---|---|---|
| Empty question | 400 | `raise HTTPException(status_code=400)` |
| Pipeline exception | 500 | Caught generically, message forwarded |
| Table not found | 404 | Explicit 404 with detail message |
| Bad SQL param | 400 | SQLite exception forwarded as 400 |

---

## 7. Streamlit Frontend

### Architecture Pattern

Streamlit follows a **re-run model**: every user interaction (button click, text input) causes the entire Python script to re-execute from top to bottom. State is preserved across re-runs using `st.session_state`.

### Session State Usage

```python
# Pre-fill input when user clicks an example query
st.session_state.query_input = ex

# Store last API result to survive re-runs
st.session_state.last_result = response.json()
```

`session_state` is a dictionary-like object scoped to one browser session. It persists across re-runs but not across browser refreshes.

### Caching Strategy

```python
@st.cache_data(show_spinner=False)
def fetch_tables():  ...

@st.cache_data(show_spinner=False)
def fetch_schema(table: str): ...
```

`@st.cache_data` memoizes function results in memory. Since the schema rarely changes, caching avoids hammering the API on every re-render. The function signature arguments act as the cache key.

### Environment-Aware API URL

```python
API_BASE = os.getenv("API_BASE", "http://localhost:8000")
```

In `docker-compose.yml`, `API_BASE=http://api:8000` is injected as an env var, so Streamlit talks to the API container by its Docker network hostname (`api`), not `localhost`.

### Sidebar Structure

1. **Example Queries** — pre-built buttons that inject values into `session_state.query_input`
2. **Schema Browser** — live table/column explorer powered by API calls
3. **API Status** — real-time health check displayed as success/error indicator

### Results Rendering Logic

```python
raw = data.get("result") or {}
rows    = raw.get("rows", [])     # list of lists
columns = raw.get("columns", []) # list of strings

df = pd.DataFrame(rows, columns=columns)
st.dataframe(df, use_container_width=True, hide_index=True)
```

The API can return either structured `{columns, rows}` or a formatted string — the frontend handles both cases.

---

## 8. Containerization — Docker

### Why Docker?

- **Reproducibility:** "It works on my machine" → "It works everywhere"
- **Isolation:** Each service has its own Python env, no conflicts
- **Portability:** Same image runs locally, on ECS, or on any cloud
- **Deployment:** ECS pulls images from ECR and runs them as containers

### Dockerfile.api

```dockerfile
FROM python:3.11-slim        # minimal base — no dev tools, smaller image
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt  # layer cached unless requirements.txt changes
COPY . .                     # copy source AFTER deps — maximises cache reuse
EXPOSE 8000
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Layer caching trick:** `COPY requirements.txt` + `RUN pip install` BEFORE `COPY . .`  
If only source code changes (not requirements), Docker reuses the pip layer → much faster builds.

**`0.0.0.0` vs `127.0.0.1`:**  
`127.0.0.1` only accepts connections from the same machine. Inside a container, you must bind to `0.0.0.0` to accept connections from outside the container (the Docker network).

### Dockerfile.streamlit

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

Same pattern. Streamlit's `--server.address=0.0.0.0` is the equivalent of FastAPI's `--host 0.0.0.0`.

### docker-compose.yml

```yaml
services:
  api:
    build: { context: ., dockerfile: Dockerfile.api }
    ports: ["8000:8000"]      # host:container
    env_file: [.env]          # load OPENAI_API_KEY etc.

  frontend:
    build: { context: ., dockerfile: Dockerfile.streamlit }
    ports: ["8501:8501"]
    env_file: [.env]
    environment:
      API_BASE: http://api:8000  # use Docker network hostname, NOT localhost
    depends_on: [api]            # start api before frontend
```

**Docker Compose Networking:**  
All services in a compose file share a private virtual network. Service names (`api`, `frontend`) become DNS hostnames. So `http://api:8000` inside the `frontend` container resolves to the `api` container — `localhost` would point to the frontend container itself.

**`depends_on` limitation:**  
It only waits for the container to *start*, not for the application to be *ready*. In production, use health-check-based dependency: `depends_on: api: condition: service_healthy`.

---

## 9. CI/CD Pipeline — GitHub Actions → AWS

### Trigger

```yaml
on:
  push:
    branches: [main]
```

Every `git push` to `main` triggers an automated deployment. No manual steps needed.

### AWS Services Used

| AWS Service | Role |
|---|---|
| **ECR** (Elastic Container Registry) | Docker image storage (like Docker Hub but private, on AWS) |
| **ECS** (Elastic Container Service) | Runs containers on managed infrastructure |
| **ECS Cluster** `text_to_sql_cluster` | Logical grouping of ECS services |
| **ECS Services** `api_service`, `frontend-service` | Keep N containers running, handle restarts |
| **IAM** | Credentials for GitHub Actions to push to ECR and update ECS |

### Pipeline Steps

```
Step 1: Checkout code
        ↓
Step 2: Configure AWS credentials (from GitHub Secrets)
        ↓
Step 3: Login to ECR (get auth token)
        ↓
Step 4: Build API Docker image
        Tag as :latest AND :{git-sha}
        Push both tags to ECR
        ↓
Step 5: Build Frontend Docker image
        Same double-tagging strategy
        Push to ECR
        ↓
Step 6: aws ecs update-service --force-new-deployment (API)
        ↓
Step 7: aws ecs update-service --force-new-deployment (Frontend)
```

### Double-Tagging Strategy

```bash
-t $ECR_REGISTRY/$REPO:$IMAGE_TAG   # immutable: tied to exact git commit SHA
-t $ECR_REGISTRY/$REPO:latest        # mutable: always points to newest image
```

`:latest` = "deploy this now"  
`:{sha}` = "rollback to exactly this version if needed"

This is industry standard — you can rollback to any previous deployment by SHA.

### GitHub Secrets

Secrets (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) are stored in GitHub → Settings → Secrets, never in code. The workflow accesses them via `${{ secrets.AWS_ACCESS_KEY_ID }}`.

### `force-new-deployment`

```bash
aws ecs update-service --cluster ... --service ... --force-new-deployment
```

ECS pulls the `:latest` image from ECR and replaces running tasks with new ones — zero-downtime rolling update.

---

## 10. Key Concepts Explained

### RAG (Retrieval-Augmented Generation)

Instead of feeding all data to the LLM (expensive, hits context limits), RAG retrieves only the *relevant* subset first.

```
Query → Embed → Search Vector DB → Top-K relevant docs → LLM
```

Here: Query → ChromaDB → Top-3 schemas → GPT-4o (smaller, focused prompt)

Without RAG, you'd put all 10 table schemas in every prompt. With RAG, you send only 3.  
**This is the same pattern used in ChatGPT's web search, GitHub Copilot, and enterprise chatbots.**

### LangGraph State Machine

LangGraph is a **finite state machine** where:
- States = `GraphState` dict
- Transitions = edges and conditional edges
- Actions = nodes (Python functions that modify state)

The retry loop (`fix_sql → execute_sql`) is a cycle in the graph — impossible in DAG-only frameworks like basic LangChain.

### SQL Window Functions

The example queries in the app demonstrate window functions — a common SQL interview topic:

```sql
-- RANK() — ties get same rank, gap after
SELECT name, total_spend, RANK() OVER (ORDER BY total_spend DESC) AS rnk
FROM ...

-- ROW_NUMBER() — unique rank even for ties
SELECT name, ROW_NUMBER() OVER (PARTITION BY category ORDER BY revenue DESC)

-- LAG() — compare current row to previous row
SELECT name, amount, LAG(amount) OVER (ORDER BY order_date) AS prev_amount

-- Running total
SELECT order_date, SUM(total_amount) OVER (ORDER BY order_date) AS running_total
```

### Agentic AI vs Simple LLM Calls

| Simple LLM Call | Agentic System (this project) |
|---|---|
| One prompt → one response | Multi-step: retrieve → generate → validate → execute |
| No memory between calls | Shared state (`GraphState`) flows through all nodes |
| No error recovery | Retry loop with `fix_sql` |
| No external tool use | Calls ChromaDB, SQLite, OpenAI as tools |

### Pydantic — Why It Matters

Pydantic provides **runtime type validation** at API boundaries:
- Catches malformed JSON before it reaches business logic
- Auto-generates JSON schemas (used by Swagger /docs)
- Makes API contracts explicit and machine-readable
- Used by FastAPI, LangChain, LangGraph internally

---

## 11. FAANG-Level Interview Questions

---

### Section A — System Design

**Q1. Design a Text-to-SQL system that handles 10,000 queries per minute. What changes would you make to this architecture?**

*Answer framework:*
- Replace SQLite with PostgreSQL/BigQuery (concurrent reads, larger datasets)
- Add a caching layer (Redis) for identical queries (many business questions repeat)
- Replace ChromaDB with a managed vector DB (Pinecone, Weaviate, pgvector)
- Add a request queue (Celery + Redis) to decouple LLM calls from HTTP requests
- Horizontal scaling: multiple FastAPI replicas behind a load balancer
- Rate limiting per user/tenant to prevent abuse
- Async LLM calls to avoid blocking threads

---

**Q2. The fix_sql retry loop could run forever. How would you prevent this in production?**

*Answer:*
- Add `max_retries = 3` guard: `if state["retry_count"] >= 3: set error, route to END`
- Add a timeout per LLM call (httpx timeout parameter in OpenAI client)
- Circuit breaker: if OpenAI API is down, fail fast with 503 instead of retrying
- Track retry metrics and alert if retry rate > threshold
- Different LLMs for retry (GPT-4o for generation, GPT-4o-mini for fixing — already done here)

---

**Q3. How would you make this system multi-tenant (multiple companies sharing one deployment)?**

*Answer:*
- Each tenant has their own SQLite/PostgreSQL schema or database
- ChromaDB collection per tenant: `schema_collection_{tenant_id}`
- JWT authentication: token contains `tenant_id`, injected into every LangGraph call
- Row-level security in the database
- Rate limiting per tenant (not per user)
- Tenant-specific LLM prompts (different schemas, different business context)

---

**Q4. What are the failure modes of this system and how would you observe them?**

| Failure | Detection | Mitigation |
|---|---|---|
| OpenAI API down | HTTP 5xx from OpenAI | Retry with exponential backoff, fallback to local model |
| Bad SQL every time | retry_count always maxes | Alert on high p95 retry count |
| ChromaDB returns wrong schema | Wrong SQL generated | Evaluate RAG recall offline with golden dataset |
| SQLite write contention | SQLite SQLITE_BUSY error | Use WAL mode, or move to PostgreSQL |
| LLM generates SELECT * on huge table | OOM / timeout | Enforce LIMIT in validate_sql |

---

### Section B — Machine Learning / AI

**Q5. Explain RAG. What are its limitations in the context of this project?**

*Answer:*
- **RAG:** Embed the query, retrieve top-K relevant documents, inject into LLM prompt
- **Limitations here:**
  - ChromaDB uses local embeddings — quality depends on the embedding model
  - If query is ambiguous, retrieved schemas may be wrong → bad SQL
  - `n_results=3` is a fixed hyperparameter — complex queries spanning 5+ tables will have incomplete context
  - No re-ranking step: results are ranked purely by embedding similarity, not by actual SQL relevance
  - Schema strings are flat text — loses FK relationships and constraints

**Better approach for production:**
- Store full DDL (CREATE TABLE statements with FK constraints)
- Add a re-ranking model (cross-encoder) after initial retrieval
- Use a query classifier to decide how many schemas to retrieve (1-5 based on query complexity)

---

**Q6. How do you evaluate whether the SQL generation is accurate?**

*Answer:*
- **Execution accuracy:** Did the SQL run without error? (already tracked via retry_count)
- **Result accuracy:** Does the result match a human-written SQL for the same question?
- Build a golden dataset: 100 questions + expected SQL + expected results
- Compare output SQL by execution result, not string match (two different SQL queries can return the same result)
- Track: % exact match, % execution success, % correct result, average retry count
- Tools: `sqlglot` for AST comparison, `deepeval` for LLM evaluation

---

**Q7. What are the risks of using an LLM to generate SQL that runs on a real database?**

*Answer:*
- **SQL injection via prompt injection:** Malicious user question could manipulate the LLM to generate `DROP TABLE` if validation is bypassed
- **Data exfiltration:** LLM could generate queries that expose PII (the app only does SELECT, but SELECT * on a users table might leak emails)
- **Resource exhaustion:** LLM might generate `SELECT * FROM orders` on a billion-row table without LIMIT
- **Logic errors:** LLM generates syntactically valid but semantically wrong SQL — no test catches this without golden data
- **Mitigation:**
  - Allowlist only SELECT, enforce LIMIT
  - Column-level access control (mask PII columns)
  - Query cost estimation before execution (EXPLAIN QUERY PLAN)
  - Sandboxed read replica for LLM queries, never production write DB

---

### Section C — Backend / APIs

**Q8. What is the difference between `@app.on_event("startup")` and calling `create_tables()` at module level (as done here)?**

*Answer:*
- Module-level calls run when the module is **imported**, not when the server starts
- `@app.on_event("startup")` / `lifespan` context manager runs only when Uvicorn starts the server
- Module-level code also runs during **testing** (when you import `api`) — this can cause side effects
- Best practice: use `lifespan` async context manager (FastAPI 0.95+) for startup/shutdown logic
- The current approach works but is harder to test because you can't import `api` without seeding the DB

---

**Q9. How does Pydantic's `Optional` field work, and why does the response use it?**

*Answer:*
- `Optional[str]` = `Union[str, None]` — the field can be a string or None
- If the LLM doesn't set `explanation` (e.g. on error paths), it's None — not an empty string
- Pydantic serializes None as `null` in JSON
- The frontend checks `if explanation:` which is falsy for both None and empty string
- In Pydantic v2, `Optional` implies `default=None` unless you set `default=...`

---

**Q10. The `/preview` and `/schema` endpoints have a potential SQL injection. How would you fix it?**

*Answer:*
```python
# Current (vulnerable):
cur.execute(f"SELECT * FROM {table_name} LIMIT ?;", (limit,))

# Fixed — whitelist against known tables:
@app.get("/preview/{table_name}")
def preview_table(table_name: str, limit: int = 5):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Get allowed tables first
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    allowed = {row[0] for row in cur.fetchall()}
    if table_name not in allowed:
        raise HTTPException(status_code=404, detail="Table not found")
    # Now safe to use in f-string (verified against DB's own metadata)
    cur.execute(f"SELECT * FROM {table_name} LIMIT ?;", (limit,))
```

---

### Section D — DevOps / Cloud

**Q11. Explain the CI/CD pipeline. What happens when you `git push origin main`?**

*Step-by-step:*
1. GitHub Actions runner (Ubuntu VM) is provisioned
2. Code is checked out
3. AWS credentials are configured from GitHub Secrets
4. `docker build` creates the API image tagged with `:sha` and `:latest`
5. `docker push` uploads both tags to ECR
6. Same for frontend image
7. `aws ecs update-service --force-new-deployment` tells ECS to pull `:latest` and replace running tasks
8. ECS performs a rolling update — new tasks start, old tasks drain and stop
9. Load balancer routes traffic to new tasks only after health checks pass

---

**Q12. What is the difference between `docker-compose` and Amazon ECS?**

| Aspect | docker-compose | Amazon ECS |
|---|---|---|
| Scope | Local development | Production cloud deployment |
| Scaling | Manual (`--scale service=N`) | Auto-scaling groups, Fargate |
| Networking | Virtual bridge network | VPC, subnets, security groups |
| Image source | Local build / Docker Hub | ECR (private registry) |
| Health checks | Optional, basic | Load balancer + ECS health checks |
| Cost | Free (runs locally) | Pay per CPU/memory per second |

---

**Q13. Why do you push both `:latest` and `:{sha}` tags to ECR? What's the benefit?**

*Answer:*
- `:latest` is always overwritten by the newest push — ECS uses this for "deploy the newest version"
- `:{sha}` is immutable — tied to a specific git commit, never overwritten
- If a deployment causes issues, you can rollback to a previous SHA:
  ```bash
  aws ecs update-service --task-definition my-task:42  # old task def using old SHA
  ```
- `:latest` alone gives you no rollback history
- `:{sha}` alone means ECS doesn't know which to pull as "current"
- Together: best of both worlds

---

**Q14. What AWS IAM permissions does the GitHub Actions role need for this workflow?**

*Minimum required permissions:*
```json
{
  "Statement": [
    { "Effect": "Allow", "Action": ["ecr:GetAuthorizationToken"], "Resource": "*" },
    { "Effect": "Allow", "Action": ["ecr:BatchCheckLayerAvailability", "ecr:PutImage",
        "ecr:InitiateLayerUpload", "ecr:UploadLayerPart", "ecr:CompleteLayerUpload"],
      "Resource": "arn:aws:ecr:us-east-1:ACCOUNT:repository/txt_to_sql_api" },
    { "Effect": "Allow", "Action": ["ecs:UpdateService"],
      "Resource": "arn:aws:ecs:us-east-1:ACCOUNT:service/text_to_sql_cluster/*" }
  ]
}
```

**Principle of Least Privilege:** never give `AdministratorAccess` to CI/CD runners. Scope permissions to exact resources and actions needed.

---

### Section E — Databases & SQL

**Q15. Explain the difference between RANK(), DENSE_RANK(), and ROW_NUMBER().**

```sql
-- Given scores: 100, 90, 90, 80

-- ROW_NUMBER(): unique, no ties respected
-- 1, 2, 3, 4

-- RANK(): ties get same rank, gap after
-- 1, 2, 2, 4

-- DENSE_RANK(): ties get same rank, NO gap after
-- 1, 2, 2, 3
```

**When to use which:**
- `ROW_NUMBER()` — pagination (need exactly N rows)
- `RANK()` — leaderboards where ties should skip ranks (like Olympics)
- `DENSE_RANK()` — percentile calculations, no gaps desired

---

**Q16. Write SQL to find the top-selling product per category.**

```sql
WITH ranked AS (
    SELECT
        c.category_name,
        p.name AS product_name,
        SUM(oi.price * oi.quantity) AS revenue,
        ROW_NUMBER() OVER (
            PARTITION BY c.category_id
            ORDER BY SUM(oi.price * oi.quantity) DESC
        ) AS rn
    FROM order_items oi
    JOIN products p ON oi.product_id = p.product_id
    JOIN categories c ON p.category_id = c.category_id
    GROUP BY c.category_id, p.product_id
)
SELECT category_name, product_name, revenue
FROM ranked
WHERE rn = 1;
```

---

**Q17. What is a self-referencing foreign key and when would you use it?**

*Answer:*
- A column that references the primary key of the **same table**
- Used for hierarchical data: org charts (employee → manager), categories (parent → child), comments (reply → original post)
- In this project: `categories.parent_category_id → categories.category_id`
- Query with self-join: `SELECT child.name, parent.name FROM categories child LEFT JOIN categories parent ON child.parent_category_id = parent.category_id`
- For deep hierarchies (unlimited depth), use recursive CTEs (`WITH RECURSIVE`)

---

**Q18. Explain why the current insert_data() function would insert duplicate data if called twice.**

*Answer:*
- `INSERT INTO` without `INSERT OR IGNORE` or an existence check always inserts
- Calling `insert_data()` twice creates duplicate rows
- Fixes:
  1. `INSERT OR IGNORE INTO` with a UNIQUE constraint
  2. `INSERT INTO ... WHERE NOT EXISTS (...)`
  3. Guard: `if cur.execute("SELECT COUNT(*) FROM customers").fetchone()[0] > 0: return`
- Current code uses `create_tables()` idempotently but `insert_data()` is not idempotent — a design gap

---

### Section F — Python / Code Quality

**Q19. What is `TypedDict` and why is it used for GraphState instead of a regular dict or dataclass?**

*Answer:*
- `TypedDict` = dict with type annotations — gives IDE autocomplete and mypy type checking, no runtime overhead
- Regular `dict`: no type hints, easy to typo key names
- `dataclass`: instances have attributes (dot notation), must be instantiated — LangGraph expects dict-like state
- `total=False`: all keys optional — nodes only write the keys they modify, others remain unchanged
- LangGraph merges node outputs into existing state using dict update semantics — TypedDict is the perfect fit

---

**Q20. What does `@st.cache_data` do and what are its limitations?**

*Answer:*
- Memoizes function output in memory, keyed by function name + argument values
- Prevents redundant API calls on each Streamlit re-run
- **Limitations:**
  - Cache is per-process — not shared across multiple Streamlit workers
  - Cache is never invalidated unless TTL is set or `clear()` is called — stale data if schema changes
  - Not suitable for functions with side effects
  - Arguments must be hashable (lists/dicts fail unless serialized)
- For cross-session sharing, use `@st.cache_resource` (for connections, models)

---

## Quick Reference — Architecture Patterns Used

| Pattern | Where | Why |
|---|---|---|
| RAG | ChromaDB + LLM | Schema-aware SQL generation |
| State Machine | LangGraph | Multi-step agent with retries |
| Repository Pattern | `txt_to_sql.py` functions | DB access isolated from pipeline |
| API Gateway | FastAPI | Single entry point; decouples frontend from LLM |
| Warm-up | `app.state.graph` at startup | No cold-start latency on first request |
| Idempotency | `CREATE TABLE IF NOT EXISTS` | Safe to restart without data loss |
| Immutable + Mutable Tags | ECR :sha + :latest | Deploy latest, rollback by SHA |
| Least Privilege | IAM policies | Scope GitHub Actions to minimum permissions |
| Defense in Depth | validate_sql + whitelist | LLM output never trusted blindly |

---

*Notes prepared for: Text-to-SQL AI Agent Project*  
*Author: Vanshata | Date: 2026-04-25*  
*Stack: LangGraph · OpenAI GPT-4o · ChromaDB · FastAPI · Streamlit · Docker · AWS ECS/ECR · GitHub Actions*
