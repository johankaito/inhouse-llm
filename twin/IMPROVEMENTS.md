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

## 2026-01-03 - Safety audit: bare except fix, output truncation proposal, doc drift fix, test coverage for config/modes
- Fixed bare `except` in modes.py → specific exception types
- Fixed stale model alias table in QUICKREF.md (fast/balanced/quality mismatch with twin.config.json)
- Proposed output truncation for bash/glob/grep tools (sandboxed tool safety backlog item)
- Added unit tests for config.py and modes.py (zero prior coverage)
- Files changed: twin/lib/modes.py, twin/QUICKREF.md, twin/tests/test_config.py (new), twin/tests/test_modes.py (new)
- Commit: (pending)

## 2025-01-28 - Safety: Sensitive-path guardrails for file-writing tools

**What:** Added path confinement and sensitive-path blocklists to _write_file, _edit_file, _apply_patch, and self_improver.propose_improvement. Blocks writes outside cwd, to ~/.ssh, /etc, and known credential files.

**Why (5 Whys):**
1. File-writing tools accept arbitrary paths with no validation
2. A single hallucinated or injected tool call can overwrite system/credential files
3. Self-improvement writes files autonomously without human confirmation
4. Path allowlists are the right granularity for a CLI tool (vs full sandboxing)
5. Safety rails reduce blast radius of all other bugs — defense-in-depth

**Also fixed:**
- Dict indentation in _reload_modules state snapshot
- Stale `self` references in main loop (should be `current` after hot-swap)
- Added test_path_safety.py for guardrail verification

- Files: lib/tools.py, lib/self_improver.py, lib/session.py, tests/test_path_safety.py
- Commit: (pending)

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
