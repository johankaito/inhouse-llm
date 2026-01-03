# Twin Self-Improvements Log

This file tracks all autonomous improvements made by twin to itself.

Each improvement includes:
- Timestamp
- Description
- Reasoning (5 Whys analysis)
- Files changed
- Git commit hash

---

## 2026-01-02 - Non-interactive one-shot mode
- Added stdin one-shot support: when twin is run without a TTY, it now reads a prompt from stdin, answers once, prints the response, and saves the session instead of exiting.
- Files changed: twin/lib/session.py
- Commit: (see git history)

## 2026-01-02 - Auto env context injection
- When the user asks about current directory/files/project, twin auto-appends the environment snapshot (cwd, git, README summary, top files) to the prompt so the model answers with concrete context.
- Works in both interactive and one-shot modes; displays a dim note when injected.
- Files changed: twin/lib/session.py
- Commit: (see git history)

---

## Pending / Proposed Improvements (tracked for parity)

| Status   | Item                                                              | Impact (relative) |
|----------|-------------------------------------------------------------------|-------------------|
| Done     | Intent-driven tool use for env/file queries (auto pwd/ls/read) | 35%                |
| Done     | Smarter summaries (replace heuristic truncation with bulletizer/summarizer for running/context resume) | 25%                |
| Done     | Live model knobs via commands (/ctx to set num_ctx, /temp to set temperature) | 15%                |
| Done     | Non-TTY one-shot flag (-c \"prompt\") for clean single-shot without piping | 10%                |
| Done     | Repo-aware retrieval (bounded mini-RAG over repo/README/entrypoints with cited snippets) | 25%                |
| Pending  | Citation-style answers (file/line anchors where info was found) | 20%                |
| Pending  | Tests for reload hot-swap, env snapshot presence, tool intent mapping | 10%                |
| Pending  | Expand intent tools to code navigation (find symbols/paths automatically) | 10%                |
| Pending  | Safety/harmlessness rails (refusal rules, sensitive-path guardrails; inspired by Claude’s constitutional AI focus) | 15%                |
| Pending  | Sandboxed/tool safety (timeouts, partial outputs, avoid outbound network by default; similar to Codex CLI sandbox) | 10%                |

## 2026-01-02 - Bulletized summaries
- Replaced heuristic truncation with sentence-based bulletized summaries for running context and session resume, keeping outputs concise and readable.
- Files changed: twin/lib/session.py
- Commit: (see git history)

## 2026-01-02 - Live model knobs
- Added `/ctx` and `/temp` commands to set num_ctx and temperature at runtime (stored in generation_params for the session).
- Files changed: twin/lib/session.py
- Commit: (see git history)

## 2026-01-02 - CLI one-shot flag
- Added `-c/--command` flag to twin CLI to accept a one-shot prompt without piping stdin; still saves the session.
- Files changed: twin/bin/twin
- Commit: (see git history)

## 2026-01-02 - Repo-aware retrieval
- Added lightweight repo index (README, key entrypoints) with token-overlap retrieval and cited snippets auto-injected into prompts for repo/code questions.
- Files changed: twin/lib/session.py
- Commit: (see git history)
