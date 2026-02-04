from fastapi import FastAPI, Header, HTTPException
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import sqlite3
import hashlib
import os

import httpx
from bs4 import BeautifulSoup

# =========================
# App setup
# =========================
app = FastAPI(
    title="SummitOV Monitor API",
    version="1.0",
    description="Tracks changes on SummitOV public pages for GPT Actions"
)

# =========================
# SEED URLS (ADD MORE LATER)
# =========================
SEED_URLS = [
    "https://summitov.com/",
    "https://summitov.com/tickets/",
]
# =========================
# SOCIAL ACCOUNTS (CONFIG ONLY)
# =========================
SOCIAL_ACCOUNTS = {
    "instagram": "summitov",
    "facebook": "https://www.facebook.com/SummitOV/",
    "twitter": "https://twitter.com/summitOV",
    "linkedin": "https://www.linkedin.com/company/summit-one-vanderbilt/",
    "tiktok": "https://www.tiktok.com/@summitov",
    "youtube": "https://www.youtube.com/channel/UCE7l8RccNbjuc_h_Rp3vriQ"
}

DB_PATH = os.getenv("DB_PATH", "data.db")
API_KEY = os.getenv("API_KEY", "")  # optional auth for /refresh

# =========================
# Models
# =========================
class Item(BaseModel):
    title: str
    channel: str
    published_at: str
    url: str
    summary: Optional[str] = None

# =========================
# Database helpers
# =========================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS page_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            title TEXT,
            text_content TEXT,
            content_hash TEXT
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_url_time
        ON page_snapshots(url, fetched_at)
    """)
    conn.commit()
    conn.close()

@app.on_event("startup")
def startup():
    init_db()

# =========================
# Utility functions
# =========================
def sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()

def extract_text(html: str) -> Dict[str, str]:
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = soup.title.get_text(strip=True) if soup.title else ""
    main = soup.find("main")
    node = main if main else soup.body if soup.body else soup

    text = " ".join(node.get_text(separator=" ", strip=True).split())
    text = text[:20000]  # keep DB small

    return {"title": title, "text": text}

async def fetch_page(url: str) -> Dict[str, str]:
    headers = {"User-Agent": "SummitOV-Monitor/1.0"}
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=headers) as client:
        r = await client.get(url)
        r.raise_for_status()
        parsed = extract_text(r.text)
        parsed["url"] = url
        return parsed

def require_api_key(auth: Optional[str]):
    if not API_KEY:
        return
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    if auth.replace("Bearer ", "").strip() != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid token")

# =========================
# Routes
# =========================
@app.get("/")
def root():
    return {
        "ok": True,
        "message": "SummitOV Monitor running",
        "tracked_urls": SEED_URLS
    }

@app.post("/refresh")
async def refresh(authorization: Optional[str] = Header(default=None)):
    """
    Fetches all seed URLs and stores snapshots.
    Marks whether each page changed since last fetch.
    """
    require_api_key(authorization)

    conn = get_db()
    results = []

    try:
        for url in SEED_URLS:
            try:
                parsed = await fetch_page(url)
                title = parsed["title"]
                text = parsed["text"]
                h = sha256(text)

                prev = conn.execute(
                    "SELECT content_hash FROM page_snapshots WHERE url = ? ORDER BY fetched_at DESC LIMIT 1",
                    (url,)
                ).fetchone()
                prev_hash = prev["content_hash"] if prev else None

                changed = (prev_hash != h)

                conn.execute(
                    "INSERT INTO page_snapshots(url, fetched_at, title, text_content, content_hash) VALUES (?, ?, ?, ?, ?)",
                    (url, datetime.now(timezone.utc).isoformat(), title, text, h)
                )

                results.append({
                    "url": url,
                    "title": title,
                    "changed": changed
                })
            except Exception as e:
                results.append({"url": url, "error": str(e)})

        conn.commit()
    finally:
        conn.close()

    return {"results": results}

@app.get("/latest")
def latest(since_days: int = 30):
    """
    Returns pages that changed in the last N days.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
    conn = get_db()

    try:
        rows = conn.execute(
            """
            SELECT * FROM page_snapshots
            WHERE fetched_at >= ?
            ORDER BY url, fetched_at
            """,
            (cutoff.isoformat(),)
        ).fetchall()

        last_hash = {}
        items: List[Item] = []

        for r in rows:
            url = r["url"]
            h = r["content_hash"]
            prev = last_hash.get(url)

            if prev != h:
                items.append(Item(
                    title=r["title"] or "Untitled",
                    channel="website",
                    published_at=r["fetched_at"][:10],
                    url=url,
                    summary=(r["text_content"][:280] + "…") if r["text_content"] else None
                ))

            last_hash[url] = h

        items.sort(key=lambda x: x.published_at, reverse=True)
        return {"results": [i.dict() for i in items]}
    finally:
        conn.close()

@app.get("/search")
def search(q: str, since_days: int = 30):
    """
    Searches stored snapshots for keyword matches.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
    like = f"%{q.strip()}%"
    conn = get_db()

    try:
        rows = conn.execute(
            """
            SELECT * FROM page_snapshots
            WHERE fetched_at >= ?
              AND (title LIKE ? OR text_content LIKE ?)
            ORDER BY fetched_at DESC
            LIMIT 25
            """,
            (cutoff.isoformat(), like, like)
        ).fetchall()

        items = [
            Item(
                title=r["title"] or "Untitled",
                channel="website",
                published_at=r["fetched_at"][:10],
                url=r["url"],
                summary=(r["text_content"][:280] + "…") if r["text_content"] else None
            )
            for r in rows
        ]

        return {"results": [i.dict() for i in items]}
    finally:
        conn.close()

