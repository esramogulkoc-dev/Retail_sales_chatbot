import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.utilities import SQLDatabase
from langchain_experimental.sql import SQLDatabaseChain
from langchain.prompts import FewShotPromptTemplate, PromptTemplate
from langchain.embeddings.huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.example_selectors.semantic_similarity import SemanticSimilarityExampleSelector
from few_shots import few_shots

# Load environment variables
load_dotenv()

def get_few_shot_db_chain():
    """
    Creates and returns a SQLDatabaseChain with few-shot prompt using semantic similarity.

    Returns:
        SQLDatabaseChain: The configured database chain with LLM and few-shot examples
    """

    provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    api_key = os.getenv("GOOGLE_API_KEY")

    # Initialize SQLite database
    db = SQLDatabase.from_uri("sqlite:///data/tshirts.db")

    # Initialize LLM
    if provider == "ollama":
        llm = ChatOllama(
            model=os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0")),
            base_url=os.getenv("OLLAMA_API_URL", "http://127.0.0.1:11434"),
        )
    elif provider == "groq":
        if not os.getenv("GROQ_API_KEY"):
            raise ValueError("GROQ_API_KEY not found in .env file")
        llm = ChatGroq(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0")),
            api_key=os.getenv("GROQ_API_KEY"),
        )
    elif provider in {"gemini", "google", "google_gemini", "google_generative"}:
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in .env file")
        llm = ChatGoogleGenerativeAI(
            model=os.getenv("GOOGLE_MODEL", "gemini-2.5-flash"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0")),
            google_api_key=api_key,
        )
    else:
        raise ValueError("Unsupported LLM_PROVIDER. Use ollama, groq, or gemini.")

    # Initialize embeddings
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    # Create semantic similarity example selector
    example_selector = SemanticSimilarityExampleSelector.from_examples(
        few_shots,
        embeddings,
        Chroma,
        k=2  # Select top 2 examples
    )

    # Create few-shot prompt template
    few_shot_prompt = FewShotPromptTemplate(
        example_selector=example_selector,
        example_prompt=PromptTemplate(
            input_variables=["input", "query", "answer"],
            template="Input: {input}\nSQL Query: {query}\nAnswer: {answer}"
        ),
        prefix="""You are a SQLite database expert. Given an input question, first create a syntactically correct SQLite query to run, then look at the results of the query and return a natural language answer.

Schema of the database:
- t_shirts table: t_shirt_id (INTEGER), brand (TEXT), color (TEXT), size (TEXT), price (INTEGER), stock_quantity (INTEGER)
- discounts table: discount_id (INTEGER), t_shirt_id (INTEGER), pct_discount (DECIMAL)

Use SQLite functions like SUM, COUNT, AVG, GROUP BY, etc.

Here are some examples:""",
        suffix="Input: {input}\nSQL Query:",
        input_variables=["input"]
    )

    # Create SQLDatabaseChain
    db_chain = SQLDatabaseChain.from_llm(
        llm,
        db,
        prompt=few_shot_prompt,
        verbose=True
    )

    return db_chain


def run_query(question: str) -> str:
    """
    Runs a natural language question against the database.

    Args:
        question (str): The natural language question

    Returns:
        str: The answer from the database
    """
    chain = get_few_shot_db_chain()
    answer = chain.run(question)
    return answer


if __name__ == "__main__":
    # Test the chain
    test_question = "How many total t-shirts are left in stock?"
    print(f"Question: {test_question}")
    answer = run_query(test_question)
    print(f"Answer: {answer}")
