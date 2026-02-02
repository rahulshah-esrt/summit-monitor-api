# main.py
from fastapi import FastAPI
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

app = FastAPI(title="Summit Monitor API", version="1.0", description="Sample API for GPT Actions")

class Item(BaseModel):
    title: str
    channel: str
    published_at: str
    url: str
    summary: Optional[str] = None

@app.get("/", summary="Root health")
def root():
    return {"ok": True, "message": "Summit Monitor API running"}

@app.get("/latest", response_model=dict, summary="Latest items")
def latest(since_days: int = 7):
    # placeholder data — will be replaced later with real collectors
    return {
        "results": [
            Item(
                title="Sample Summit update",
                channel="website",
                published_at=datetime.utcnow().isoformat(),
                url="https://example.com/press",
                summary="Placeholder item from /latest"
            ).dict()
        ]
    }

@app.get("/search", response_model=dict, summary="Search items")
def search(q: str, since_days: int = 30):
    # placeholder search result
    return {
        "results": [
            Item(
                title=f"Sample search result for: {q}",
                channel="social",
                published_at=datetime.utcnow().isoformat(),
                url="https://example.com/social",
                summary="Placeholder item from /search"
            ).dict()
        ]
    }
