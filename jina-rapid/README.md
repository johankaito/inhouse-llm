# Twin Jina Rapid Proxy

A small FastAPI service that mirrors the `https://r.jina.ai/<url>` workflow used by Claude and Twin's `web_fetch` tool.
It fetches a web page, strips boilerplate, and returns plain text so your local Twin instance can rely on it instead of hitting Jina's public proxy.

## Run it

### 1. Docker (recommended)

```bash
cd jina-rapid
docker compose up --build
```

The endpoint listens on `http://0.0.0.0:8000` by default. Docker will rebuild the image when dependencies change.

### 2. Python (if you prefer not to use Docker)

```bash
cd jina-rapid
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn rapid_service:app --host 0.0.0.0 --port 8000
```

## API

- `GET /fetch?url=<URL>&lang=<language>` — returns JSON `{url, title, text, status_code, elapsed_seconds}`.
- `GET /` — health check, returns the same schema with a placeholder text.

The response truncates text at `MAX_CONTENT_LENGTH` characters (default 25k, override with `MAX_CONTENT_LENGTH`).

## Integration with Twin

Set the environment variable before starting Twin so it prefers this local service instead of the built-in HTML parser:

```bash
export TWIN_JINA_RAPID_URL=http://127.0.0.1:8000/fetch
```

If the service is available, `twin` will call it and return the cleaned text plus metadata, falling back to `lib/tools.py`'s HTML converter if the proxy is unreachable.

## Notes

- Avoid downloading large files through this plane; it is intended for HTML pages only.
- The `jina-rapid/cache/` directory is ignored to keep the repo clean.
- Docker Compose injects a generous request timeout and auto-restarts on failure for resiliency.
