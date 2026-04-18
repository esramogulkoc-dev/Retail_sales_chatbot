# Retails — Natural Language to SQL

Ask a t-shirt store database questions in plain English. Powered by LLM + LangChain with a hybrid direct / few-shot fallback pipeline and a built-in validation layer.

**Live demo:** _<!-- TODO: Streamlit Cloud URL here -->_

![App screenshot](langchain_esra/screenshot.png)

---

## Deploy - Live demo

Deployed on Streamlit Community Cloud:
_<!-- TODO: paste the deploy URL here -->_

## Project (STAR)

### Situation
A retail store keeps inventory, pricing and discount data in a SQLite database. Non-technical staff (store managers, analysts) need to answer questions like *"How many red Adidas t-shirts do we have?"* or *"What's the total revenue if we sell all Van Heusen stock after discounts?"* — but they don't know SQL.

### Task
Build a natural-language Q&A interface that:
- Generates correct SQL from plain-English questions
- Protects the database from destructive or malformed queries
- Stays fast on simple questions, but reliable on tricky ones

### Action
Designed a **hybrid query-generation pipeline** with two paths and a validation layer between them:

1. **Direct LLM (fast path)** — LLM generates SQL from the schema alone.
2. **Validation layer** — four checks before the query ever runs:
   - **Extraction**: strips markdown fences, prefixes, trailing prose.
   - **Static check**: `SELECT`/`WITH` only; rejects `INSERT/UPDATE/DELETE/DROP/…`; runs `EXPLAIN` for syntax.
   - **Intent check**: if the question implies aggregation (*how many*, *total*, *highest*), the SQL must use `SUM/COUNT/AVG/MIN/MAX` or `ORDER BY + LIMIT`.
   - **Result check**: rejects empty / all-`NULL` outputs.
3. **Few-shot fallback (reliable path)** — on any validation failure, a `SemanticSimilarityExampleSelector` over ChromaDB picks the 2 most similar Q→SQL examples and the LLM regenerates.
4. **Read-only execution** — all queries run via `sqlite3` in `mode=ro`, so writes are impossible even if the keyword filter were bypassed.

```
Question → Direct LLM → Validate → Execute (read-only) → Answer
                │
                └── fail ──► Few-shot fallback ──► Answer
```

### Result
- **Safe by default**: prompt-injection attempts to run DDL/DML are rejected at the validation layer.
- **Robust to LLM mistakes**: wrong-shape queries (e.g. returning 5 raw rows instead of one `SUM`) are caught by the intent check and auto-corrected via few-shot.
- **Observable**: every question logs `Q → SQL → RESULT → STRATEGY` to `sql_queries.log`; the UI shows which strategy was used and the generated SQL.
- **Pluggable LLMs**: Groq / Google Gemini / Ollama are swappable with a single config change.

---
## Architecture

```
User Question
      │
      ▼
┌─────────────────────────┐
│  1. Direct LLM          │  LLM generates SQL from schema description alone
│     (fast path)         │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  2. Validation Layer    │  Checks: syntax errors, NULL/empty results,
│                         │  suspicious aggregation outputs
└────────────┬────────────┘
             │
     [pass] ─┤─ [fail]
             │        │
             │        ▼
             │  ┌─────────────────────────────────────┐
             │  │  3. Few-shot Fallback (reliable)     │
             │  │  SemanticSimilarityExampleSelector   │
             │  │  finds top-2 similar Q→SQL examples  │
             │  │  from ChromaDB vector store,         │
             │  │  then LLM generates correct SQL       │
             │  └─────────────────────────────────────┘
             │        │
             └────────┘
                  │
                  ▼
           Natural language answer
```

**Key design decision:** Direct LLM is tried first for speed. Few-shot learning is a fallback, not the default — this avoids the ChromaDB/embedding overhead on every request.



## Tech Stack

| Layer | Choice |
|---|---|
| LLM | Groq `llama-3.3-70b-versatile` / Gemini `gemini-2.5-flash` / Ollama |
| Framework | LangChain (`SQLDatabaseChain`, `FewShotPromptTemplate`) |
| Embeddings | HuggingFace `all-MiniLM-L6-v2` |
| Vector store | ChromaDB |
| Database | SQLite (read-only at query time) |
| UI | Streamlit |

## Database

```sql
t_shirts  (t_shirt_id, brand, color, size, price, stock_quantity)
discounts (discount_id, t_shirt_id, pct_discount)
-- brands: Adidas, Nike, Van Heusen, Levi
-- sizes:  XS, S, M, L, XL     colors: White, Red, Blue, Black
```

## Run locally

```bash
pip install -r requirements.txt
# .env
#   GROQ_API_KEY=...        (or GOOGLE_API_KEY for Gemini)
streamlit run main.py
```

