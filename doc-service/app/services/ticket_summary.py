import os
from pathlib import Path
from datetime import datetime

import httpx
from dotenv import load_dotenv


# ============================================================
# Load environment variables
# ============================================================

load_dotenv()


# ============================================================
# Configuration
# ============================================================

TICKET_SERVICE_URL = os.getenv(
    "TICKET_SERVICE_URL",
    "http://localhost:8000",
)

INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")

if not INTERNAL_API_KEY:
    raise RuntimeError(
        "INTERNAL_API_KEY is not set in doc-service .env"
    )


# ============================================================
# Storage directory
# ============================================================

STORAGE_DIR = (
    Path(__file__).resolve().parents[1]
    / "storage"
    / "ticket_summaries"
)

STORAGE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# Fetch ticket from ticket-service
# ============================================================

def fetch_ticket(ticket_id: int):
    """
    Fetch ticket information from the main ticket service
    using internal service-to-service authentication.
    """

    headers = {
        "X-Internal-Key": INTERNAL_API_KEY
    }

    response = httpx.get(
        f"{TICKET_SERVICE_URL}/tickets/{ticket_id}",
        headers=headers,
        timeout=10.0,
    )

    # Give us a useful error instead of only:
    # "502 Bad Gateway"
    if response.status_code != 200:
        raise RuntimeError(
            f"Ticket service returned "
            f"{response.status_code}: "
            f"{response.text}"
        )

    return response.json()


# ============================================================
# Generate ticket summary
# ============================================================

def generate_ticket_summary(ticket_id: int) -> Path:
    """
    Fetch the ticket from ticket-service and generate
    a plain-text summary file.
    """

    ticket = fetch_ticket(ticket_id)

    lines = [
        "TICKET SUMMARY",
        "=" * 60,

        f"Ticket ID: {ticket['id']}",
        f"External ID: {ticket['external_id']}",
        f"Title: {ticket['title']}",
        f"Module: {ticket['module']}",
        f"Component: {ticket.get('component') or 'N/A'}",
        f"Type: {ticket['ticket_type']}",
        f"Severity: {ticket.get('severity') or 'N/A'}",
        f"Priority: {ticket.get('priority') or 'N/A'}",
        f"Status: {ticket['status']}",
        f"Resolution: {ticket.get('resolution') or 'N/A'}",

        "",

        "Description:",
        ticket.get("description") or "N/A",

        "",

        f"Generated: {datetime.utcnow().isoformat()}Z",
    ]

    file_path = (
        STORAGE_DIR
        / f"ticket_{ticket_id}_summary.txt"
    )

    file_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    return file_path