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
