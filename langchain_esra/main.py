import streamlit as st
from langchain_helper import get_few_shot_db_chain
from langchain_community.utilities import SQLDatabase
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama
import os
from dotenv import load_dotenv
from sqlalchemy import text

# Load environment variables
load_dotenv()

# Set page config
st.set_page_config(
    page_title="AtliQ Tees - Database Q&A",
    page_icon="👕",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        text-align: center;
        color: #1f77b4;
        margin-bottom: 20px;
    }
    .question-box {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .answer-box {
        background-color: #d4edda;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
        border-left: 4px solid #28a745;
    }
    .method-badge {
        display: inline-block;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 12px;
        margin-left: 10px;
    }
    .direct-llm {
        background-color: #cce5ff;
        color: #0047ab;
    }
    .few-shot {
        background-color: #fff3cd;
        color: #856404;
    }
    .error-box {
        background-color: #f8d7da;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
        border-left: 4px solid #dc3545;
    }
    </style>
""", unsafe_allow_html=True)

# Title
st.markdown("<h1 class='main-header'>👕 AtliQ Tees Database Q&A</h1>", unsafe_allow_html=True)

# Subtitle
st.markdown("""
Ask natural language questions about our t-shirt inventory, sales, and discounts.
The system tries direct LLM first, then uses few-shot learning if needed.
""")

# Sidebar info
with st.sidebar:
    st.header("About")
    st.write("""
    **AtliQ Tees** - T-shirt Inventory Management System

    Brands: Adidas, Nike, Van Heusen, Levi's

    Colors: White, Red, Blue, Black

    Sizes: XS, S, M, L, XL
    """)

    # Show current LLM provider
    provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    provider_emoji = {
        "gemini": "🔷",
        "groq": "🟪",
        "ollama": "🦙"
    }
    emoji = provider_emoji.get(provider, "🤖")
    st.info(f"{emoji} **LLM Provider:** {provider.upper()}")

    st.header("Sample Questions")
    sample_questions = [
        "How many total t-shirts are left in stock?",
        "How many Nike t-shirts do we have in XS size?",
        "What is the total inventory value for all S-size t-shirts?",
        "How much revenue will we generate if we sell all Adidas shirts?",
        "How many different colors of t-shirts do we have?"
    ]

    for q in sample_questions:
        if st.button(q, key=q):
            st.session_state.user_question = q

# Initialize session state
if "user_question" not in st.session_state:
    st.session_state.user_question = ""

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


def normalize_sql(query_text: str) -> str:
    """Clean up LLM-generated SQL"""
    lines = [line.strip() for line in query_text.strip().splitlines()]
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    if lines and lines[0].lower().startswith("sql"):
        lines = [line for line in lines if not line.lower().startswith("sql")]
    return "\n".join(lines).strip()


def get_direct_llm(question: str) -> str:
    """Get SQL directly from LLM (Method 1)"""
    provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()

    # Normalize provider names
    if provider in {"ollama"}:
        llm = ChatOllama(
            model=os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0")),
            base_url=os.getenv("OLLAMA_API_URL", "http://127.0.0.1:11434"),
        )
    elif provider in {"groq"}:
        llm = ChatGroq(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0")),
            api_key=os.getenv("GROQ_API_KEY"),
        )
    elif provider in {"gemini", "google", "google_gemini", "google_generative"}:
        llm = ChatGoogleGenerativeAI(
            model=os.getenv("GOOGLE_MODEL", "gemini-2.5-flash"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0")),
            google_api_key=os.getenv("GOOGLE_API_KEY"),
        )
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider}. Use: gemini, groq, or ollama")

    schema_description = """SQLite database schema:
- t_shirts table: t_shirt_id (INTEGER), brand (TEXT), color (TEXT), size (TEXT), price (INTEGER), stock_quantity (INTEGER)
- discounts table: discount_id (INTEGER), t_shirt_id (INTEGER), pct_discount (DECIMAL)

Return ONLY the valid SQLite SQL query. No markdown, no explanation."""

    prompt = f"""{schema_description}

Question: {question}

SQL Query:"""

    response = llm.invoke(prompt)
    return normalize_sql(response.content)


def validate_result(sql_query: str, result: str) -> dict:
    """
    Validate SQL result for logic errors
    Returns: {is_valid: bool, reasons: [str]}
    """
    validation = {"is_valid": True, "reasons": []}

    # Check for NULL/empty results
    if result is None or result.strip() == "" or result == "None":
        validation["is_valid"] = False
        validation["reasons"].append("Empty/NULL result - possible logic error")

    # Check if result looks suspicious (very short string for aggregation)
    if len(result) < 2 and ("SUM" in sql_query.upper() or "COUNT" in sql_query.upper()):
        validation["is_valid"] = False
        validation["reasons"].append("Insufficient result for aggregation query")

    return validation


def execute_sql(sql_query: str) -> tuple[str, bool]:
    """
    Execute SQL query and return result + validity flag
    Returns: (result, is_valid)
    """
    db = SQLDatabase.from_uri("sqlite:///data/tshirts.db")

    try:
        result = db.run(sql_query)

        # Validate result
        validation = validate_result(sql_query, result)

        return result, validation["is_valid"]

    except Exception as e:
        raise Exception(f"SQL Syntax Error: {str(e)}")


def answer_question_hybrid(question: str) -> dict:
    """
    Hybrid approach with validation:
    1. Try direct LLM first (fast)
    2. Validate result (syntax + logic)
    3. If validation fails, use few-shot learning (reliable)
    """

    result = {
        "answer": None,
        "method": None,
        "sql": None,
        "error": None,
        "confidence": None,
    }

    # Method 1: Direct LLM
    try:
        st.write("🔍 **[1/3] Trying direct LLM approach...**")
        sql = get_direct_llm(question)
        result["sql"] = sql

        st.write(f"Generated SQL:\n```sql\n{sql}\n```")

        try:
            answer, is_valid = execute_sql(sql)

            if is_valid:
                st.write("✅ **[2/3] Validation passed**")
                result["answer"] = answer
                result["method"] = "direct_llm"
                result["confidence"] = "high"
                return result
            else:
                st.warning("⚠️ **[2/3] Validation failed** - Result looks suspicious (empty/NULL)")
                raise Exception("Result validation failed - likely logic error in SQL")

        except Exception as e:
            error_msg = str(e)
            st.warning(f"Validation failed: {error_msg}")
            result["error"] = error_msg
            # Continue to fallback

    except Exception as e:
        error_msg = str(e)
        st.warning(f"Direct LLM failed: {error_msg}")
        result["error"] = error_msg

    # Method 2: Few-shot learning (fallback)
    st.write("🎯 **[3/3] Falling back to few-shot learning...**")
    try:
        chain = get_few_shot_db_chain()
        answer = chain.run(question)
        result["answer"] = answer
        result["method"] = "few_shot"
        result["confidence"] = "reliable"
        return result

    except Exception as e:
        result["error"] = f"Few-shot also failed: {str(e)}"
        result["confidence"] = "failed"
        return result


# Main input area
col1, col2 = st.columns([4, 1])

with col1:
    user_input = st.text_input(
        "Ask a question about our t-shirt inventory:",
        value=st.session_state.user_question,
        placeholder="e.g., How many Adidas t-shirts are in stock?",
        key="input_field"
    )

with col2:
    submit_button = st.button("Ask", type="primary")

# Process question
if submit_button and user_input:
    st.session_state.user_question = user_input

    with st.spinner("Processing your question..."):
        result = answer_question_hybrid(user_input)

        if result["answer"]:
            # Add to chat history
            st.session_state.chat_history.append({
                "question": user_input,
                "answer": result["answer"],
                "method": result["method"],
                "sql": result["sql"],
                "confidence": result["confidence"]
            })
        else:
            st.error(f"Failed to answer: {result['error']}")

# Display chat history
if st.session_state.chat_history:
    st.divider()
    st.subheader("Conversation History")

    for i, interaction in enumerate(reversed(st.session_state.chat_history)):
        with st.container():
            # Question
            st.markdown(f"<div class='question-box'><b>Q:</b> {interaction['question']}</div>", unsafe_allow_html=True)

            # Method badge + confidence
            if interaction["method"] == "direct_llm":
                badge = '<span class="method-badge direct-llm">⚡ Direct LLM</span>'
            else:
                badge = '<span class="method-badge few-shot">🎯 Few-shot</span>'

            confidence = interaction.get("confidence", "unknown")
            confidence_emoji = {
                "high": "🟢",
                "reliable": "🟡",
                "failed": "🔴"
            }.get(confidence, "⚪")

            st.markdown(f"{badge} {confidence_emoji} {confidence}", unsafe_allow_html=True)

            # SQL if available
            if interaction.get("sql"):
                with st.expander("View SQL"):
                    st.code(interaction["sql"], language="sql")

            # Answer
            st.markdown(f"<div class='answer-box'><b>A:</b> {interaction['answer']}</div>", unsafe_allow_html=True)
            st.write("")  # Spacing

    # Clear history button
    if st.button("Clear History"):
        st.session_state.chat_history = []
        st.rerun()

# Footer
st.divider()
st.caption("AtliQ Tees - Hybrid LLM + Few-shot Learning | Powered by Google Gemini/Groq/Ollama and LangChain | Made with Streamlit")
