# In-House LLM Project

## What This Is

Self-hosted, terminal-native LLM setup equivalent to Claude Code using open source models. Hybrid architecture: portable MacBook + powerful home server.

## Architecture

```
MacBook M1 Max (32GB) — portable
├── Ollama (local model serving)
├── Aider (automated file editing)
└── Qwen2.5 Coder 7B-14B models

Home Server — powerful inference
├── Higher-param models
└── RAG knowledge bases
```

- `twin/` — Claude Code equivalent with tools (Phase 2, complete)
- `jina-rapid/` — RAG/embedding experiments

## Status

Phase 2 complete: `twin` with tool-use working and git-tracked.

## Rules

- **NEVER include Claude references in commits**
- Package manager: use whatever is appropriate per component (Python/pip, Node/npm)
- Models and large binary files are never committed
