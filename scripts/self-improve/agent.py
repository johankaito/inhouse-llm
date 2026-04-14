#!/usr/bin/env python3
"""
Self-improvement agent for johankaito/inhouse-llm (twin).

Multi-dimensional daily audit across six dimensions:
  1. Code quality    — bugs, anti-patterns, type hints, dead code
  2. Prompt quality  — system prompts in session.py, domain prompts, 5 Whys copy
  3. Backlog pick    — implement ONE pending item from IMPROVEMENTS.md
  4. Test coverage   — identify gaps, generate missing unit tests
  5. Documentation   — docs/*.md drift vs actual implementation
  6. Safety/reliability — tool edge cases, missing input validation

Changes are categorised:
  auto_apply   — safe edits (docs, type hints, docstrings, domain prompts, new tests)
  propose_only — logic/feature changes; included in PR diff for human review
  new_files    — new test or doc files to create

Exit codes:
  0 — at least one change applied/proposed; GH Actions creates a PR
  2 — nothing to improve; GH Actions skips PR
"""

import ast
import json
import os
import sys
import textwrap
from pathlib import Path

import anthropic

REPO_ROOT = Path(__file__).resolve().parents[2]
TWIN_DIR = REPO_ROOT / "twin"

MAX_FILE_CHARS = 10_000   # truncate large source files before sending
MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-6")

AUDIT_DIMENSIONS = """
You are auditing the **twin** project — a terminal-native local LLM wrapper that
replicates Claude Code's planning experience using open-source models (Ollama +
Qwen2.5-Coder). The goal is to improve twin autonomously, every day.

Audit across these six dimensions. For every finding, apply a 5 Whys to confirm
it is a genuine improvement before proposing it.

---

## Dimension 1 — Code quality
Look for:
- Bugs, edge cases not handled (empty input, missing keys, None propagation)
- Dead code, unreachable branches, unused imports
- Missing type annotations on public functions
- Anti-patterns: bare `except`, mutable default args, open() without context manager
- Inconsistencies between similar code paths (e.g., JSON parsing in one place uses
  try/except, another doesn't)

## Dimension 2 — Prompt quality
Look for:
- `_get_domain_prompt()` in session.py: only a handful of agents have domain prompts.
  Any agent that lacks a domain prompt gets generic outputs. Add concrete, specific
  domain prompts for missing agents (decision-framework, wealth-planner, travel-agent
  already have sparse or no prompts — add them).
- The 5 Whys block in `_build_system_prompt()`: is it clearly worded? Does it
  actually enforce the protocol or just describe it?
- Tool calling instructions: are the examples accurate? Any outdated format?

## Dimension 3 — Backlog pick (HIGHEST PRIORITY)
Read IMPROVEMENTS.md carefully. Pick the **single highest-impact pending item**
and implement it as a propose_only change (the human will review before merging).
Justify the pick with 5 Whys. If the item is too large for a single PR, scope
it down to the smallest shippable slice.

Current pending items (from IMPROVEMENTS.md — verify against actual file content):
- Citation-style answers (file/line anchors)
- Tests for reload hot-swap, env snapshot, tool intent mapping
- Expand intent tools to code navigation (find symbols/paths automatically)
- Safety/harmlessness rails
- Sandboxed tool safety (timeouts, partial outputs)

## Dimension 4 — Test coverage
Identify Python modules in twin/lib/ that have zero or minimal test coverage.
Write concrete unit tests that:
- Mock Ollama calls (use unittest.mock.patch)
- Test specific functions in isolation
- Cover at least one happy path + one error path per function
Prefer new_files over modifying existing tests.

## Dimension 5 — Documentation drift
Compare docs/*.md and QUICKREF.md / TESTING.md / IMPROVEMENTS.md against
the actual implementation. Flag:
- Commands/flags documented that no longer exist or changed signature
- Features implemented but not documented
- Stale status markers (e.g., "Phase 2 in progress" when it's complete)

## Dimension 6 — Safety and reliability
Look for:
- Tools in tools.py that don't bound their output (could return 10MB of data)
- Missing timeouts on subprocess calls
- Shell injection risks (user input passed to bash/glob without sanitisation)
- Missing error propagation (tool silently returns empty on failure)
"""


def read_file(path: Path, max_chars: int = MAX_FILE_CHARS) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n[... truncated at {max_chars} chars ...]"
        return text
    except Exception as e:
        return f"[could not read: {e}]"


def collect_context() -> dict[str, str]:
    """Collect all relevant source files into a labelled dict."""
    files: dict[str, str] = {}

    # Core source
    lib_dir = TWIN_DIR / "lib"
    if lib_dir.exists():
        for py_file in sorted(lib_dir.glob("*.py")):
            # session.py and tools.py are large — give them more budget
            budget = 15_000 if py_file.stem in ("session", "tools") else MAX_FILE_CHARS
            files[f"twin/lib/{py_file.name}"] = read_file(py_file, budget)

    bin_file = TWIN_DIR / "bin" / "twin"
    if bin_file.exists():
        files["twin/bin/twin"] = read_file(bin_file)

    # Config
    config_file = TWIN_DIR / "twin.config.json"
    if config_file.exists():
        files["twin/twin.config.json"] = read_file(config_file, 3_000)

    # Improvement backlog
    improvements = TWIN_DIR / "IMPROVEMENTS.md"
    if improvements.exists():
        files["twin/IMPROVEMENTS.md"] = read_file(improvements, 8_000)

    # Docs (summarised)
    for doc in ["QUICKREF.md", "TESTING.md"]:
        p = TWIN_DIR / doc
        if p.exists():
            files[f"twin/{doc}"] = read_file(p, 4_000)

    docs_dir = REPO_ROOT / "docs"
    if docs_dir.exists():
        for md in sorted(docs_dir.glob("*.md"))[:6]:  # cap at 6 doc files
            files[f"docs/{md.name}"] = read_file(md, 3_000)

    # Existing tests (names only + first 40 lines, to avoid flooding context)
    for test_file in sorted(TWIN_DIR.glob("test_*.py")):
        files[f"twin/{test_file.name}"] = read_file(test_file, 2_500)

    # Requirements
    req = TWIN_DIR / "requirements.txt"
    if req.exists():
        files["twin/requirements.txt"] = read_file(req, 1_000)

    # CLAUDE.md
    claude_md = REPO_ROOT / "CLAUDE.md"
    if claude_md.exists():
        files["CLAUDE.md"] = read_file(claude_md, 3_000)

    return files


def build_prompt(context: dict[str, str]) -> str:
    sections = []
    for label, content in context.items():
        sections.append(f"### {label}\n```\n{content}\n```")
    files_block = "\n\n".join(sections)

    output_schema = textwrap.dedent("""
        Return a single JSON object — no markdown wrapper, no extra text:

        {
          "summary": "2-4 sentences covering what you found across all six dimensions",
          "changes_found": true,

          "auto_apply": [
            {
              "file": "twin/lib/session.py",
              "description": "one-line description",
              "dimension": "prompt_quality",
              "five_whys": "Why 1: ...\\nWhy 2: ...\\n...",
              "confidence": 0.95,
              "old_text": "exact text to replace (must be unique in the file)",
              "new_text": "replacement text"
            }
          ],

          "propose_only": [
            {
              "file": "twin/lib/tools.py",
              "description": "one-line description",
              "dimension": "backlog_pick",
              "five_whys": "Why 1: ...\\n...",
              "confidence": 0.88,
              "proposed_diff": "unified diff or before/after block — used in PR description only"
            }
          ],

          "new_files": [
            {
              "path": "twin/test_config_edge_cases.py",
              "description": "unit tests for config.py edge cases",
              "dimension": "test_coverage",
              "content": "#!/usr/bin/env python3\\n..."
            }
          ],

          "improvements_md_entry": "## <date> - <title>\\n- <what changed>\\n- Files changed: ...\\n- Commit: (pending)\\n",

          "observations": [
            "notable finding that doesn't need a code change"
          ]
        }

        Quality bar:
        - auto_apply: only changes you are >90% confident improve correctness/quality
          WITHOUT changing observable behaviour. Safe categories: docs, domain prompts,
          type annotations, docstrings, new standalone test files.
        - propose_only: logic changes, new features, architectural changes — anything
          that could break behaviour. Exactly ONE backlog item per run.
        - Skip pure cosmetic/style changes.
        - old_text must be unique in the file (not a common string like "return None").
        - new_text must be valid Python if the file is Python.
        - If nothing genuine found: set changes_found: false, empty arrays.
    """).strip()

    return textwrap.dedent(f"""
        {AUDIT_DIMENSIONS}

        ---

        ## Output format

        {output_schema}

        ---

        ## Source files

        {files_block}
    """).strip()


def validate_python(path: Path, content: str) -> tuple[bool, str]:
    """Check that content is valid Python. Returns (ok, error_msg)."""
    try:
        ast.parse(content)
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError at line {e.lineno}: {e.msg}"


def apply_auto_changes(changes: list[dict]) -> list[dict]:
    """Apply auto_apply changes to disk. Returns applied list."""
    applied = []
    for change in changes:
        if change.get("confidence", 0) < 0.90:
            print(f"  SKIP (confidence {change['confidence']:.0%} < 90%): {change['description']}", file=sys.stderr)
            continue

        rel_path = change["file"]
        target = REPO_ROOT / rel_path
        if not target.exists():
            print(f"  SKIP (file not found): {rel_path}", file=sys.stderr)
            continue

        content = target.read_text(encoding="utf-8")
        old = change["old_text"]
        new = change["new_text"]

        if old not in content:
            print(f"  SKIP (old_text not found): {rel_path} — {old[:60]!r}", file=sys.stderr)
            continue
        if content.count(old) > 1:
            print(f"  SKIP (old_text not unique): {rel_path} — {old[:60]!r}", file=sys.stderr)
            continue

        new_content = content.replace(old, new, 1)

        # Syntax-check Python files before writing
        if target.suffix == ".py":
            ok, err = validate_python(target, new_content)
            if not ok:
                print(f"  SKIP (syntax error after edit): {rel_path} — {err}", file=sys.stderr)
                continue

        target.write_text(new_content, encoding="utf-8")
        print(f"  APPLIED [{change['dimension']}]: {rel_path} — {change['description']}", file=sys.stderr)
        applied.append(change)

    return applied


def write_new_files(new_files: list[dict]) -> list[dict]:
    """Write new files to disk. Returns list of written files."""
    written = []
    for nf in new_files:
        target = REPO_ROOT / nf["path"]
        if target.exists():
            print(f"  SKIP (file already exists): {nf['path']}", file=sys.stderr)
            continue

        content = nf["content"]

        # Syntax-check new Python files
        if target.suffix == ".py":
            ok, err = validate_python(target, content)
            if not ok:
                print(f"  SKIP (new file has syntax error): {nf['path']} — {err}", file=sys.stderr)
                continue

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print(f"  CREATED [{nf['dimension']}]: {nf['path']} — {nf['description']}", file=sys.stderr)
        written.append(nf)

    return written


def append_improvements_log(entry: str):
    """Append a new entry to IMPROVEMENTS.md above the Pending table."""
    log_path = TWIN_DIR / "IMPROVEMENTS.md"
    if not log_path.exists() or not entry.strip():
        return
    content = log_path.read_text(encoding="utf-8")
    # Insert after the last --- separator before Pending table
    marker = "## Pending / Proposed Improvements"
    if marker in content:
        idx = content.index(marker)
        content = content[:idx] + entry.strip() + "\n\n" + content[idx:]
    else:
        content = content + "\n\n" + entry.strip() + "\n"
    log_path.write_text(content, encoding="utf-8")
    print("  UPDATED: twin/IMPROVEMENTS.md", file=sys.stderr)


def write_pr_body(result: dict, applied: list[dict], written: list[dict]) -> str:
    """Write detailed PR description to pr_body.md."""
    propose_only = result.get("propose_only", [])
    observations = result.get("observations", [])

    lines = [
        "## Summary",
        "",
        result.get("summary", ""),
        "",
        f"**Auto-applied**: {len(applied)} changes | "
        f"**New files**: {len(written)} | "
        f"**Proposed for review**: {len(propose_only)}",
        "",
    ]

    if applied:
        lines += ["## Auto-applied Changes", ""]
        for i, c in enumerate(applied, 1):
            lines += [
                f"### {i}. [{c['dimension']}] {c['description']}",
                "",
                f"**File**: `{c['file']}` | **Confidence**: {c.get('confidence', 0):.0%}",
                "",
                f"**5 Whys**:",
                "```",
                c.get("five_whys", ""),
                "```",
                "",
                "<details><summary>Diff</summary>",
                "",
                "**Before:**",
                "```python",
                c["old_text"][:600],
                "```",
                "**After:**",
                "```python",
                c["new_text"][:600],
                "```",
                "</details>",
                "",
            ]

    if written:
        lines += ["## New Files Created", ""]
        for nf in written:
            lines += [f"- `{nf['path']}` — {nf['description']}"]
        lines.append("")

    if propose_only:
        lines += [
            "## Proposed Changes (review required — NOT auto-applied)",
            "",
            "> These are logic/feature changes. Review carefully before cherry-picking.",
            "",
        ]
        for i, c in enumerate(propose_only, 1):
            lines += [
                f"### {i}. [{c['dimension']}] {c['description']}",
                "",
                f"**File**: `{c['file']}` | **Confidence**: {c.get('confidence', 0):.0%}",
                "",
                f"**5 Whys**: {c.get('five_whys', '')}",
                "",
                "**Proposed diff:**",
                "```diff",
                c.get("proposed_diff", "")[:1_000],
                "```",
                "",
            ]

    if observations:
        lines += ["## Observations (no code change needed)", ""]
        for obs in observations:
            lines += [f"- {obs}"]
        lines.append("")

    lines += [
        "---",
        "*Review auto-applied changes carefully. Proposed changes require manual implementation.*",
        "*Generated by the daily self-improve workflow.*",
    ]

    body = "\n".join(lines)
    (REPO_ROOT / "pr_body.md").write_text(body, encoding="utf-8")
    return body


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    print("Collecting source files...", file=sys.stderr)
    context = collect_context()
    print(f"  {len(context)} files ({sum(len(v) for v in context.values()):,} chars total)", file=sys.stderr)

    print(f"Calling Claude API ({MODEL})...", file=sys.stderr)
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        system=(
            "You are a senior Python engineer performing a rigorous daily audit of "
            "an open-source project. Be surgical, specific, and confident. Never "
            "propose vague improvements — every change must be concrete and safe to apply."
        ),
        messages=[{"role": "user", "content": build_prompt(context)}],
    )

    raw = message.content[0].text.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        if "```" in raw:
            raw = raw[: raw.rfind("```")]

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: Could not parse API response as JSON: {e}", file=sys.stderr)
        print(f"Raw (first 1000 chars):\n{raw[:1000]}", file=sys.stderr)
        sys.exit(1)

    if not result.get("changes_found"):
        print("No changes proposed — project looks solid.", file=sys.stderr)
        write_pr_body(result, [], [])
        sys.exit(2)

    # Apply auto_apply changes
    auto_changes = result.get("auto_apply", [])
    print(f"Applying {len(auto_changes)} auto_apply change(s)...", file=sys.stderr)
    applied = apply_auto_changes(auto_changes)

    # Write new files
    new_files = result.get("new_files", [])
    print(f"Writing {len(new_files)} new file(s)...", file=sys.stderr)
    written = write_new_files(new_files)

    # Update IMPROVEMENTS.md
    entry = result.get("improvements_md_entry", "")
    if entry:
        append_improvements_log(entry)

    # Check if anything actually changed on disk
    has_disk_changes = bool(applied or written or entry)

    if not has_disk_changes and not result.get("propose_only"):
        print("All changes were skipped — nothing written.", file=sys.stderr)
        write_pr_body(result, [], [])
        sys.exit(2)

    print("Writing PR body...", file=sys.stderr)
    write_pr_body(result, applied, written)
    print(
        f"Done — {len(applied)} applied, {len(written)} new files, "
        f"{len(result.get('propose_only', []))} proposed for review.",
        file=sys.stderr,
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
