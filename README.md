# 🧠 Text-to-SQL AI Agent (LangGraph + RAG + SQLite)

An intelligent AI-powered application that converts **natural language queries into SQL**, executes them on a database, and returns results — built using **LangGraph, OpenAI, ChromaDB, and SQLite**.

---

## 🚀 Features

* 🔍 **Natural Language → SQL**
* 🧠 **RAG-based Schema Retrieval (ChromaDB)**
* 🔗 **Multi-step AI Pipeline using LangGraph**
* 🔒 **SQL Safety Validation (Read-only enforcement)**
* 📊 **Structured Query Results**
* ⚡ **Lightweight SQLite Database**
* 🖥️ Optional **Streamlit UI**

---

## 🏗️ Architecture

```text
User Query
   ↓
Schema Retrieval (ChromaDB)
   ↓
SQL Generation (LLM)
   ↓
SQL Validation (Safety Layer)
   ↓
SQL Execution (SQLite)
   ↓
Results Output
```

---

## 📂 Project Structure

```text
.
├── txt_to_sql.py      # Core LangGraph pipeline and db creation (all nodes)
├── app.py           # Streamlit UI 
├── txt_to_sql.db    # SQLite database (auto-created)
├── txt_to_sql_db/       # Vector DB persistence
├── requirements.txt
└── README.md
```

---

## ⚙️ Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/text_to_sql_app.git
```

---

### 2. Setup environment (Recommended: uv)

```bash
uv venv
.venv\Scripts\activate
uv pip install -r requirements.txt
```

---

### 3. Set OpenAI API Key

```bash
setx OPENAI_API_KEY "your_api_key"
```

---

## ▶️ Run the Project

### 🔹 Without UI (CLI)

```bash
uv run python txt_to_sql.py
```

---

### 🔹 With Streamlit UI

```bash
uv run streamlit run app.py
```

---

## 💡 Example Queries

Try these in the app:

* "Show all customers"
* "Top customers by total spending"
* "List all orders that are not delivered"
* "Total revenue generated"
* "Which products are sold the most?"

---

## 🧠 Core Components

### 🔹 LangGraph Pipeline

Handles multi-step reasoning:

* Schema retrieval
* SQL generation
* Validation
* Execution

---

### 🔹 ChromaDB (Vector DB)

Stores database schema for semantic retrieval.

---

### 🔹 OpenAI LLM

Generates SQL queries from natural language.

---

### 🔹 SQLite

Lightweight relational database for execution.

---

## 🔒 Safety Features

* ❌ Blocks: `DROP`, `DELETE`, `UPDATE`, `INSERT`
* ✅ Allows only `SELECT` queries
* 🛡 Prevents accidental data modification

---

## 📊 Output Format

```json
{
  "columns": ["name", "total_spent"],
  "rows": [
    ["Rahul", 5000],
    ["Ananya", 3000]
  ]
}
```

---


## 🧑‍💻 Tech Stack

* Python
* LangGraph
* OpenAI API
* ChromaDB
* SQLite
* Streamlit

---

## 🤝 Contributing

Contributions are welcome! Feel free to open issues or submit PRs.

---

## ⭐ Show your support

If you like this project, give it a ⭐ on GitHub!

---

## 👨‍💻 Author

**Vanshata**
Aspiring AI Engineer | Building Agentic AI Systems

---
<img width="940" height="501" alt="image" src="https://github.com/user-attachments/assets/8f0a22d7-36dd-42a1-a5ea-c9c0897ea16d" />

<img width="940" height="479" alt="image" src="https://github.com/user-attachments/assets/fc0fb046-d916-465c-b2d8-35592b2b1388" />

<img width="940" height="681" alt="image" src="https://github.com/user-attachments/assets/c901926c-61e3-4d92-b3c1-75964368da7f" />

Demo available on request: https://texttosqlapp-p6pvfjpargujvsowt3mte8.streamlit.app/
