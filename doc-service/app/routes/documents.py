from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import FileResponse
from pathlib import Path

from app.services.ticket_summary import generate_ticket_summary, STORAGE_DIR as SUMMARY_DIR
from app.services.weekly_report import generate_weekly_report, STORAGE_DIR as REPORT_DIR

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/ticket-summary")
def create_ticket_summary(ticket_id: int):
    try:
        path = generate_ticket_summary(ticket_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to generate summary: {e}")

    return {"ticket_id": ticket_id, "filename": path.name,
            "download_url": f"/documents/ticket-summary/{ticket_id}/download"}


@router.get("/ticket-summary/{ticket_id}/download")
def download_ticket_summary(ticket_id: int):
    path = SUMMARY_DIR / f"ticket_{ticket_id}_summary.txt"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Summary not found. Generate it first.")
    return FileResponse(path, filename=path.name, media_type="text/plain")


@router.post("/weekly-report")
def create_weekly_report():

    try:
        path = generate_weekly_report()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to generate report: {e}")

    return {"filename": path.name,
            "download_url": f"/documents/weekly-report/{path.stem.replace('weekly_report_', '')}/download"}




@router.get("/weekly-report/{report_date}/download")
def download_weekly_report(report_date: str):
    path = REPORT_DIR / f"weekly_report_{report_date}.txt"

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="Report not found for that date."
        )

    return FileResponse(
        path,
        filename=path.name,
        media_type="text/plain"
    )