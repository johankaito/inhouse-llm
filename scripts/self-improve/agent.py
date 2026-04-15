#!/usr/bin/env python3
"""
Self-improvement agent for johankaito/inhouse-llm (twin).

Two-pass architecture with prompt caching:
  Pass 1 — AST-extracted signatures for all files → identifies which files
            need deep review and what to look for. Cheap + fast.
  Pass 2 — Full untruncated content of flagged files (prompt-cached) →
            concrete changes. Deep + complete.

Improvements over v1:
  - session.py (84k chars) and tools.py (53k chars) are no longer truncated
  - Deduplication via self-improve-proposed.jsonl (14-day window)
  - pending-improvements.md tracks propose_only items across runs
    (items >3 days old become mandatory focus for next run)
  - PR outcome learnings via self-improve-outcomes.md
  - max_tokens raised to 16384

Exit codes:
  0 — changes applied/proposed
  2 — nothing to do
"""

import ast as ast_module
import hashlib
import json
import os
import sys
import textwrap
from datetime import datetime, timedelta
from pathlib import Path

import anthropic

REPO_ROOT = Path(__file__).resolve().parents[2]
TWIN_DIR = REPO_ROOT / "twin"

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-6")
DEDUP_LOG = TWIN_DIR / "self-improve-proposed.jsonl"
OUTCOMES_FILE = TWIN_DIR / "self-improve-outcomes.md"
PENDING_FILE = TWIN_DIR / "pending-improvements.md"
DEDUP_WINDOW_DAYS = 14


# ---------------------------------------------------------------------------
# File collection
# ---------------------------------------------------------------------------

def read_file(path: Path, max_chars: int | None = None) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        if max_chars and len(text) > max_chars:
            text = text[:max_chars] + f"\n\n[... truncated at {max_chars} chars ...]"
        return text
    except Exception as e:
        return f"[could not read: {e}]"


def extract_signatures(path: Path) -> str:
    """
    Extract function/class signatures + docstrings via AST.
    Falls back to first 3000 chars if parsing fails.
    """
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast_module.parse(source)
        lines = source.splitlines()
        output = []

        for node in ast_module.walk(tree):
            if not isinstance(node, (ast_module.FunctionDef, ast_module.AsyncFunctionDef, ast_module.ClassDef)):
                continue
            # Signature line
            sig = lines[node.lineno - 1].rstrip()
            # Docstring
            doc = ast_module.get_docstring(node)
            if doc:
                short_doc = doc[:150].replace("\n", " ")
                if len(doc) > 150:
                    short_doc += "..."
                output.append(f"{sig}  # \"\"\"{short_doc}\"\"\"")
            else:
                output.append(sig)

        return "\n".join(output) if output else source[:3_000]
    except Exception:
        return read_file(path, 3_000)


def collect_signatures() -> dict[str, str]:
    """Pass 1: lightweight signature-only view of all source files."""
    files: dict[str, str] = {}

    lib_dir = TWIN_DIR / "lib"
    if lib_dir.exists():
        for py_file in sorted(lib_dir.glob("*.py")):
            files[f"twin/lib/{py_file.name} [signatures]"] = extract_signatures(py_file)

    bin_file = TWIN_DIR / "bin" / "twin"
    if bin_file.exists():
        files["twin/bin/twin [signatures]"] = extract_signatures(bin_file)

    # Non-Python supporting files (small, send in full)
    for rel, cap in [
        ("twin/twin.config.json", 3_000),
        ("twin/IMPROVEMENTS.md", 8_000),
        ("twin/QUICKREF.md", 4_000),
        ("twin/TESTING.md", 3_000),
        ("CLAUDE.md", 3_000),
    ]:
        p = REPO_ROOT / rel
        if p.exists():
            files[rel] = read_file(p, cap)

    # Test file names only (to detect coverage gaps)
    test_names = [tf.name for tf in sorted(TWIN_DIR.glob("test_*.py"))]
    # Also check twin/tests/
    tests_dir = TWIN_DIR / "tests"
    if tests_dir.exists():
        test_names += [f"tests/{tf.name}" for tf in sorted(tests_dir.glob("test_*.py"))]
    if test_names:
        files["existing-tests"] = "Existing test files:\n" + "\n".join(f"  - {n}" for n in test_names)

    return files


def collect_full_content(file_keys: list[str]) -> dict[str, str]:
    """Pass 2: full untruncated content for flagged files."""
    files: dict[str, str] = {}
    for key in file_keys:
        # Strip [signatures] suffix to get real path
        rel = key.replace(" [signatures]", "")
        path = REPO_ROOT / rel
        if path.exists():
            files[rel] = path.read_text(encoding="utf-8", errors="replace")
        else:
            files[rel] = f"[file not found: {rel}]"
    return files


# ---------------------------------------------------------------------------
# Dedup + outcomes + pending
# ---------------------------------------------------------------------------

def load_recently_proposed() -> list[dict]:
    if not DEDUP_LOG.exists():
        return []
    cutoff = datetime.utcnow() - timedelta(days=DEDUP_WINDOW_DAYS)
    recent = []
    for line in DEDUP_LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            if datetime.fromisoformat(entry.get("date", "2000-01-01")) >= cutoff:
                recent.append(entry)
        except (json.JSONDecodeError, ValueError):
            continue
    return recent


def load_outcomes() -> str:
    return read_file(OUTCOMES_FILE, 3_000) if OUTCOMES_FILE.exists() else ""


def load_pending_improvements() -> list[dict]:
    """Read pending-improvements.md and return items with age in days."""
    if not PENDING_FILE.exists():
        return []
    items = []
    current: dict | None = None
    today = datetime.utcnow().date()
    for line in PENDING_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            if current:
                items.append(current)
            parts = line[3:].split(" | ")
            if len(parts) >= 3:
                try:
                    proposed_date = datetime.fromisoformat(parts[0].strip()).date()
                    age = (today - proposed_date).days
                except ValueError:
                    age = 0
                current = {
                    "date": parts[0].strip(),
                    "slug": parts[1].strip() if len(parts) > 1 else "",
                    "status": parts[2].strip() if len(parts) > 2 else "pending",
                    "age_days": age,
                    "lines": [line],
                }
            else:
                current = None
        elif current is not None:
            current["lines"].append(line)
    if current:
        items.append(current)
    return [i for i in items if i.get("status") == "pending"]


def write_dedup_log(all_proposals: list[dict]):
    date_str = datetime.utcnow().date().isoformat()
    with DEDUP_LOG.open("a", encoding="utf-8") as f:
        for c in all_proposals:
            old = c.get("old_text", c.get("proposed_diff", ""))
            entry = {
                "date": date_str,
                "file": c.get("file", ""),
                "hash": hashlib.sha256(old.encode()).hexdigest()[:8],
                "preview": old[:80].replace("\n", "↵"),
                "description": c.get("description", ""),
            }
            f.write(json.dumps(entry) + "\n")


def update_pending_improvements(propose_only: list[dict], applied_descriptions: list[str]):
    """
    - Mark implemented items as done.
    - Append new propose_only items.
    """
    today = datetime.utcnow().date().isoformat()
    existing = PENDING_FILE.read_text(encoding="utf-8") if PENDING_FILE.exists() else (
        "# Pending Improvements\n\n<!-- AUTO-MANAGED: do not edit manually -->\n\n"
    )

    # Mark implemented items as done
    for desc in applied_descriptions:
        existing = existing.replace("| pending", "| done", 1) if desc[:30] in existing else existing

    # Append new propose_only items
    new_entries = []
    for item in propose_only:
        slug = item.get("description", "")[:40].lower().replace(" ", "-").replace("/", "-")
        entry = (
            f"## {today} | {slug} | pending\n"
            f"**File**: `{item.get('file', '?')}`\n"
            f"**Description**: {item.get('description', '')}\n"
            f"**5 Whys**: {item.get('five_whys', '')[:300]}\n"
            f"**Proposed diff**:\n```diff\n{item.get('proposed_diff', '')[:600]}\n```\n"
        )
        new_entries.append(entry)

    if new_entries:
        existing = existing.rstrip() + "\n\n" + "\n\n".join(new_entries) + "\n"

    PENDING_FILE.write_text(existing, encoding="utf-8")


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

PASS1_SCHEMA = textwrap.dedent("""
    Return JSON only — no markdown wrapper:

    {
      "files_needing_deep_review": [
        "twin/lib/session.py [signatures]",
        "twin/lib/tools.py [signatures]"
      ],
      "focus_per_file": {
        "twin/lib/session.py [signatures]": "bare except near _build_system_prompt, domain prompts only for 3 agents",
        "twin/lib/tools.py [signatures]": "subprocess calls without timeout, no output size bound"
      },
      "preliminary_findings": "2-3 sentence summary of patterns spotted from signatures",
      "backlog_pick": {
        "item": "name of the IMPROVEMENTS.md item to implement this run",
        "rationale": "why this item, 5 Whys compressed"
      }
    }
""").strip()

PASS2_SCHEMA = textwrap.dedent("""
    Return JSON only — no markdown wrapper:

    {
      "summary": "2-4 sentences across all six dimensions",
      "changes_found": true,

      "auto_apply": [
        {
          "file": "twin/lib/session.py",
          "description": "one-line description",
          "dimension": "code_quality | prompt_quality | test_coverage | documentation_drift | safety",
          "five_whys": "Why 1: ...\\nWhy 2: ...\\n...",
          "confidence": 0.95,
          "old_text": "shortest unique string (1-2 lines, no surrounding context, no trailing spaces)",
          "new_text": "replacement text"
        }
      ],

      "propose_only": [
        {
          "file": "twin/lib/session.py",
          "description": "one-line description",
          "dimension": "backlog_pick",
          "five_whys": "...",
          "confidence": 0.88,
          "proposed_diff": "unified diff or before/after block"
        }
      ],

      "new_files": [
        {
          "path": "twin/tests/test_config_edge_cases.py",
          "description": "...",
          "dimension": "test_coverage",
          "content": "#!/usr/bin/env python3\\n..."
        }
      ],

      "improvements_md_entry": "## <date> - <title>\\n- <what>\\n- Files: ...\\n- Commit: (pending)\\n",

      "observations": ["notable finding, no code change needed"]
    }

    Quality bar:
    - auto_apply only if >90% confident AND safe (no logic changes)
    - propose_only for logic/feature changes — one backlog item per run
    - old_text must be the SHORTEST unique string that locates the change (1-2 lines max)
    - Never include surrounding context lines in old_text — only the lines that change
    - old_text is matched with Python str.replace() — must be exact, no trailing spaces/tabs
    - new_text must be valid Python if file is Python
    - If nothing genuine found, set changes_found: false
""").strip()


def build_pass1_prompt(
    signatures: dict[str, str],
    recently_proposed: list[dict],
    pending: list[dict],
    outcomes: str,
) -> str:
    sections = [f"### {k}\n```\n{v}\n```" for k, v in signatures.items()]
    files_block = "\n\n".join(sections)

    dedup_block = ""
    if recently_proposed:
        lines = [f"  - [{e['date']}] {e['file']}: {e['preview']}" for e in recently_proposed[-20:]]
        dedup_block = "\n**Do NOT re-propose these (proposed in last 14 days):**\n" + "\n".join(lines) + "\n"

    mandatory_block = ""
    overdue = [p for p in pending if p.get("age_days", 0) >= 3]
    if overdue:
        items = [f"  - {p['slug']} (pending {p['age_days']} days)" for p in overdue]
        mandatory_block = (
            "\n**MANDATORY: These pending improvements are overdue (>3 days). "
            "One of them MUST be the backlog_pick this run:**\n" + "\n".join(items) + "\n"
        )

    outcomes_block = f"\n**Prior PR outcomes:**\n```\n{outcomes}\n```\n" if outcomes else ""

    return textwrap.dedent(f"""
        You are doing a preliminary audit of the **twin** local-LLM project.

        Below are function signatures and docstrings for all source files (NOT full content).
        Your task: identify which files need deep review and what specific issues to target.

        Six audit dimensions:
          1. code_quality — bugs, bare except, missing type hints, dead code
          2. prompt_quality — domain prompts incomplete, 5-Whys copy, tool instructions
          3. test_coverage — untested modules or critical functions
          4. documentation_drift — QUICKREF/TESTING vs implementation
          5. safety — missing subprocess timeouts, unbounded output, shell injection
          6. backlog_pick — ONE pending IMPROVEMENTS.md item to implement
        {dedup_block}{mandatory_block}{outcomes_block}
        ## Output format

        {PASS1_SCHEMA}

        ## Source files (signatures only)

        {files_block}
    """).strip()


def build_pass2_prompt(
    full_files: dict[str, str],
    pass1: dict,
    recently_proposed: list[dict],
) -> list[dict]:
    """Returns the messages list for Pass 2, with cache_control on the heavy content block."""
    sections = [f"### {k}\n```\n{v}\n```" for k, v in full_files.items()]
    files_block = "\n\n".join(sections)

    dedup_note = ""
    if recently_proposed:
        lines = [f"  - [{e['date']}] {e['file']}: {e['preview']}" for e in recently_proposed[-20:]]
        dedup_note = "\n**Skip these (proposed in last 14 days):**\n" + "\n".join(lines) + "\n"

    focus = json.dumps(pass1.get("focus_per_file", {}), indent=2)
    backlog = json.dumps(pass1.get("backlog_pick", {}), indent=2)
    preliminary = pass1.get("preliminary_findings", "")

    system_note = textwrap.dedent(f"""
        You are doing a deep audit of the **twin** local-LLM project.

        ## Preliminary findings (from Pass 1 signature analysis)
        {preliminary}

        ## Files flagged for deep review + focus areas
        ```json
        {focus}
        ```

        ## Backlog item to implement this run
        ```json
        {backlog}
        ```
        {dedup_note}
        ## Output format

        {PASS2_SCHEMA}

        ## Full source files (untruncated)

    """).strip()

    return [
        {
            "role": "user",
            "content": [
                # Large files block — eligible for prompt caching
                {
                    "type": "text",
                    "text": files_block,
                    "cache_control": {"type": "ephemeral"},
                },
                {
                    "type": "text",
                    "text": system_note,
                },
            ],
        }
    ]


# ---------------------------------------------------------------------------
# Apply changes
# ---------------------------------------------------------------------------

def validate_python(path: Path, content: str) -> tuple[bool, str]:
    try:
        ast_module.parse(content)
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError at line {e.lineno}: {e.msg}"


def _rstrip_lines(s: str) -> str:
    """Strip trailing whitespace from each line (catches editor/LLM trailing-space mismatches)."""
    return "\n".join(line.rstrip() for line in s.split("\n"))


def apply_auto_changes(changes: list[dict]) -> list[dict]:
    applied = []
    for change in changes:
        if change.get("confidence", 0) < 0.90:
            print(f"  SKIP (confidence {change['confidence']:.0%} < 90%): {change['description']}", file=sys.stderr)
            continue
        rel_path = change["file"]
        target = REPO_ROOT / rel_path
        if not target.exists():
            print(f"  SKIP (not found): {rel_path}", file=sys.stderr)
            continue
        content = target.read_text(encoding="utf-8")
        old, new = change["old_text"], change["new_text"]

        # 1. Exact match
        if old in content and content.count(old) == 1:
            new_content = content.replace(old, new, 1)
        elif old in content:
            print(f"  SKIP (not unique): {rel_path} — {old[:60]!r}", file=sys.stderr)
            continue
        else:
            # 2. Fallback: rstrip each line (catches trailing whitespace mismatches)
            content_norm = _rstrip_lines(content)
            old_norm = _rstrip_lines(old)
            new_norm = _rstrip_lines(new)
            if old_norm in content_norm and content_norm.count(old_norm) == 1:
                new_content = content_norm.replace(old_norm, new_norm, 1)
                print(f"  (normalized match)", file=sys.stderr)
            else:
                print(f"  SKIP (old_text not found): {rel_path} — {old[:60]!r}", file=sys.stderr)
                continue

        if target.suffix == ".py":
            ok, err = validate_python(target, new_content)
            if not ok:
                print(f"  SKIP (syntax error): {rel_path} — {err}", file=sys.stderr)
                continue
        target.write_text(new_content, encoding="utf-8")
        print(f"  APPLIED [{change['dimension']}]: {rel_path} — {change['description']}", file=sys.stderr)
        applied.append(change)
    return applied


def write_new_files(new_files: list[dict]) -> list[dict]:
    written = []
    for nf in new_files:
        target = REPO_ROOT / nf["path"]
        if target.exists():
            print(f"  SKIP (exists): {nf['path']}", file=sys.stderr)
            continue
        content = nf["content"]
        if target.suffix == ".py":
            ok, err = validate_python(target, content)
            if not ok:
                print(f"  SKIP (syntax error in new file): {nf['path']} — {err}", file=sys.stderr)
                continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print(f"  CREATED [{nf['dimension']}]: {nf['path']} — {nf['description']}", file=sys.stderr)
        written.append(nf)
    return written


def append_improvements_log(entry: str):
    if not entry.strip():
        return
    log_path = TWIN_DIR / "IMPROVEMENTS.md"
    if not log_path.exists():
        return
    content = log_path.read_text(encoding="utf-8")
    marker = "## Pending / Proposed Improvements"
    if marker in content:
        idx = content.index(marker)
        content = content[:idx] + entry.strip() + "\n\n" + content[idx:]
    else:
        content += "\n\n" + entry.strip() + "\n"
    log_path.write_text(content, encoding="utf-8")
    print("  UPDATED: twin/IMPROVEMENTS.md", file=sys.stderr)


def write_pr_body(result: dict, applied: list[dict], written: list[dict]) -> str:
    propose_only = result.get("propose_only", [])
    lines = [
        "## Summary",
        "",
        result.get("summary", ""),
        "",
        f"**Auto-applied**: {len(applied)} | **New files**: {len(written)} | **Proposed for review**: {len(propose_only)}",
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
                "<details><summary>5 Whys + Diff</summary>",
                "",
                f"**5 Whys**: {c.get('five_whys', '')}",
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
        lines += ["## New Files", ""]
        for nf in written:
            lines += [f"- `{nf['path']}` — {nf['description']}"]
        lines.append("")

    if propose_only:
        lines += [
            "## Proposed Changes (review required — NOT auto-applied)",
            "",
            "> Logic/feature changes. Review carefully. Items tracked in `twin/pending-improvements.md`.",
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
                "```diff",
                c.get("proposed_diff", "")[:1_000],
                "```",
                "",
            ]

    if result.get("observations"):
        lines += ["## Observations", ""]
        for obs in result["observations"]:
            lines += [f"- {obs}"]
        lines.append("")

    lines += [
        "---",
        "*Generated by the daily self-improve workflow (two-pass + prompt caching).*",
    ]

    body = "\n".join(lines)
    (REPO_ROOT / "pr_body.md").write_text(body, encoding="utf-8")
    return body


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        if "```" in raw:
            raw = raw[: raw.rfind("```")]
    raw = raw.strip()
    result, _ = json.JSONDecoder().raw_decode(raw)
    return result


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    recently_proposed = load_recently_proposed()
    pending = load_pending_improvements()
    outcomes = load_outcomes()

    if recently_proposed:
        print(f"Dedup: {len(recently_proposed)} recently proposed changes loaded", file=sys.stderr)
    if pending:
        overdue = [p for p in pending if p.get("age_days", 0) >= 3]
        print(f"Pending: {len(pending)} items ({len(overdue)} overdue)", file=sys.stderr)

    # ── Pass 1: signatures ──────────────────────────────────────────────────
    print("Pass 1: collecting signatures...", file=sys.stderr)
    signatures = collect_signatures()
    sig_chars = sum(len(v) for v in signatures.values())
    print(f"  {len(signatures)} files, {sig_chars:,} chars (~{sig_chars//4:,} tokens)", file=sys.stderr)

    client = anthropic.Anthropic(api_key=api_key)

    print(f"Pass 1: calling Claude API ({MODEL})...", file=sys.stderr)
    p1_message = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=(
            "You are a senior Python engineer performing a preliminary audit. "
            "Be specific about which files need deep review and why. "
            "Return only JSON."
        ),
        messages=[
            {
                "role": "user",
                "content": build_pass1_prompt(signatures, recently_proposed, pending, outcomes),
            }
        ],
    )

    try:
        pass1 = parse_json(p1_message.content[0].text)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"ERROR: Pass 1 JSON parse failed: {e}", file=sys.stderr)
        print(p1_message.content[0].text[:500], file=sys.stderr)
        sys.exit(1)

    flagged = pass1.get("files_needing_deep_review", [])
    print(f"Pass 1 complete. Flagged {len(flagged)} files: {flagged}", file=sys.stderr)
    if pass1.get("preliminary_findings"):
        print(f"  Findings: {pass1['preliminary_findings'][:200]}", file=sys.stderr)

    if not flagged:
        print("No files flagged for deep review — nothing to improve.", file=sys.stderr)
        (REPO_ROOT / "pr_body.md").write_text("## No changes needed\n\nPass 1 found no issues.\n")
        sys.exit(2)

    # ── Pass 2: full content of flagged files ───────────────────────────────
    print("Pass 2: collecting full file content...", file=sys.stderr)
    full_files = collect_full_content(flagged)
    full_chars = sum(len(v) for v in full_files.values())
    print(f"  {len(full_files)} files, {full_chars:,} chars (~{full_chars//4:,} tokens)", file=sys.stderr)

    print(f"Pass 2: calling Claude API ({MODEL})...", file=sys.stderr)
    p2_messages = build_pass2_prompt(full_files, pass1, recently_proposed)
    p2_message = client.messages.create(
        model=MODEL,
        max_tokens=16384,
        system=(
            "You are a senior Python engineer performing a deep audit of the twin project. "
            "Be surgical, specific, and conservative. Only auto_apply changes that are "
            "clearly safe (no logic changes). Return only JSON."
        ),
        messages=p2_messages,
    )

    try:
        result = parse_json(p2_message.content[0].text)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"ERROR: Pass 2 JSON parse failed: {e}", file=sys.stderr)
        print(p2_message.content[0].text[:500], file=sys.stderr)
        sys.exit(1)

    if not result.get("changes_found"):
        print("No changes proposed after deep review.", file=sys.stderr)
        write_pr_body(result, [], [])
        sys.exit(2)

    # Write ALL proposals to dedup log
    all_proposals = result.get("auto_apply", []) + result.get("propose_only", [])
    if all_proposals:
        write_dedup_log(all_proposals)

    # Apply auto_apply
    auto_changes = result.get("auto_apply", [])
    print(f"Applying {len(auto_changes)} auto_apply change(s)...", file=sys.stderr)
    applied = apply_auto_changes(auto_changes)

    # Write new files
    new_files = result.get("new_files", [])
    print(f"Writing {len(new_files)} new file(s)...", file=sys.stderr)
    written = write_new_files(new_files)

    # Update IMPROVEMENTS.md log
    entry = result.get("improvements_md_entry", "")
    if entry:
        append_improvements_log(entry)

    # Update pending-improvements.md
    propose_only = result.get("propose_only", [])
    applied_descs = [c["description"] for c in applied]
    if propose_only or applied_descs:
        update_pending_improvements(propose_only, applied_descs)

    has_disk_changes = bool(applied or written or entry)
    if not has_disk_changes and not propose_only:
        print("Nothing written to disk.", file=sys.stderr)
        write_pr_body(result, [], [])
        sys.exit(2)

    write_pr_body(result, applied, written)
    print(
        f"Done — {len(applied)} applied, {len(written)} new files, "
        f"{len(propose_only)} proposed for review.",
        file=sys.stderr,
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
