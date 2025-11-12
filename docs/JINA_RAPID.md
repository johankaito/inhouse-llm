# Jina Rapid Proxy for Twin

Twin’s `web_fetch` tool can optionally talk to a local Jina-inspired proxy instead of parsing HTML itself. The proxy reproduces the behavior of `https://r.jina.ai/<url>` so you can avoid remote rate limits and keep the extraction logic under your control.

## What it does

- Fetches arbitrary HTML pages using `httpx`
- Strips boilerplate via `justext` (English stoplist by default)
- Returns a JSON payload with `url`, `title`, `text`, `status_code`, and timing metadata
- Caps the returned text to `MAX_CONTENT_LENGTH` characters (25k by default) so Twin doesn’t overload

## Running the service

From the repo root:

```bash
cd jina-rapid
# either bring up docker compose (preferred)...
docker compose up --build
# ...or use the included venv
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn rapid_service:app --host 0.0.0.0 --port 8000
```

Docker automatically exposes port `8000`. Once running, the health check and fetch endpoints are:

- `GET http://localhost:8000/` – quick health/status
- `GET http://localhost:8000/fetch?url=https://example.com` – cleaned document

Use `curl` to sanity-check:

```bash
curl "http://localhost:8000/fetch?url=https://www.qantas.com" | jq
```

## Connecting Twin

Tell Twin to use the proxy instead of the built-in parser:

```bash
export TWIN_JINA_RAPID_URL=http://127.0.0.1:8000/fetch
twin
```

When the variable is present, `twin` prefers the proxy and returns the `title` plus cleaned `text`. If the service is down it falls back to the original `requests + BeautifulSoup` path.

You can add the `export` command to your shell profile or wrap Twin in a launcher script so it’s always available while you run local sessions.
