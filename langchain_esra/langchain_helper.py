import logging
import os
import re
import sqlite3
from turtle import st
import uuid
from typing import Optional

from dotenv import load_dotenv

from langchain_ollama import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

from langchain_core.prompts import FewShotPromptTemplate, PromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.example_selectors import SemanticSimilarityExampleSelector
from langchain_community.utilities import SQLDatabase
from langchain_experimental.sql import SQLDatabaseChain

import chromadb

from few_shots import few_shots


# Keep sql_queries.log free of httpx/langchain records that propagate up the tree.
class _OnlySqlQueriesFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.name == "sql_queries"


sql_logger = logging.getLogger("sql_queries")
sql_logger.setLevel(logging.INFO)
sql_logger.propagate = False
if not sql_logger.handlers:
    _handler = logging.FileHandler("sql_queries.log", encoding="utf-8")
    _handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    _handler.addFilter(_OnlySqlQueriesFilter())
    sql_logger.addHandler(_handler)


load_dotenv()

db_path = r"C:\Projects\RETAIL_SALES_CHATBOT\langchain_esra\data\tshirts.db"

PROVIDER = "groq"  # "ollama" | "gemini" | "groq"


def _build_llm(temperature: float):
    if PROVIDER == "ollama":
        return ChatOllama(model="qwen2.5:7b", temperature=temperature)
    elif PROVIDER == "groq":
        return ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=temperature,
            api_key=st.secrets["GROQ_API_KEY"]
        )
    else:
        return ChatGoogleGenerativeAI(
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            model="gemini-2.5-flash",
            temperature=temperature,
        )


llm = _build_llm(temperature=0.2)


PROMPT_SUFFIX = """Only use the following tables:
{table_info}

Question: {input}"""

sqlite_prompt = """You are a SQLite expert. Given an input question, first create a syntactically correct SQLite query to run, then look at the results of the query and return the answer to the input question.
Unless the user specifies in the question a specific number of examples to obtain, query for at most {top_k} results using the LIMIT clause as per SQLite. You can order the results to return the most informative data in the database.
Never query for all columns from a table. You must query only the columns that are needed to answer the question. Wrap each column name in backticks (`) to denote them as delimited identifiers.
Pay attention to use only the column names you can see in the tables below. Be careful to not query for columns that do not exist. Also, pay attention to which column is in which table.
Pay attention to use DATE('now') function to get the current date, if the question involves "today".

Important database value rules:
- Color values are capitalized: use 'White', 'Red', 'Blue', 'Black' — NOT 'white', 'red', etc.
- Size values are abbreviations: use 'XS', 'S', 'M', 'L', 'XL' — NOT 'small', 'medium', 'large', etc.

Use the following format:

question: Question here
SQLQuery: SQLQuery to run with no pre-amble
SQLResult: Result of the SQLQuery
answer: Final answer here

No pre-amble.
"""


# ---------------------------------------------------------------------------
# Validation layer
# ---------------------------------------------------------------------------

class ValidationError(Exception):
    """Raised when generated SQL or its result fails a safety / sanity check."""


_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|replace|attach|detach|pragma)\b",
    re.IGNORECASE,
)

_AGGREGATION_INTENT = re.compile(
    r"\b(how many|total|sum|count|average|avg|min|max|highest|lowest|most|least)\b",
    re.IGNORECASE,
)
_AGGREGATE_FN = re.compile(r"\b(sum|count|avg|min|max)\s*\(", re.IGNORECASE)


def _extract_sql(text: str) -> str:
    """Pull a clean SELECT out of LLM output that may contain fences, prefixes, or trailing prose."""
    if not text:
        raise ValidationError("empty LLM output")
    fence = re.search(r"```(?:sql)?\s*(.+?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1)
    text = re.sub(r"^\s*SQLQuery\s*:\s*", "", text, flags=re.IGNORECASE | re.MULTILINE)
    # Keep text from the first SELECT/WITH up to a semicolon (or end).
    m = re.search(r"(?is)\b(select|with)\b.+?(?:;|\Z)", text)
    if not m:
        raise ValidationError("no SELECT/WITH found in LLM output")
    return m.group(0).strip().rstrip(";").strip()


def validate_sql(sql: str) -> None:
    """Static checks + syntax check via EXPLAIN (does not execute the query)."""
    if not sql or not sql.strip():
        raise ValidationError("SQL is empty")
    head = sql.strip().lower()
    if not (head.startswith("select") or head.startswith("with")):
        raise ValidationError(f"only SELECT/WITH allowed; got: {sql[:60]!r}")
    if _FORBIDDEN.search(sql):
        raise ValidationError("SQL contains a write/DDL keyword")
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            conn.execute(f"EXPLAIN {sql}")
    except sqlite3.Error as e:
        raise ValidationError(f"syntax error: {e}")


def validate_intent(question: str, sql: str) -> None:
    """If the question asks for an aggregate ('how many', 'total', 'highest', ...),
    the SQL must use an aggregate function or ORDER BY + LIMIT. Otherwise the LLM
    likely returned raw rows instead of a computed answer."""
    if not _AGGREGATION_INTENT.search(question):
        return
    if _AGGREGATE_FN.search(sql):
        return
    has_order_by = re.search(r"\border\s+by\b", sql, re.IGNORECASE)
    has_limit = re.search(r"\blimit\b", sql, re.IGNORECASE)
    if has_order_by and has_limit:
        return
    raise ValidationError(
        "question implies aggregation but SQL has no SUM/COUNT/AVG/MIN/MAX "
        "and no ORDER BY + LIMIT"
    )


def validate_result(rows) -> None:
    """Reject empty results and all-NULL aggregates — these usually mean the SQL was wrong."""
    if rows is None:
        raise ValidationError("query returned None")
    if isinstance(rows, str):
        stripped = rows.strip()
        if not stripped or stripped in ("[]", "()", "None", "[(None,)]"):
            raise ValidationError("query returned no rows / all NULL")
        return
    try:
        if len(rows) == 0:
            raise ValidationError("query returned zero rows")
    except TypeError:
        return
    flat = []
    for row in rows:
        if isinstance(row, (tuple, list)):
            flat.extend(row)
        else:
            flat.append(row)
    if flat and all(v is None for v in flat):
        raise ValidationError("query returned only NULL values")


def _run_readonly(sql: str):
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        return conn.execute(sql).fetchall()


# ---------------------------------------------------------------------------
# Direct-LLM path
# ---------------------------------------------------------------------------

_DIRECT_PROMPT = PromptTemplate.from_template(
    """You are a SQLite expert. Return ONLY the SQLite SELECT query — no prose, no code fences, no 'SQLQuery:' prefix.

Tables:
{table_info}

Rules:
- SELECT only. No INSERT/UPDATE/DELETE/DDL.
- Color values are capitalized: 'White', 'Red', 'Blue', 'Black'.
- Size values are abbreviations: 'XS', 'S', 'M', 'L', 'XL'.
- Wrap column names in backticks.
- Limit to {top_k} rows unless aggregating.

Question: {input}
SQL:"""
)


def _direct_llm_sql(db: SQLDatabase, question: str, top_k: int = 5) -> str:
    prompt = _DIRECT_PROMPT.format(
        table_info=db.get_table_info(), top_k=top_k, input=question
    )
    raw = llm.invoke(prompt).content
    return _extract_sql(raw)


# ---------------------------------------------------------------------------
# Few-shot chain (fallback)
# ---------------------------------------------------------------------------

def get_few_shot_db_chain():
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    to_vectorize = [" ".join(example.values()) for example in few_shots]

    client = chromadb.Client()
    for col in client.list_collections():
        try:
            client.delete_collection(col.name)
        except Exception:
            pass

    vectorstore = Chroma.from_texts(
        to_vectorize,
        embeddings,
        metadatas=few_shots,
        collection_name=f"few_shots_{uuid.uuid4().hex[:8]}",
    )

    example_selector = SemanticSimilarityExampleSelector(
        vectorstore=vectorstore,
        k=1,
    )

    example_prompt = PromptTemplate(
        input_variables=["question", "SQLQuery", "SQLResult", "answer"],
        template="""
Question: {question}
SQLQuery: {SQLQuery}
SQLResult: {SQLResult}
Answer: {answer}
""",
    )

    few_shot_prompt = FewShotPromptTemplate(
        example_selector=example_selector,
        example_prompt=example_prompt,
        prefix=sqlite_prompt,
        suffix=PROMPT_SUFFIX,
        input_variables=["input", "table_info", "top_k"],
    )

    db = SQLDatabase.from_uri(f"sqlite:///{db_path}")
    chain = SQLDatabaseChain.from_llm(
        llm=llm,
        db=db,
        verbose=True,
        prompt=few_shot_prompt,
        return_direct=True,
        return_intermediate_steps=True,
    )
    return chain


def _extract_chain_sql(response) -> Optional[str]:
    """Dig the SQL out of SQLDatabaseChain.intermediate_steps (shape varies by version)."""
    if not isinstance(response, dict):
        return None
    for step in response.get("intermediate_steps", []):
        if isinstance(step, str) and re.search(r"\bselect\b|\bwith\b", step, re.IGNORECASE):
            try:
                return _extract_sql(step)
            except ValidationError:
                continue
        if isinstance(step, dict):
            for key in ("sql_cmd", "query", "input"):
                val = step.get(key)
                if isinstance(val, str) and re.search(r"\bselect\b|\bwith\b", val, re.IGNORECASE):
                    try:
                        return _extract_sql(val)
                    except ValidationError:
                        continue
    return None


# ---------------------------------------------------------------------------
# Orchestrator: direct LLM first, few-shot as safety net
# ---------------------------------------------------------------------------

def ask(chain, question: str) -> dict:
    """Hybrid query generation.

    1) Ask the LLM directly for SQL, validate, and execute read-only.
    2) On any validation failure, fall back to the few-shot SQLDatabaseChain.

    Returns a dict: {result, sql, strategy, attempts}.
    """
    db = SQLDatabase.from_uri(f"sqlite:///{db_path}")
    attempts = []

    sql_logger.info("Q: %s", question)

    # Step 1 — Direct LLM
    direct_sql = None
    try:
        direct_sql = _direct_llm_sql(db, question)
        sql_logger.info("DIRECT_SQL: %s", direct_sql)
        validate_sql(direct_sql)
        validate_intent(question, direct_sql)
        rows = _run_readonly(direct_sql)
        validate_result(rows)
        sql_logger.info("DIRECT_RESULT: %s", rows)
        sql_logger.info("STRATEGY: direct\n")
        attempts.append({"strategy": "direct", "sql": direct_sql, "ok": True})
        return {
            "result": rows,
            "sql": direct_sql,
            "strategy": "direct",
            "attempts": attempts,
        }
    except Exception as e:
        sql_logger.warning("DIRECT_FAILED: %s", e)
        attempts.append({"strategy": "direct", "sql": direct_sql, "error": str(e)})

    # Step 2 — Few-shot fallback
    try:
        response = chain.invoke({"query": question})
        fs_sql = _extract_chain_sql(response)
        if fs_sql:
            sql_logger.info("FEWSHOT_SQL: %s", fs_sql)
        rows = response.get("result") if isinstance(response, dict) else response
        validate_result(rows)
        sql_logger.info("FEWSHOT_RESULT: %s", rows)
        sql_logger.info("STRATEGY: fewshot\n")
        attempts.append({"strategy": "fewshot", "sql": fs_sql, "ok": True})
        return {
            "result": rows,
            "sql": fs_sql,
            "strategy": "fewshot",
            "attempts": attempts,
        }
    except Exception as e:
        sql_logger.error("FEWSHOT_FAILED: %s\n", e)
        attempts.append({"strategy": "fewshot", "error": str(e)})
        raise


if __name__ == "__main__":
    chain = get_few_shot_db_chain()
    print(ask(chain, "How many white color Levi t-shirts do we have?"))
