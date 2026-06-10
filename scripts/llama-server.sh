#!/usr/bin/env bash
# Launch llama-server per the local-first foundation (docs/architecture/local-first-foundation.md §2).
# Serves a GGUF straight from Ollama's blob store — no duplicate model storage.
#
# Usage:
#   scripts/llama-server.sh [ollama-model-tag] [port]
#   scripts/llama-server.sh qwen3-coder:latest 8080

set -euo pipefail

MODEL_TAG="${1:-qwen3-coder:latest}"
PORT="${2:-8080}"
CTX_SIZE="${LLAMA_CTX_SIZE:-32768}"

BLOB=$(ollama show --modelfile "$MODEL_TAG" 2>/dev/null | awk '/^FROM \//{print $2; exit}')
if [ -z "$BLOB" ] || [ ! -f "$BLOB" ]; then
  echo "error: could not resolve GGUF blob for '$MODEL_TAG' (is it pulled in Ollama?)" >&2
  exit 1
fi

echo "model:    $MODEL_TAG"
echo "blob:     $BLOB"
echo "endpoint: http://127.0.0.1:${PORT}/v1 (OpenAI) + /v1/messages (Anthropic)"
echo "ctx:      $CTX_SIZE  kv: q8_0 (foundation floor — do not go below)"

exec llama-server \
  -m "$BLOB" \
  --jinja \
  --ctx-size "$CTX_SIZE" \
  --cache-type-k q8_0 \
  --cache-type-v q8_0 \
  --host 127.0.0.1 \
  --port "$PORT"
