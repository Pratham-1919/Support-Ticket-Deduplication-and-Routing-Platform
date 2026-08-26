# src/ml/similarity_search.py


"""
Similarity Search for Support Tickets

Purpose:
    1. Accept a new ticket title + description.
    2. Generate an embedding using the SAME model used during
       the original ticket embedding process.
    3. Search ChromaDB for the most similar existing tickets.
    4. Fetch the matching ticket information from PostgreSQL.
    5. Return ticket IDs, titles, descriptions and similarity scores.

Architecture:

    New Ticket
        |
        v
    Embedding Model
        |
        v
    ChromaDB
        |
        v
    Top-K Similar Tickets
        |
        v
    PostgreSQL
        |
        v
    Ticket details
"""

import os
import sys
from src.core.logging_config import logger

import chromadb
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

from src.db.session import SessionLocal
from src.db.models import Ticket, Module

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# CONFIGURATION
# ============================================================

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "all-MiniLM-L6-v2"
)

CHROMA_PATH = os.getenv(
    "CHROMA_PATH",
    os.path.join(PROJECT_ROOT, "chroma_db")
)

CHROMA_COLLECTION = os.getenv(
    "CHROMA_COLLECTION",
    "support_tickets"
)

DEFAULT_TOP_K = int(
    os.getenv("SIMILARITY_TOP_K", "5")
)

SIMILARITY_THRESHOLD = float(
    os.getenv("SIMILARITY_THRESHOLD", "0.80")
)


# ============================================================
# LOAD EMBEDDING MODEL
# ============================================================

print("=" * 70)
print("LOADING EMBEDDING MODEL")
print("=" * 70)

print(f"Model: {EMBEDDING_MODEL}")

model = SentenceTransformer(EMBEDDING_MODEL)

print("Embedding model loaded.")


# ============================================================
# CONNECT TO CHROMADB
# ============================================================

print()
print("=" * 70)
print("CONNECTING TO CHROMADB")
print("=" * 70)

print(f"ChromaDB path: {CHROMA_PATH}")
print(f"Collection: {CHROMA_COLLECTION}")

chroma_client = chromadb.PersistentClient(
    path=CHROMA_PATH
)

try:
    collection = chroma_client.get_collection(
        name=CHROMA_COLLECTION
    )
except Exception as error:
    raise RuntimeError(
        f"""
Could not find ChromaDB collection '{CHROMA_COLLECTION}'.

Make sure that:

1. embedding.py has already been executed.
2. similarity_search.py is using the SAME ChromaDB path.
3. similarity_search.py is using the SAME collection name.

ChromaDB path:
{CHROMA_PATH}

Original error:
{error}
"""
    )

print("ChromaDB collection loaded.")

try:
    chroma_count = collection.count()
    print(f"ChromaDB records: {chroma_count}")
except Exception:
    chroma_count = None


# ============================================================
# TEXT PREPARATION
# ============================================================

from src.ml.ticket_text import build_ticket_text as prepare_ticket_text


# ============================================================
# SIMILARITY SEARCH
# ============================================================

def search_similar_tickets(
    title,
    description,
    top_k=DEFAULT_TOP_K,
    threshold=None
):
    """
    Search ChromaDB for tickets similar to a new ticket.
    """

    if threshold is None:
        threshold = SIMILARITY_THRESHOLD

    ticket_text = prepare_ticket_text(title, description)

    if not ticket_text.strip():
        raise ValueError(
            "Ticket title and description cannot both be empty."
        )

    print()
    print("Generating embedding for new ticket...")

    query_embedding = model.encode(
        ticket_text,
        normalize_embeddings=True
    )

    query_embedding = query_embedding.tolist()

    print(
        f"Searching ChromaDB for top {top_k} similar tickets..."
    )

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=[
            "metadatas",
            "documents",
            "distances"
        ]
    )

    if not results or not results.get("ids"):
        return []

    result_ids = results["ids"][0]
    result_metadatas = results.get("metadatas", [[]])[0]
    result_documents = results.get("documents", [[]])[0]
    result_distances = results.get("distances", [[]])[0]

    candidates = []

    for index, chroma_id in enumerate(result_ids):

        metadata = (
            result_metadatas[index]
            if index < len(result_metadatas)
            else {}
        )
        document = (
            result_documents[index]
            if index < len(result_documents)
            else None
        )
        distance = (
            result_distances[index]
            if index < len(result_distances)
            else None
        )

        # squared L2 distance on unit vectors -> cosine similarity
        similarity = None
        if distance is not None:
            similarity = 1.0 - (float(distance) / 2.0)

        ticket_id = metadata.get("ticket_id")
        if ticket_id is None:
            ticket_id = chroma_id

        candidates.append(
            {
                "ticket_id": str(ticket_id),
                "chroma_id": str(chroma_id),
                "similarity_score": similarity,
                "distance": distance,
                "metadata": metadata,
                "document": document,
            }
        )

    candidates = enrich_from_postgresql(candidates)

    for candidate in candidates:
        similarity = candidate["similarity_score"]
        if similarity is not None:
            candidate["above_threshold"] = (similarity >= threshold)
        else:
            candidate["above_threshold"] = False

    return candidates


# ============================================================
# POSTGRESQL ENRICHMENT
# ============================================================

def enrich_from_postgresql(candidates):
    """
    Fetch full ticket information from PostgreSQL via SQLAlchemy.
    """
    if not candidates:
        return candidates

    db = SessionLocal()
    try:
        for candidate in candidates:
            ticket_id = str(candidate["ticket_id"])

            result = (
                db.query(Ticket, Module.name)
                .join(Module, Ticket.module_id == Module.id)
                .filter(
                    (Ticket.external_id == ticket_id)
                    | (Ticket.id == int(ticket_id) if ticket_id.isdigit() else False)
                )
                .first()
            )

            if result:
                t, module_name = result
                candidate["postgres"] = {
                    "id": t.id,
                    "external_id": t.external_id,
                    "module": module_name,
                    "ticket_type": t.ticket_type,
                    "title": t.title,
                    "description": t.description,
                    "component": t.component,
                    "product": t.product,
                    "version": t.version,
                    "severity": t.severity,
                    "priority": t.priority,
                    "status": t.status,
                    "resolution": t.resolution,
                }
            else:
                candidate["postgres"] = None
    except Exception as error:
        logger.warning(f"WARNING: Could not enrich results from PostgreSQL.\nError: {error}")
        for candidate in candidates:
            candidate["postgres"] = None
    finally:
        db.close()

    return candidates


# ============================================================
# PRINT RESULTS
# ============================================================

def print_results(results, threshold=SIMILARITY_THRESHOLD):
    print()
    print("=" * 70)
    print("SIMILAR TICKET RESULTS")
    print("=" * 70)

    if not results:
        print("No similar tickets found.")
        return

    for index, result in enumerate(results, start=1):
        postgres_data = result.get("postgres")

        print()
        print("-" * 70)
        print(f"Rank: {index}")
        print(f"Ticket ID: {result['ticket_id']}")

        similarity = result.get("similarity_score")

        if similarity is not None:
            print(f"Similarity: {similarity:.4f}")
            print(f"Threshold: {threshold:.4f}")
            if similarity >= threshold:
                print("Decision: POSSIBLE DUPLICATE")
            else:
                print("Decision: BELOW DUPLICATE THRESHOLD")
        else:
            print("Similarity: N/A")

        if postgres_data:
            print(f"Module: {postgres_data['module']}")
            print(f"Type: {postgres_data['ticket_type']}")
            print(f"Title: {postgres_data['title']}")
            print(f"Severity: {postgres_data['severity']}")
            print(f"Status: {postgres_data['status']}")
        else:
            print("PostgreSQL ticket information: NOT FOUND")


def get_ticket_details(ticket_id):
    """
    Fetch minimal ticket details (id, title, description) via SQLAlchemy.
    """
    db = SessionLocal()
    try:
        t = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if t is None:
            return None
        return {
            "ticket_id": t.id,
            "title": t.title,
            "description": t.description,
        }
    finally:
        db.close()


# ============================================================
# MANUAL TEST
# ============================================================

def main():
    print()
    print("=" * 70)
    print("SUPPORT TICKET SIMILARITY SEARCH")
    print("=" * 70)

    print()
    print(
        f"ChromaDB records: {chroma_count}"
        if chroma_count is not None
        else "ChromaDB record count unavailable."
    )

    title = input("\nEnter new ticket title: ").strip()
    description = input("Enter new ticket description: ").strip()

    if not title and not description:
        print("ERROR: Title and description cannot both be empty.")
        return

    results = search_similar_tickets(
        title=title,
        description=description,
        top_k=DEFAULT_TOP_K,
        threshold=SIMILARITY_THRESHOLD
    )

    print_results(results, threshold=SIMILARITY_THRESHOLD)


if __name__ == "__main__":
    main()