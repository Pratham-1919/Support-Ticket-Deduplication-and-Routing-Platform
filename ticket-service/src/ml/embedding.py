"""
PostgreSQL -> Embeddings -> ChromaDB

Reads historical tickets from the PostgreSQL `tickets` table
in batches, generates embeddings from:

    title + description

and stores them in a persistent ChromaDB collection.

PostgreSQL remains the source of truth.
ChromaDB is used for vector similarity search.
"""

from pathlib import Path
import sys

import chromadb
from sentence_transformers import SentenceTransformer


# ============================================================
# MAKE src/ AVAILABLE FOR IMPORT
# ============================================================

# Current file:
# src/ml/embedding_generator.py
#
# parents[0] -> ml
# parents[1] -> src
# parents[2] -> project root

PROJECT_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(PROJECT_ROOT / "src"))


# ============================================================
# IMPORT POSTGRES CONNECTION
# ============================================================

from src.db.connection import get_connection


# ============================================================
# CONFIGURATION
# ============================================================

# Persistent ChromaDB directory
CHROMA_PATH = PROJECT_ROOT / "chroma_db"

# ChromaDB collection name
COLLECTION_NAME = "eclipse_tickets"

# Embedding model
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Number of tickets fetched from PostgreSQL at once
DB_BATCH_SIZE = 1000

# Number of texts encoded together by the embedding model
EMBEDDING_BATCH_SIZE = 100


# ============================================================
# TEST MODE
# ============================================================

# Start with 1000 tickets.
#
# After everything works correctly, change this to:
#
# MAX_TICKETS = None
#
# Then the complete tickets table will be processed.

MAX_TICKETS = None


# ============================================================
# CHROMADB
# ============================================================

def get_chroma_collection():
    """
    Create or open the persistent ChromaDB collection.
    """

    print("\nConnecting to ChromaDB...")
    print(f"ChromaDB path: {CHROMA_PATH}")

    CHROMA_PATH.mkdir(
        parents=True,
        exist_ok=True
    )

    client = chromadb.PersistentClient(
        path=str(CHROMA_PATH)
    )

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={
            "description": "Historical Eclipse support tickets"
        }
    )

    print("ChromaDB connection successful.")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Existing records: {collection.count()}")

    return collection


# ============================================================
# EMBEDDING MODEL
# ============================================================

def load_embedding_model():
    """
    Load the embedding model.
    """

    print("\nLoading embedding model...")
    print(f"Model: {MODEL_NAME}")

    model = SentenceTransformer(MODEL_NAME)

    print("Embedding model loaded successfully.")

    return model


# ============================================================
# CREATE TEXT FOR EMBEDDING
# ============================================================

from src.ml.ticket_text import build_ticket_text as create_ticket_text


# ============================================================
# GENERATE AND STORE EMBEDDINGS
# ============================================================

def generate_embeddings(
    connection,
    collection,
    model
):
    """
    Read tickets from PostgreSQL in chunks,
    generate embeddings and store them in ChromaDB.
    """

    print("\n" + "=" * 70)
    print("POSTGRESQL -> EMBEDDINGS -> CHROMADB")
    print("=" * 70)

    cursor = connection.cursor(
        name="ticket_embedding_cursor"
    )

    query = """
        SELECT
            external_id,
            title,
            description,
            module_id,
            severity,
            ticket_type
        FROM tickets
        ORDER BY id
    """

    cursor.execute(query)

    total_processed = 0

    while True:

        # ----------------------------------------------------
        # Determine how many rows to fetch
        # ----------------------------------------------------

        if MAX_TICKETS is not None:

            remaining = (
                MAX_TICKETS - total_processed
            )

            if remaining <= 0:
                break

            fetch_size = min(
                DB_BATCH_SIZE,
                remaining
            )

        else:

            fetch_size = DB_BATCH_SIZE

        # ----------------------------------------------------
        # Fetch a batch
        # ----------------------------------------------------

        rows = cursor.fetchmany(fetch_size)

        if not rows:
            break

        print(
            f"\nFetched {len(rows)} tickets "
            f"from PostgreSQL."
        )

        ids = []
        documents = []
        metadatas = []

        # ----------------------------------------------------
        # Prepare ticket documents
        # ----------------------------------------------------

        for row in rows:

            (
                external_id,
                title,
                description,
                module_id,
                severity,
                ticket_type
            ) = row

            document = create_ticket_text(
                title,
                description
            )

            # Skip empty tickets
            if not document:
                print(
                    f"Skipping ticket {external_id}: "
                    "empty title and description."
                )
                continue

            ids.append(
                str(external_id)
            )

            documents.append(
                document
            )

            metadatas.append(
                {
                    "ticket_id": str(external_id),

                    "module_id": (
                        str(module_id)
                        if module_id is not None
                        else ""
                    ),

                    "severity": (
                        str(severity)
                        if severity is not None
                        else ""
                    ),

                    "ticket_type": (
                        str(ticket_type)
                        if ticket_type is not None
                        else ""
                    )
                }
            )

        if not documents:
            continue

        # ----------------------------------------------------
        # Generate embeddings
        # ----------------------------------------------------

        print(
            f"Generating embeddings for "
            f"{len(documents)} tickets..."
        )

        embeddings = model.encode(
            documents,
            batch_size=EMBEDDING_BATCH_SIZE,
            show_progress_bar=True,
            normalize_embeddings=True
        )

        # Convert numpy array to Python list
        embeddings = embeddings.tolist()

        # ----------------------------------------------------
        # Store embeddings in ChromaDB
        # ----------------------------------------------------

        print(
            f"Storing {len(ids)} embeddings "
            f"in ChromaDB..."
        )

        collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )

        total_processed += len(rows)

        print(
            f"PostgreSQL tickets processed: "
            f"{total_processed}"
        )

        print(
            f"ChromaDB records: "
            f"{collection.count()}"
        )

    cursor.close()

    print("\n" + "=" * 70)
    print("EMBEDDING GENERATION COMPLETED")
    print("=" * 70)

    print(
        f"Tickets processed: {total_processed}"
    )

    print(
        f"ChromaDB records: {collection.count()}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n" + "=" * 70)
    print("ECLIPSE TICKETS EMBEDDING PIPELINE")
    print("=" * 70)

    print(
        f"\nProject root:\n{PROJECT_ROOT}"
    )

    print(
        f"\nChromaDB location:\n{CHROMA_PATH}"
    )

    connection = None

    try:

        # ----------------------------------------------------
        # PostgreSQL
        # ----------------------------------------------------

        print("\nConnecting to PostgreSQL...")

        connection = get_connection()

        print(
            "PostgreSQL connection successful."
        )

        # ----------------------------------------------------
        # ChromaDB
        # ----------------------------------------------------

        collection = get_chroma_collection()

        # ----------------------------------------------------
        # Embedding model
        # ----------------------------------------------------

        model = load_embedding_model()

        # ----------------------------------------------------
        # Process tickets
        # ----------------------------------------------------

        generate_embeddings(
            connection=connection,
            collection=collection,
            model=model
        )

    except Exception as error:

        print("\nERROR")
        print("-" * 70)
        print(
            f"{type(error).__name__}: {error}"
        )

        raise

    finally:

        if connection is not None:

            connection.close()

            print(
                "\nPostgreSQL connection closed."
            )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()