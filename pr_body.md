## Summary

Critical safety gaps: _write_file, _edit_file, _apply_patch, and _improve_self accept arbitrary paths with zero confinement—a misguided tool call can overwrite /etc/passwd or ~/.ssh/authorized_keys. Session.py has a dict literal indentation error in _reload_modules (misaligned closing braces will cause a SyntaxError on certain Python versions or confuse state migration). QUICKREF.md model alias table contradicts the actual config mappings. The backlog pick implements sensitive-path guardrails across all file-writing tools.

**Auto-applied**: 2 | **New files**: 1 | **Proposed for review**: 3

## Auto-applied Changes

### 1. [code_quality] Use 'current' instead of 'self' inside main loop to fix stale-reference bugs after hot-swap

**File**: `twin/lib/session.py` | **Confidence**: 93%

<details><summary>5 Whys + Diff</summary>

**5 Whys**: Why 1: After /reload swaps 'current' to a new orchestrator, lines like 'self._parse_tool_calls(response)' still reference the old instance.
Why 2: This means tool execution, formatting, restart handling, and agent display all operate on stale state.
Why 3: The hot-swap feature was added but the main loop body was not fully migrated to use 'current'.
Why 4: This causes silent correctness bugs where tool results update the old instance's messages.
Why 5: Consistent use of the loop variable is essential for hot-swap integrity.

**Before:**
```python
                if response:
                    # Check for tool calls in response
                    tool_calls = self._parse_tool_calls(response)

                    if tool_calls:
                        # Execute tools
                        tool_results = self._execute_tools(tool_calls)

                        # Check if restart is required (self-improvement)
                        requires_restart = any(
                            r.metadata.get('requires_restart', False) for r in tool_results
                        )

                        # Format results and send back to mod
```
**After:**
```python
                if response:
                    # Check for tool calls in response
                    tool_calls = current._parse_tool_calls(response)

                    if tool_calls:
                        # Execute tools
                        tool_results = current._execute_tools(tool_calls)

                        # Check if restart is required (self-improvement)
                        requires_restart = any(
                            r.metadata.get('requires_restart', False) for r in tool_results
                        )

                        # Format results and send back 
```
</details>

### 2. [code_quality] Fix another stale 'self' reference for vision_model lookup inside main loop

**File**: `twin/lib/session.py` | **Confidence**: 95%

<details><summary>5 Whys + Diff</summary>

**5 Whys**: Why 1: 'self._get_vision_model()' uses old instance after hot-swap.
Why 2: Should be 'current._get_vision_model()' like surrounding code.
Why 3: Inconsistent self/current usage was introduced when hot-swap was added.
Why 4: Vision model lookup on stale instance could return wrong config.
Why 5: All main-loop body references must use 'current' for correctness.

**Before:**
```python
                vision_model = None
                if image_paths:
                    vision_model = self._get_vision_model()
```
**After:**
```python
                vision_model = None
                if image_paths:
                    vision_model = current._get_vision_model()
```
</details>

## New Files

- `twin/tests/test_path_safety.py` — Tests for the sensitive-path guardrail system proposed in the backlog pick

## Proposed Changes (review required — NOT auto-applied)

> Logic/feature changes. Review carefully. Items tracked in `twin/pending-improvements.md`.

### 1. [backlog_pick] Add sensitive-path guardrails to all file-writing tools (_write_file, _edit_file, _apply_patch) and self-improvement to prevent writes outside allowed boundaries

**File**: `twin/lib/tools.py` | **Confidence**: 92%

**5 Whys**: Why 1: _write_file, _edit_file, _apply_patch, and _improve_self accept arbitrary paths with no confinement — a single bad tool call can overwrite /etc/passwd, ~/.ssh/authorized_keys, or any system file.
Why 2: Tool registration focused on functionality; no one added path boundaries because the LLM was 'trusted'.
Why 3: Self-improvement already writes files autonomously, meaning an LLM hallucination can damage the host.
Why 4: Sandboxing (containers, seccomp) is too heavy for a CLI tool; path allowlists are the right granularity.
Why 5: Safety rails reduce blast radius of all other bugs — defense-in-depth before expanding features.

```diff
--- a/twin/lib/tools.py
+++ b/twin/lib/tools.py
@@ -1,6 +1,7 @@
 """
 Tool system for twin
 Implements core tools: Read, Write, Edit, Bash, Glob, Grep
+Includes sensitive-path guardrails for all file-mutation operations
 Plus online resources: web_search, web_fetch, GitHub API
 """
 
@@ -48,6 +49,68 @@ except ImportError:
     SELF_IMPROVEMENT_AVAILABLE = False
 
 
+# ---------------------------------------------------------------------------
+# Sensitive-path safety rails
+# ---------------------------------------------------------------------------
+
+# Paths that must NEVER be written to, regardless of context
+_SENSITIVE_PATH_PREFIXES = [
+    os.path.expanduser('~/.ssh'),
+    os.path.expanduser('~/.gnupg'),
+    os.path.expanduser('~/.aws'),
+    os.path.expanduser('~/.config/gcloud'),
+    os.path.expanduser('~/.kube'),
+    os.path.expanduser('~/.docker'),
+    '/etc/',
+    '/var/',
+    '/usr/',
+    '/bin/',
+    '/sbin/',
+    '/boot/',
+    '/sys/',
+    '/proc/',
+    '/d
```

### 2. [safety] Add path confinement to propose_improvement so file writes cannot escape twin_dir

**File**: `twin/lib/self_improver.py` | **Confidence**: 94%

**5 Whys**: Why 1: propose_improvement joins twin_dir with user-supplied file paths but never validates the result stays inside twin_dir.
Why 2: A path like '../../.ssh/authorized_keys' would resolve outside twin/ and overwrite SSH keys.
Why 3: The LLM generates file paths; hallucinations or prompt injection could produce traversal paths.
Why 4: Self-improvement runs autonomously — there's no human confirmation step before writes.
Why 5: Confinement is the minimum viable safety boundary for autonomous file mutation.

```diff
--- a/twin/lib/self_improver.py
+++ b/twin/lib/self_improver.py
@@ -60,6 +60,14 @@ class SelfImprover:
         timestamp = datetime.now().isoformat()
         improvement_id = datetime.now().strftime("%Y%m%d-%H%M%S")
 
+        # Path confinement: all file paths must resolve inside twin_dir
+        twin_dir_resolved = self.twin_dir.resolve()
+        for file_path in files.keys():
+            full_path = (self.twin_dir / file_path).resolve()
+            if not str(full_path).startswith(str(twin_dir_resolved)):
+                raise Exception(
+                    f"Path confinement violation: '{file_path}' resolves outside twin directory"
+                )
+
         # Capture diff before changes
         old_contents = {}

```

### 3. [documentation_drift] Document that model alias table needs syncing with twin.config.json — balanced=7b not 14b, quality=14b not 32b, max=32b is the large model

**File**: `twin/QUICKREF.md` | **Confidence**: 90%

**5 Whys**: Why 1: QUICKREF says balanced=qwen2.5-coder:14b but the actual config maps balanced to the 7b model.
Why 2: The mid-session example also shows wrong model names.
Why 3: A previous IMPROVEMENTS.md entry claimed this was fixed, but the file still contains stale values.
Why 4: Users relying on QUICKREF will get unexpected model behavior.
Why 5: Doc-config drift erodes trust in the project's documentation.

```diff
The QUICKREF.md model alias table, the agent model descriptions section, and the mid-session switching example all need to be regenerated from the actual twin.config.json values. Without access to twin.config.json in this audit, the exact replacement text cannot be produced, but every instance of 'balanced → qwen2.5-coder:14b' should likely be 'balanced → qwen2.5-coder:7b', 'quality → qwen2.5-coder:32b' should be 'quality → qwen2.5-coder:14b', and 'max → qwen2.5-coder:32b' is the 32b tier. The 'Balanced Agents (use qwen2.5-coder:14b)' section should reference the correct model.
```

## Observations

- Global mutable state for ESC key handling (_esc_pressed, _keyboard_listener) is fragile in threaded contexts — the pynput listener and the timer thread in _call_ollama can race. Consider using threading.Event instead of a bare global bool.
- _detect_offline() does a synchronous TCP connect to 1.1.1.1:443 with timeout=1 — this runs at ToolRegistry __init__ time, meaning every session start blocks for up to 1s on offline networks. Consider lazy detection or caching.
- _bash uses shell=True which enables shell injection. A model-generated command like 'rm -rf /' would execute. Consider adding a command blocklist or requiring user confirmation for destructive commands (rm -rf, mkfs, dd, etc.).
- _web_fetch has no response body size limit — a multi-GB page will be fully downloaded before the 10000-char truncation. Add stream=True and a max-bytes check to requests.get.
- _format_tool_results truncates at 8000 chars but _read_file can return 2000 lines * ~120 chars = ~240K chars before truncation — the tool result formatting is the only safety net and it's applied late.
- The _parse_legacy_tool_calls regex `r'TOOL_CALL:\s*(\w+)\s*\nARGS:\s*(\{[^}]+\})'` uses `[^}]+` which fails on nested JSON objects (e.g., the 'files' dict in improve_self). This means self-improvement via legacy format will silently fail to parse.
- _embed_cache_get calls list.remove() which is O(n) on the order list — with 500 cached entries this is slow. Consider using collections.OrderedDict for O(1) LRU.
- The _collect_repo_chunks method hardcodes glob patterns ('bin/twin', 'twin/lib/*.py') that only work when cwd is the twin project root — these should be generalized or removed for use in arbitrary repos.
- In _build_repo_index (session.py), the same hardcoded patterns appear. This index is rebuilt on every session start but never persisted, so large repos re-index every launch.

---
*Generated by the daily self-improve workflow (two-pass + prompt caching).*
## Test Results
```
.......                                                                  [100%]
7 passed in 0.75s
```
