# Retails — Natural Language to SQL

A retail Q&A system that lets users query a t-shirt inventory database using plain English. The system converts natural language questions into SQL, executes them, and returns human-readable answers.

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

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Google Gemini `gemini-2.5-flash` / Groq / Ollama (switchable via `.env`) |
| Orchestration | LangChain (`SQLDatabaseChain`, `FewShotPromptTemplate`) |
| Semantic Search | HuggingFace `all-MiniLM-L6-v2` + ChromaDB |
| Database | SQLite (`t_shirts`, `discounts` tables) |
| UI | Streamlit |

---

## Database Schema

```sql
t_shirts (t_shirt_id, brand, color, size, price, stock_quantity)
discounts (discount_id, t_shirt_id, pct_discount)
-- Brands: Adidas, Nike, Van Heusen, Levi's
-- Sizes: XS, S, M, L, XL | Colors: White, Red, Blue, Black
```

---

## Setup

```bash
pip install -r requirements.txt
# .env: set LLM_PROVIDER=gemini and GOOGLE_API_KEY=...
streamlit run main.py
```

---

## Project Status

Work in progress — core hybrid inference pipeline is complete. Testing and edge case handling ongoing.
