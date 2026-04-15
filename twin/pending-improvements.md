# Pending Improvements

<!-- AUTO-MANAGED: do not edit manually -->

## 2026-04-15 | add-sensitive-path-guardrails-to-all-fil | pending
**File**: `twin/lib/tools.py`
**Description**: Add sensitive-path guardrails to all file-writing tools (_write_file, _edit_file, _apply_patch) and self-improvement to prevent writes outside allowed boundaries
**5 Whys**: Why 1: _write_file, _edit_file, _apply_patch, and _improve_self accept arbitrary paths with no confinement — a single bad tool call can overwrite /etc/passwd, ~/.ssh/authorized_keys, or any system file.
Why 2: Tool registration focused on functionality; no one added path boundaries because the LLM w
**Proposed diff**:
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
+# Paths that must NEVER be written to, r
```


## 2026-04-15 | add-path-confinement-to-propose_improvem | pending
**File**: `twin/lib/self_improver.py`
**Description**: Add path confinement to propose_improvement so file writes cannot escape twin_dir
**5 Whys**: Why 1: propose_improvement joins twin_dir with user-supplied file paths but never validates the result stays inside twin_dir.
Why 2: A path like '../../.ssh/authorized_keys' would resolve outside twin/ and overwrite SSH keys.
Why 3: The LLM generates file paths; hallucinations or prompt injection co
**Proposed diff**:
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
+                    f"Path confinement violat
```


## 2026-04-15 | document-that-model-alias-table-needs-sy | pending
**File**: `twin/QUICKREF.md`
**Description**: Document that model alias table needs syncing with twin.config.json — balanced=7b not 14b, quality=14b not 32b, max=32b is the large model
**5 Whys**: Why 1: QUICKREF says balanced=qwen2.5-coder:14b but the actual config maps balanced to the 7b model.
Why 2: The mid-session example also shows wrong model names.
Why 3: A previous IMPROVEMENTS.md entry claimed this was fixed, but the file still contains stale values.
Why 4: Users relying on QUICKREF
**Proposed diff**:
```diff
The QUICKREF.md model alias table, the agent model descriptions section, and the mid-session switching example all need to be regenerated from the actual twin.config.json values. Without access to twin.config.json in this audit, the exact replacement text cannot be produced, but every instance of 'balanced → qwen2.5-coder:14b' should likely be 'balanced → qwen2.5-coder:7b', 'quality → qwen2.5-coder:32b' should be 'quality → qwen2.5-coder:14b', and 'max → qwen2.5-coder:32b' is the 32b tier. The 'Balanced Agents (use qwen2.5-coder:14b)' section should reference the correct model.
```

## 2026-04-15 | tests-for-reload-hot-swap-state-migratio | pending
**File**: `twin/tests/test_hot_reload_and_augment.py`
**Description**: Tests for reload hot-swap state migration, env snapshot building, and tool intent mapping — the backlog pick for this run
**5 Whys**: Why 1: _reload_modules performs state migration between old and new SessionOrchestrator instances with no test coverage.
Why 2: If state migration silently drops fields (e.g. repo_index, running_summary), the session degrades without visible error.
Why 3: _augment_with_env/_augment_with_tools/_augme
**Proposed diff**:
```diff
See new_files entry for twin/tests/test_hot_reload_and_augment.py
```


## 2026-04-15 | add-path-traversal-guard-to-propose_impr | pending
**File**: `twin/lib/self_improver.py`
**Description**: Add path traversal guard to propose_improvement to prevent writes outside twin_dir
**5 Whys**: Why 1: propose_improvement joins twin_dir with arbitrary file_path keys from the LLM without resolving or checking.
Why 2: A malicious or hallucinated path like '../../.bashrc' would write outside the twin directory.
Why 3: Self-improvement is an autonomous capability — the LLM chooses the file path
**Proposed diff**:
```diff
--- a/twin/lib/self_improver.py
+++ b/twin/lib/self_improver.py
@@ -68,6 +68,14 @@
 
         timestamp = datetime.now().isoformat()
         improvement_id = datetime.now().strftime("%Y%m%d-%H%M%S")
 
+        # Path traversal guard: all files must resolve within twin_dir
+        for file_path in files.keys():
+            full_path = (self.twin_dir / file_path).resolve()
+            twin_resolved = self.twin_dir.resolve()
+            if not str(full_path).startswith(str(twin_resolved) + os.sep) and full_path != twin_resolved:
+                raise ValueError(
+                    f"Path 
```

## 2026-04-15 | enrich-citation-style-answers:-add-line- | pending
**File**: `twin/lib/session.py`
**Description**: Enrich citation-style answers: add line-range anchors to _retrieve_repo_context hits and format _append_sources as clickable file:line references
**5 Whys**: Why 1: Users need to verify LLM claims by checking the actual source lines.
Why 2: Current _append_sources outputs raw snippet text without actionable line references.
Why 3: The repo index already stores start_line per chunk but it's not surfaced in citations.
Why 4: Without verifiable citations, l
**Proposed diff**:
```diff
--- a/twin/lib/session.py
+++ b/twin/lib/session.py
@@ _retrieve_repo_context method
     def _retrieve_repo_context(self, query: str, max_chunks: int = 3) -> List[Dict[str, Any]]:
         """Retrieve top repo chunks based on simple token overlap"""
         if not self.repo_index:
             return []
 
         tokens = re.findall(r'\w+', query.lower())
         token_set = set(tokens)
         if not token_set:
             return []
 
         scored = []
         for chunk in self.repo_index:
             chunk_tokens = set(re.findall(r'\w+', chunk['text'].lower()))
             score 
```

