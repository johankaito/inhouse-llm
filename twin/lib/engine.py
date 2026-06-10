"""Engine adapters: one chat contract, swappable backends.

The harness contract (docs/architecture/local-first-foundation.md §1):
one base URL, model selected per-request via the model field, engine
specifics never leak above this module. Two adapters:

- OllamaEngine: Ollama's native API. Generation options (num_ctx,
  keep_alive, temperature, top_p) are passed client-side per request.
- OpenAICompatEngine: any OpenAI-compatible /v1/chat/completions server
  (llama-server, llama-swap, LM Studio, vLLM). Context size is a server
  concern there (--ctx-size); num_ctx and keep_alive are not sent.

Both return/yield Ollama-shaped payloads ({'message': {'content': ...}})
so the session layer is engine-agnostic.
"""

import json
import sys
from typing import Any, Dict, Iterator, List, Optional, Union

import requests


class EngineError(Exception):
    pass


class OllamaEngine:
    def __init__(self, base_url: str = "http://localhost:11434", timeout: int = 120):
        self.base_url = base_url
        self.timeout = timeout
        self._client = None

    def _get_client(self):
        if self._client is None:
            import ollama
            self._client = ollama.Client(host=self.base_url, timeout=self.timeout)
        return self._client

    def chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> Union[Dict[str, Any], Iterator[Dict[str, Any]]]:
        client = self._get_client()
        return client.chat(model=model, messages=messages, options=options or {}, stream=stream)


class OpenAICompatEngine:
    # Options that only exist in Ollama's native API; on /v1 servers the
    # context window is set server-side (e.g. llama-server --ctx-size).
    _SERVER_SIDE_OPTIONS = ("num_ctx", "keep_alive")

    def __init__(self, base_url: str, api_key: str = "", timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._warned_ollama_v1 = False

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _warn_if_ollama_v1(self, options: Dict[str, Any]) -> None:
        # Pointing the /v1 adapter at Ollama silently drops num_ctx — the
        # exact silent-truncation failure the foundation doc warns about.
        # Bake the context into the model with a Modelfile instead.
        if self._warned_ollama_v1:
            return
        if ":11434" in self.base_url and any(k in options for k in self._SERVER_SIDE_OPTIONS):
            sys.stderr.write(
                "warning: openai-compat engine pointed at Ollama /v1 — num_ctx is NOT "
                "honoured on this path. Bake it into the model "
                "(ollama create <name>-ctx -f Modelfile with PARAMETER num_ctx) "
                "or use the native ollama provider.\n"
            )
            self._warned_ollama_v1 = True

    def _build_payload(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        options: Dict[str, Any],
        stream: bool,
    ) -> Dict[str, Any]:
        clean_messages = []
        for message in messages:
            if message.get("images"):
                raise EngineError(
                    "image inputs are not supported on the openai-compat engine; "
                    "use the ollama provider for vision calls"
                )
            clean_messages.append({"role": message["role"], "content": message["content"]})

        payload: Dict[str, Any] = {"model": model, "messages": clean_messages, "stream": stream}
        if "temperature" in options:
            payload["temperature"] = options["temperature"]
        if "top_p" in options:
            payload["top_p"] = options["top_p"]
        return payload

    def chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> Union[Dict[str, Any], Iterator[Dict[str, Any]]]:
        options = options or {}
        self._warn_if_ollama_v1(options)
        payload = self._build_payload(model, messages, options, stream)
        url = f"{self.base_url}/chat/completions"

        if stream:
            return self._stream(url, payload)

        response = requests.post(url, json=payload, headers=self._headers(), timeout=self.timeout)
        if response.status_code != 200:
            raise EngineError(f"{url} returned {response.status_code}: {response.text[:500]}")
        body = response.json()
        content = body["choices"][0]["message"].get("content") or ""
        return {"message": {"content": content}}

    def _stream(self, url: str, payload: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        with requests.post(
            url, json=payload, headers=self._headers(), timeout=self.timeout, stream=True
        ) as response:
            if response.status_code != 200:
                raise EngineError(f"{url} returned {response.status_code}: {response.text[:500]}")
            for raw_line in response.iter_lines():
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8", errors="replace")
                if not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                token = delta.get("content")
                if token:
                    yield {"message": {"content": token}}


def build_engine(config: Dict[str, Any]):
    """Build the configured engine. Falls back to the legacy ollama section."""
    twin_config = config.get("twin_config", {})
    engine_cfg = twin_config.get("engine", {})
    ollama_cfg = twin_config.get("ollama", {})

    provider = engine_cfg.get("provider", "ollama")
    timeout = engine_cfg.get("timeout") or ollama_cfg.get("timeout", 120)

    if provider == "openai-compat":
        base_url = engine_cfg.get("base_url")
        if not base_url:
            raise EngineError("engine.provider is openai-compat but engine.base_url is not set")
        return OpenAICompatEngine(
            base_url=base_url,
            api_key=engine_cfg.get("api_key", ""),
            timeout=timeout,
        )

    base_url = engine_cfg.get("base_url") or ollama_cfg.get("base_url", "http://localhost:11434")
    return OllamaEngine(base_url=base_url, timeout=timeout)
