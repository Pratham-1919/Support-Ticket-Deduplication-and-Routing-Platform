import os
from pathlib import Path
from datetime import datetime, date
import httpx

TICKET_SERVICE_URL = os.getenv("TICKET_SERVICE_URL", "http://localhost:8000")
STORAGE_DIR = Path(__file__).resolve().parents[1] / "storage" / "weekly_reports"
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def fetch_weekly_stats():
    headers = {"X-Internal-Key": INTERNAL_API_KEY}
    resp = httpx.get(f"{TICKET_SERVICE_URL}/tickets/stats/weekly", headers=headers, timeout=10.0)
    resp.raise_for_status()
    return resp.json()


def generate_weekly_report() -> Path:
    stats = fetch_weekly_stats()

    lines = [
        f"WEEKLY TICKET REPORT",
        f"=" * 60,
        f"Period: {stats['period']}",
        f"Generated: {datetime.utcnow().isoformat()}Z",
        f"",
        f"Tickets received: {stats['tickets_received']}",
        f"Duplicates detected: {stats['duplicates_detected']}",
        f"Duplicate rate: {stats['duplicate_rate'] * 100:.2f}%",
        f"",
        f"Most affected modules:",
    ]
    for m in stats["most_affected_modules"]:
        lines.append(f"  - {m['module']}: {m['count']} tickets")

    today_str = date.today().isoformat()
    file_path = STORAGE_DIR / f"weekly_report_{today_str}.txt"
    file_path.write_text("\n".join(lines), encoding="utf-8")
    return file_path