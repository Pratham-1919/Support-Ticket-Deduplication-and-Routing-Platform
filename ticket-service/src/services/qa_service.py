import os
from typing import Any, Dict, List

from dotenv import load_dotenv
from langchain_groq import ChatGroq

from src.ml.similarity_search import search_similar_tickets


load_dotenv()


# ============================================================
# Q&A configuration
# ============================================================

QA_TOP_K = 5

# Start here and tune this after testing real questions.
QA_RELEVANCE_THRESHOLD = 0.50


# ============================================================
# LLM
# ============================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is not set in .env")


# llm = ChatGroq(
#     api_key=GROQ_API_KEY,
#     model="llama-3.3-70b-versatile",
#     temperature=0.2,
# )


llm = ChatGroq(
    api_key=GROQ_API_KEY,
    model="openai/gpt-oss-120b",
    temperature=0.2
)

# ============================================================
# Retrieve tickets
# ============================================================

def retrieve_relevant_tickets(
    question: str,
    top_k: int = QA_TOP_K,
) -> List[Dict[str, Any]]:
    """
    Retrieve historical tickets relevant to the user's question.

    Reuses the existing ChromaDB similarity-search pipeline.
    """

    results = search_similar_tickets(
        title=question,
        description="",
        top_k=top_k,
    )

    if not results:
        return []

    return results


# ============================================================
# Relevance filtering
# ============================================================

def filter_relevant_tickets(
    results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    return [
        result
        for result in results
        if result.get("similarity_score", 0)
        >= QA_RELEVANCE_THRESHOLD
    ]


# ============================================================
# Build LLM context
# ============================================================

def build_context(
    results: List[Dict[str, Any]],
) -> str:
    """
    Convert retrieved tickets into context for the LLM.
    """

    context_parts = []

    for result in results:

        postgres_data = result.get("postgres") or {}

        ticket_id = result.get("ticket_id")
        similarity = result.get("similarity_score", 0)

        title = postgres_data.get("title") or "No title"
        description = (
            postgres_data.get("description")
            or "No description available"
        )

        # Prevent extremely large ticket descriptions from
        # unnecessarily increasing the prompt size.
        description = " ".join(description.split())

        if len(description) > 1500:
            description = description[:1500] + "..."

        context_parts.append(
            f"""
Ticket ID: {ticket_id}
Title: {title}
Description: {description}
Similarity score: {similarity:.4f}
""".strip()
        )

    return "\n\n---\n\n".join(context_parts)


# ============================================================
# Build source information
# ============================================================

def build_sources(
    results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    sources = []

    for result in results:

        postgres_data = result.get("postgres") or {}

        sources.append(
            {
                "ticket_id": result.get("ticket_id"),
                "title": postgres_data.get("title"),
                "similarity_score": result.get(
                    "similarity_score"
                ),
            }
        )

    return sources


# ============================================================
# Generate answer
# ============================================================

def generate_llm_answer(
    question: str,
    context: str,
) -> str:
    """
    Generate an answer strictly from retrieved ticket context.
    """

    prompt = f"""
You are a support-ticket knowledge assistant.

Your job is to answer questions using ONLY the historical support
tickets provided in the CONTEXT below.

Rules:

1. Use only information supported by the provided tickets.
2. Do not invent ticket information.
3. If the context does not contain enough information to answer the
   question, clearly say that the available tickets do not provide
   enough information.
4. When useful, mention relevant ticket IDs.
5. Do not claim that something is true for the entire ticket database
   unless the supplied context actually proves it.
6. Keep the answer concise and useful to a support engineer.

CONTEXT:

{context}

USER QUESTION:

{question}

ANSWER:
""".strip()

    response = llm.invoke(prompt)

    return response.content


# ============================================================
# Main Q&A function
# ============================================================

def answer_question(question: str) -> Dict[str, Any]:
    """
    Complete RAG Q&A pipeline.

    Question
        ↓
    ChromaDB retrieval
        ↓
    Relevance filtering
        ↓
    Context construction
        ↓
    LLM
        ↓
    Answer + sources
    """

    question = question.strip()

    if not question:
        raise ValueError("Question cannot be empty.")

    # --------------------------------------------------------
    # Retrieve
    # --------------------------------------------------------

    results = retrieve_relevant_tickets(
        question=question,
        top_k=QA_TOP_K,
    )

    if not results:
        return {
            "question": question,
            "answer": (
                "I could not find relevant historical tickets "
                "for this question."
            ),
            "sources": [],
        }

    # --------------------------------------------------------
    # Filter weak matches
    # --------------------------------------------------------

    relevant_results = filter_relevant_tickets(results)

    if not relevant_results:
        return {
            "question": question,
            "answer": (
                "I could not find sufficiently relevant historical "
                "tickets to answer this question."
            ),
            "sources": [],
        }

    # --------------------------------------------------------
    # Build context
    # --------------------------------------------------------

    context = build_context(relevant_results)

    # --------------------------------------------------------
    # Ask LLM
    # --------------------------------------------------------

    answer = generate_llm_answer(
        question=question,
        context=context,
    )

    # --------------------------------------------------------
    # Sources
    # --------------------------------------------------------

    sources = build_sources(relevant_results)

    return {
        "question": question,
        "answer": answer,
        "sources": sources,
    }