"""Lightweight twin-facing proxy that mirrors r.jina.ai functionality."""
import os
import time
from typing import Optional

import httpx
import justext
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", "25000"))
DEFAULT_USER_AGENT = os.getenv(
    "JINA_RAPID_USER_AGENT",
    "TwinJinaRapid/1.0 (+https://github.com/johankaito/inhouse-llm)"
)

app = FastAPI(title="Twin Jina Rapid Proxy", version="0.1")


class FetchResponse(BaseModel):
    url: str
    title: Optional[str]
    text: str
    status_code: int
    elapsed_seconds: float
    source: str = Field("twin-jina-rapid")


def _extract_title(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        return title_tag.string.strip()
    return None


def _extract_text(content: bytes, lang: str) -> str:
    paragraphs = justext.justext(content, justext.get_stoplist(lang))
    filtered = [p.text.strip() for p in paragraphs if not p.is_boilerplate and p.text.strip()]

    if filtered:
        return "\n\n".join(filtered)

    soup = BeautifulSoup(content, "html.parser")
    return soup.get_text(separator="\n")


@app.get("/", response_model=FetchResponse)
async def health_check() -> FetchResponse:
    """Basic health endpoint so the twin can verify the service is alive."""
    return FetchResponse(
        url="health",
        title="Twin Jina Rapid Proxy",
        text="Service is up",
        status_code=200,
        elapsed_seconds=0.0,
    )


@app.get("/fetch", response_model=FetchResponse)
async def fetch(
    url: str = Query(..., description="Target URL to fetch"),
    lang: str = Query("English", description="Language for boilerplate removal"),
) -> FetchResponse:
    """Fetch a URL, extract readable text, and return metadata."""
    start = time.monotonic()
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0, headers=headers) as client:
            response = await client.get(url)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch {url}: {exc}")

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail="Upstream error")

    raw_text = _extract_text(response.content, lang)
    if len(raw_text) > MAX_CONTENT_LENGTH:
        truncated = raw_text[:MAX_CONTENT_LENGTH].rstrip()
        raw_text = f"{truncated}\n\n[Content truncated to {MAX_CONTENT_LENGTH} characters]"

    elapsed = time.monotonic() - start
    return FetchResponse(
        url=url,
        title=_extract_title(response.text),
        text=raw_text,
        status_code=response.status_code,
        elapsed_seconds=elapsed,
    )
