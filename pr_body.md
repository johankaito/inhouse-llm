## Summary

Found safety issues in tools.py (unbounded bash output, no shell injection sanitisation on glob paths), a bare except in modes.py, missing domain prompts for several agents in session.py, stale documentation in QUICKREF.md (model alias table wrong), and selected the 'Sandboxed tool safety (timeouts, partial outputs)' backlog item as highest-impact smallest-shippable-slice. Also adding proper unit tests for config.py and modes.py which have zero test coverage.

**Auto-applied**: 2 changes | **New files**: 2 | **Proposed for review**: 1

## Auto-applied Changes

### 1. [code_quality] Replace bare except with specific exceptions in _check_git_email

**File**: `twin/lib/modes.py` | **Confidence**: 97%

**5 Whys**:
```
Why 1: bare `except:` catches SystemExit/KeyboardInterrupt which hides real errors.
Why 2: Because the developer used a shorthand instead of listing expected exceptions.
Why 3: Because subprocess can raise TimeoutExpired, FileNotFoundError, or OSError.
Why 4: Because catching those specifically makes debugging easier and prevents silent swallowing.
Why 5: Because this is a best-practice anti-pattern fix with zero behaviour change for normal paths.
```

<details><summary>Diff</summary>

**Before:**
```python
        except:
            pass
        return None
```
**After:**
```python
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        return None
```
</details>

### 2. [documentation_drift] Fix stale model alias table — 'fast' is listed as qwen2.5-coder:7b but twin.config.json maps 'fast' to qwen2.5-coder:3b-fast and 'balanced' to qwen2.5-coder:7b

**File**: `twin/QUICKREF.md` | **Confidence**: 95%

**5 Whys**:
```
Why 1: QUICKREF.md says fast=qwen2.5-coder:7b but twin.config.json says fast=qwen2.5-coder:3b-fast.
Why 2: The config was updated to add ultrafast/fast tiers but docs were not updated.
Why 3: Users relying on QUICKREF will pick wrong aliases.
Why 4: This directly contradicts the source of truth (twin.config.json).
Why 5: Pure doc fix, no code change, safe to apply.
```

<details><summary>Diff</summary>

**Before:**
```python
| Alias | Model | Speed | RAM | Use For |
|-------|-------|-------|-----|---------|
| `fast` | qwen2.5-coder:7b | 15-20 tok/s | 8-10GB | Daily coding, quick tasks (DEFAULT) |
| `balanced` | qwen2.5-coder:14b | 8-12 tok/s | 15-18GB | Complex code, better quality |
| `quality` | qwen2.5-coder:32b | 4-6 tok/s | 25-28GB | Critical architecture decisions |
| `reasoning` | deepseek-r1:8b | 10-15 tok/s | 10-12GB | Finance, planning, 5 Whys depth |
```
**After:**
```python
| Alias | Model | Speed | RAM | Use For |
|-------|-------|-------|-----|---------|
| `ultrafast` | qwen2.5-coder:1.5b-ultrafast | 40-60 tok/s | 3-4GB | Trivial tasks, ultra-low latency |
| `fast` | qwen2.5-coder:3b-fast | 30-40 tok/s | 4-6GB | Quick tasks, light coding |
| `balanced` | qwen2.5-coder:7b | 15-20 tok/s | 8-10GB | Daily coding (DEFAULT) |
| `quality` | qwen2.5-coder:14b | 8-12 tok/s | 15-18GB | Complex code, better quality |
| `max` | qwen2.5-coder:32b | 4-6 tok/s | 25-28GB | Critical architecture decisions |
| `reasoning` | deepseek-r1:8b | 10-15 tok/s | 10-12GB | Finance, plann
```
</details>

## New Files Created

- `twin/tests/test_config.py` — Unit tests for config.py: load_all, resolve_model_alias, validate_model_exists, get_model_for_agent edge cases
- `twin/tests/test_modes.py` — Unit tests for modes.py: directory patterns, git email detection, work hours, priority ladder

## Proposed Changes (review required — NOT auto-applied)

> These are logic/feature changes. Review carefully before cherry-picking.

### 1. [backlog_pick] Add output truncation to bash tool and glob tool to prevent unbounded output (sandboxed tool safety — smallest shippable slice of the backlog item)

**File**: `twin/lib/tools.py` | **Confidence**: 88%

**5 Whys**: Why 1: The bash tool returns raw stdout with no size cap — a command like `cat /dev/urandom | base64` or `find /` can return megabytes, blowing up the context window and crashing the session.
Why 2: Because _bash() reads result.stdout in full and returns it as-is with no truncation.
Why 3: Because the original implementation prioritised feature completeness over safety bounds.
Why 4: Because this is the 'Sandboxed tool safety (timeouts, partial outputs)' backlog item — the smallest safe slice is adding output caps.
Why 5: This is the highest-impact pending safety item because unbounded output is the most likely failure mode in practice (users running `git log`, `find .`, `cat` on large files via bash).

**Proposed diff:**
```diff
--- a/twin/lib/tools.py
+++ b/twin/lib/tools.py
@@ In _bash method, after capturing result:
 
+    MAX_OUTPUT_BYTES = 100_000  # 100KB cap
+
     def _bash(self, command: str, timeout: int = 120) -> ToolResult:
         """Execute bash command"""
         try:
             result = subprocess.run(
                 command,
                 shell=True,
                 capture_output=True,
                 text=True,
                 timeout=timeout,
                 cwd=os.getcwd()
             )
 
             output = result.stdout
+            truncated = False
+            if len(output) > MAX_OUTPUT_BYTES:
+                output = output[:MAX_OUTPUT_BYTES]
+                truncated = True
+
             if result.stderr:
-                output += f"\nSTDERR:\n{result.stderr}"
+                stderr = result.stderr
+                if len(stderr) > MAX_OUTPUT_BYTES // 4:
+                    stderr = stderr[:MAX_OUTPUT_BYTES // 4]
+                    truncated = True
+        
```

## Observations (no code change needed)

- Dimension 1 — tools.py _bash() passes user-provided `command` directly to `shell=True` with no sanitisation. This is by design (it's a bash tool), but there are no guardrails preventing destructive commands like `rm -rf /`. The 'Safety/harmlessness rails' backlog item should address this with a deny-list or confirmation prompt.
- Dimension 1 — self_improver.py has two bare `except:` blocks (lines in can_improve). These should be narrowed to `(subprocess.CalledProcessError, FileNotFoundError, OSError)` in a future pass.
- Dimension 2 — session.py _get_domain_prompt() only has entries for 'health-coach', 'technical-lead', 'travel-agent', 'wealth-planner', 'decision-framework', and 'communication-handler'. Agents like 'budget-tracker', 'learning-manager', 'startup-accelerator', 'disaster-recovery-architect', 'repo-bootstrap-architect', and 'task-manager' get no domain prompt, degrading output quality. These should be added in a follow-up.
- Dimension 5 — QUICKREF.md says the default model is 'fast' but twin.config.json sets default_model to 'balanced'. The auto_apply fix corrects the alias table but the text 'Daily coding, quick tasks (DEFAULT)' also needs updating — covered by the table replacement.
- Dimension 5 — docs/PHASE1_TOOLS_COMPLETE.md references '~/.llm-planner/lib/tools.py' (old path) and says '6 Core Tools' but the current tools.py has 9+ tools (read, write, edit, apply_patch, bash, glob, grep, repo_search, plus online tools). This doc is stale.
- Dimension 6 — _grep in tools.py returns unbounded output. The propose_only change includes a grep cap at 500 lines.
- Dimension 1 — In session.py the main loop references `self.agent` and `self._parse_tool_calls` even when `current` may be a different orchestrator instance (after /reload returns a new instance). This could cause tool calls to execute on the wrong instance. Needs investigation.

---
*Review auto-applied changes carefully. Proposed changes require manual implementation.*
*Generated by the daily self-improve workflow.*
## Test Results
```
.......                                                                  [100%]
7 passed in 1.44s
```
