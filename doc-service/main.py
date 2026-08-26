from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()

from app.routes import documents  

app = FastAPI(
    title="Ticket Document & Notification Service",
    description="Generates ticket summaries and weekly reports; handles notifications.",
    version="1.0.0",
)

app.include_router(documents.router)

@app.get("/health")
def health():
    return {"status": "healthy"}