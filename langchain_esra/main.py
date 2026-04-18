import ast

import streamlit as st

from langchain_helper import ask, get_few_shot_db_chain


def format_rows(rows):
    """Return a scalar if rows is [(x,)], a flat list if single-column, else the raw repr."""
    if isinstance(rows, str):
        try:
            rows = ast.literal_eval(rows)
        except (ValueError, SyntaxError):
            return rows
    try:
        rows = [tuple(r) for r in rows]
    except TypeError:
        return str(rows)
    if len(rows) == 1 and len(rows[0]) == 1:
        return str(rows[0][0])
    if rows and all(len(r) == 1 for r in rows):
        return str([r[0] for r in rows])
    return str(rows)


st.set_page_config(
    page_title="T-Shirts - Database Q&A",
    page_icon="",
    layout="centered",
)

st.title("T-Shirts: Database Q&A")
st.caption("Ask natural language questions about t-shirt inventory, prices and discounts.")


@st.cache_resource(show_spinner="Loading few-shot chain...")
def load_chain():
    return get_few_shot_db_chain()


with st.sidebar:
    st.header("Sample questions")
    samples = [
        "How many total t-shirts are left in stock?",
        "How many red color Adidas t-shirts do we have?",
        "What is the total inventory value of all extra large size t-shirts?",
        "Which brand has the highest average price per shirt?",
        "If we have to sell all Van Huesen  t-shirts, what would be the total revenue with discount?",
    ]
    for q in samples:
        if st.button(q, key=f"sample_{q}"):
            st.session_state["question"] = q


question = st.text_input(
    "Your question:",
    value=st.session_state.get("question", ""),
    placeholder="e.g., How many Nike t-shirts do we have in XS size?",
)

if st.button("Ask", type="primary") and question:
    with st.spinner("Generating SQL and running the query..."):
        try:
            chain = load_chain()
            response = ask(chain, question)

            strategy = response.get("strategy", "unknown")
            if strategy == "direct":
                st.success("Strategy: direct LLM (passed validation)")
            elif strategy == "fewshot":
                st.warning("Strategy: few-shot fallback (direct LLM failed validation)")
            else:
                st.info(f"Strategy: {strategy}")

            st.subheader("Answer")
            st.code(format_rows(response.get("result")), language="python")

            sql = response.get("sql")
            if sql:
                with st.expander("Generated SQL", expanded=False):
                    st.code(sql, language="sql")

            attempts = response.get("attempts", [])
            if attempts:
                with st.expander("Attempts / validation trace", expanded=False):
                    for i, a in enumerate(attempts, 1):
                        st.markdown(f"**{i}. {a.get('strategy')}**")
                        if a.get("sql"):
                            st.code(a["sql"], language="sql")
                        if a.get("error"):
                            st.caption(f"Failed: {a['error']}")
                        elif a.get("ok"):
                            st.caption("OK")
        except Exception as e:
            st.error(f"Error: {e}")
