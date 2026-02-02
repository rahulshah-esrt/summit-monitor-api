from fastapi import FastAPI
from datetime import datetime

app = FastAPI(
    title="Summit Monitor API",
    description="Public-source competitive intelligence API",
    version="1.0"
)

@app.get("/latest")
def latest(since_days: int = 7):
    # TODO: later, replace with real data
    return {
        "results": [
            {
                "title": "Sample Summit update",
                "channel": "website",
                "published_at": datetime.utcnow().isoformat(),
                "url": "https://example.com/press",
                "summary": "This is placeholder data from /latest."
            }
        ]
    }

@app.get("/search")
def search(q: str, since_days: int = 30):
    # TODO: later, replace with real search over your collected data
    return {
        "results": [
            {
                "title": f"Sample result for query: {q}",
                "channel": "social",
                "published_at": datetime.utcnow().isoformat(),
                "url": "https://example.com/social",
                "summary": "This is placeholder data from /search."
            }
        ]
    }


