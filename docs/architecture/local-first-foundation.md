# Local-First Foundation — zero-API-token, model- and engine-swappable

**Tracking issue:** [#12](https://github.com/johankaito/inhouse-llm/issues/12)
**Date:** 2026-06-10 (statuses updated 2026-06-11)
**Status:** Stages 0–3 implemented and verified on the M1 Max (see §6 statuses and §7 verification evidence)
**Author:** John Keto
**Companion:** [`docs/evaluations/open-source-alternatives.md`](../evaluations/open-source-alternatives.md)

---

## Purpose

Define the foundation that lets inhouse-llm be a maximally Claude-Code-like setup with **zero ongoing API-token spend**, where **models and inference engines can be swapped freely without rewriting the harness** (`twin`, OpenCode, or whatever comes next).

The thesis in one line: **treat the model server as a replaceable commodity behind one OpenAI-compatible URL, and keep all the durable value (tools, RAG, mode/5-Whys, the text-edit-format technique) in the harness layer above it.**

This plan is adjusted by the local `twin/` audit (see the evaluation doc) and by re-verification of llama.cpp / llama-swap upstream docs as of 2026-06-10.

---

## 1. The harness contract

Everything above the model server depends only on this contract — never on which engine is running.

1. **One base URL, OpenAI-compatible.** The harness talks to a single endpoint exposing `POST /v1/chat/completions` (and `/v1/models`, `/v1/embeddings`). Optionally the same endpoint is **Anthropic-compatible** (`POST /v1/messages`) for tools that prefer that shape.
2. **The model is selected by the `model` field in the request body** — e.g. `"model": "qwen2.5-coder:14b"`. The harness never hardcodes a per-model endpoint, port, or engine.
3. **Engine specifics never leak into the harness.** GGUF paths, GPU/Metal layer counts, chat-template choice, `--jinja`, KV-cache type, context length, host/port — all live *behind* the base URL. Changing any of them must not require a harness code change.
4. **Auth is a single bearer token (or none on localhost).** On the local path there is **no key**, which is what keeps token spend at zero and satisfies the offline tenet.

Why this contract: both recommended engine features key off exactly the `model` field — llama.cpp `llama-server` **router mode** ("the `model` parameter is required to route the request to the right instance") and `llama-swap` (extracts the `model` value and loads/swaps the matching upstream). Building the harness to the contract means Ollama → `llama-server` → a future engine, or Mac → home-server, or `qwen2.5` → `qwen3`, are all config changes, not code changes.

> **Audit note:** `twin` is already close to this. It calls `ollama.chat(model=…)` and resolves the model from config/alias, so the *model-by-field* half holds. The gap is that it binds to Ollama's native client rather than a generic OpenAI-compatible client; closing that (or fronting Ollama with its own `/v1`) is the only change needed to make `twin` fully contract-compliant. Ollama already exposes `/v1` today (verified locally), so this is low-effort.

---

## 2. Default engine: llama.cpp `llama-server` with `--jinja`

**Recommended default engine on both hosts: llama.cpp `llama-server`, launched with `--jinja`.**

- `llama-server` is the reference implementation, ships an OpenAI-compatible `/v1`, and is a single native binary (no Python runtime) — aligns with the lightweight preference.
- **`--jinja` is mandatory for tool calling.** It tells the server to use the model's embedded Jinja chat template, which is what renders tool/function-call blocks correctly. Without it, an OpenAI-style request carrying a `tools` array is **rejected** (`tools param requires --jinja flag`).
- **Pin a known-good chat template per model.** `--jinja` alone is not always enough: some GGUF templates crash or mis-render tool calls, and you may need `--chat-template-file <tool_use.jinja>` or, as a fallback, `--chat-template chatml`. This is not hypothetical — OpenCode's own issue tracker documents a tool-call template crash against `llama-server` for a Qwen3-Coder GGUF (`anomalyco/opencode#1890`), fixed only by `--jinja` plus a corrected template. **Treat the (engine version, model, chat template) tuple as a pinned unit.**
- **Router mode** lets one `llama-server` hold several models and route by the `model` field; in single-model mode the field is ignored. Either way the harness contract is satisfied.

**Where Ollama fits.** Ollama is the pragmatic current state — `twin` uses its native API and it also exposes `/v1`. It embeds llama.cpp, so it is a legitimate engine under the same contract. Keep Ollama for day-to-day until `llama-server` is stood up and A/B'd; the contract makes the swap painless and reversible. The empirical check in the evaluation doc deliberately ran against Ollama to reflect the actual current setup.

---

## 3. `llama-swap` as front door — only when mixing engines or hosts

Add a proxy **only** when there is something to multiplex: more than one engine, more than one host, or hot model-swapping behind a single URL.

- **Use `mostlygeek/llama-swap`.** It is a Go **single static binary + one YAML file**, an OpenAI- **and** Anthropic-compatible `/v1` front door that reads the request's `model` field and loads/swaps the correct upstream (`llama-server`, vLLM, Ollama, etc.). It fits the harness contract exactly and the lightweight preference (one binary, no Python, no desktop app).
- **Skip LiteLLM.** LiteLLM solves the same fan-out but is a Python service with a heavier dependency surface and more recurring maintenance — the opposite of "one-time complexity over recurring cost", and not TypeScript/lightweight-first. There is no multi-vendor billing/routing problem here (the whole point is zero API spend), so LiteLLM's main value-add does not apply.
- **Do not add the proxy on day one.** A single host with one engine needs no front door — the harness points straight at `llama-server`/Ollama. Introduce `llama-swap` at Stage 4 (home-server) or whenever engine-mixing begins.

```
Harness (twin / OpenCode)
        │  OpenAI-compatible /v1, model=<name>, no key on localhost
        ▼
   [ llama-swap ]        ← OPTIONAL: only when mixing engines/hosts
        │
   ┌────┴───────────────┐
   ▼                    ▼
llama-server --jinja   llama-server --jinja
 (M1 Max, today)        (RTX 5090 host, later)
```

---

## 4. Per-hardware model picks

The owner's hardware is an **M1 Max MacBook, 32 GB unified memory (portable, today)** and a **future RTX 5090, 32 GB VRAM home-server (timeline unconfirmed)**. **Because the home-server timeline is unconfirmed, the Mac-only picks are the actionable surface today**; the RTX column is forward planning.

| Role | M1 Max 32 GB (today — actionable) | RTX 5090 32 GB (later — planning) |
|---|---|---|
| Fast daily / autocomplete | `qwen2.5-coder:7b` (~4.7 GB) | same, near-instant |
| **Daily-driver coding agent** | **`qwen2.5-coder:14b` (~9 GB)** or **`qwen3-coder` (~18.6 GB, MoE)** | `qwen3-coder` / 30B-class at higher quant + longer ctx |
| Max-quality / hard tasks | `qwen2.5-coder:32b` (~20 GB, leaves headroom for KV at q8_0) | 32B dense or larger MoE, much faster |
| Embeddings (RAG) | `nomic-embed-text` (twin's `repo_search`) | same |
| Reasoning/planning | `deepseek-r1:8b` or `qwen3` | larger reasoning model |

Notes:
- **32 GB unified (Mac) ≈ 32 GB VRAM (5090) in capacity**, so the 5090's win is **throughput and longer usable context**, not dramatically larger models. Do not assume the home-server unlocks a different model tier; assume it unlocks speed.
- On the Mac, **`:32b` + long context is tight** — rely on the q8_0 KV-cache floor (§5) and a capped `num_ctx` to fit.
- `qwen3-coder:latest` (18.6 GB) is already pulled and is the strongest single local coder available on the Mac today; it is a reasonable daily driver if 14B feels weak.
- All picks are Apache-2.0 Qwen weights or equivalent — no licence-integrity or token-spend concern.

---

## 5. Risk / failure-mode table

| # | Failure mode | Why it bites locally | Mitigation | inhouse-llm status |
|---|---|---|---|---|
| 1 | **Silent `num_ctx` truncation** | Ollama defaults `num_ctx` to a small value (≈4k) and **silently drops** older context; multi-step tool loops then "forget" earlier steps and degrade with no error. The single most common local-agent failure. | Set `num_ctx` **explicitly to ≈16–32k** on every engine. On Ollama, pass it in `options` (or bake into a Modelfile); on `llama-server`, set `--ctx-size`. Verify the server logs the value you set. | **Already mitigated in `twin`** — `_build_ollama_options` sets `num_ctx` from config (default **32768**) plus a `/ctx` override. **Any new harness (OpenCode) must be checked** — confirm it raises `num_ctx`, do not assume. |
| 2 | **Edit-format / tool-call non-adherence** | Small local models drift from strict native function-calling and unified-diff formats, producing unappliable edits or malformed tool JSON. | Prefer a **text-edit format the model can hit reliably**, validate before writing, and pin a known-good chat template (`--jinja` + `--chat-template-file`). | **`twin`'s text-edit-format technique handles this** — parse tool calls from text (structured JSON + legacy fallback) and `apply_patch` runs `patch --dry-run` before committing. **Keep this regardless of harness** (§6). |
| 3 | **Tool-surface bloat** | Injecting many verbose tool schemas into the prompt — even in plain chat — confuses small models and burns context. Documented in `anomalyco/opencode#1890` (OpenCode injects a `tools` block + Jinja template even for plain chat, tripping `llama-server`). | Expose a **minimal tool set** to local models; scope agents; avoid sending tool schemas when no tool is needed. | `twin` exposes 13 focused tools described in-prompt. When adopting OpenCode, **scope its agents/tools** rather than enabling everything. |
| 4 | **KV-cache quantisation floor** | To fit long context on 32 GB, it is tempting to quantise the KV cache hard (q4); below ~q8_0 this measurably degrades long-context coding and tool-use quality. | **Treat `q8_0` as the floor.** Use `--cache-type-k q8_0 --cache-type-v q8_0` to roughly halve KV memory vs f16 with negligible quality loss; **do not go below q8_0**. | New guidance for the `llama-server` path; not yet exercised (Ollama path today uses its own defaults). |
| 5 | **Context rot** | Even within `num_ctx`, very long contexts degrade attention ("lost in the middle"); maxing the window out *hurts* quality and speed. | Keep working context **tight**: retrieve with RAG instead of dumping whole files, summarise history, and size `num_ctx` to need (16–32k), not to maximum. | **`twin` already leans this way** — `repo_search` RAG + deterministic history summarisation. Reinforce when configuring OpenCode. |

---

## 6. Staged adoption plan

Each stage is independently shippable and reversible. **`twin`'s text-edit-format technique is preserved at every stage** — it is the harness-independent, robust-on-small-models asset, and the fallback if any external harness is dropped.

- **Stage 0 — baseline. DONE (pre-existing).** Ollama + Qwen-Coder + `twin`: text-edit-format loop, explicit `num_ctx=32768`, local RAG. Still the safety net.
- **Stage 1 — adopt OpenCode as daily driver. DONE (2026-06-11).** OpenCode pinned at **1.17.1** (npm `opencode-ai`), pointed at local Ollama `/v1` via the `model` field. Zero-key multi-step edit validated first-hand (§7). `num_ctx` handled by a Modelfile-baked variant (`qwen2.5-coder:14b-ctx32k`, `PARAMETER num_ctx 32768`) because Ollama's `/v1` path does not honour per-request `num_ctx`. `twin`'s `/edit` repointed: `editor.command=opencode` with `editor.fallback=aider` and `editor.model` override in `twin.config.json`. Config example: `docs/setup/opencode.json.example`.
- **Stage 2 — stand up `llama-server --jinja`. DONE (2026-06-11).** `scripts/llama-server.sh` serves GGUFs **directly from Ollama's blob store** (no duplicate storage), `--jinja`, `--ctx-size 32768`, KV q8_0 floor. Native `tool_calls` verified over `/v1` (§7). `twin`'s `openai-compat` engine adapter verified against it streaming and non-streaming. Pinned tuple: llama.cpp **b9580** + qwen3-coder GGUF + embedded template.
- **Stage 3 — invert the MCP gap. DONE (2026-06-11).** `twin/lib/mcp_server.py`: zero-dependency stdio MCP server exposing `repo_search` (+ `gh_search_code`/`gh_get_pr` when `GITHUB_TOKEN` is present). Registered in OpenCode (`mcp.twin`); end-to-end verified — OpenCode + qwen3-coder natively invoked `twin_repo_search` and used the RAG results (§7).
- **Stage 4 — add the home-server. PENDING (RTX 5090; timeline unconfirmed).** Run `llama-server --jinja` on the server, put **`llama-swap` in front** to route by `model` field across Mac + server. **No harness change** — purely base-URL/model routing.

### What stays, regardless of harness

- **`twin`'s text-edit-format technique** (text-parsed tool calls + `apply_patch` dry-run validation) — robust on small local models where native function-calling drifts.
- **The harness contract** (§1) — the reason every swap above is config, not code.
- **Explicit `num_ctx`** and the **q8_0 KV floor** — the two settings that most protect output quality on 32 GB.
- **`twin`'s differentiators** — RAG, mode detection, 5-Whys, Claude-format context, self-improve — surfaced to whatever harness is in front via MCP.

---

## 7. Verification evidence (2026-06-11, M1 Max 32GB)

### Tool-calling A/B matrix — same prompt, same `tools` array

| Model | Ollama `/v1` | `llama-server --jinja` (b9580) |
|---|---|---|
| qwen2.5-coder:14b | ✗ tool call emitted as fenced-JSON **text**; zero tools executed | ✗ tool call emitted as `<tools>`-wrapped **text**; `tool_calls: null` |
| qwen3-coder (30B-A3B) | ✓ full OpenCode loop: Read → Edit → Write → bash; tests pass | ✓ native `tool_calls`, `finish_reason: tool_calls` |

**Conclusion:** the failure follows the **model**, not the engine. qwen2.5-generation models are below the native-function-calling floor for Claude-Code-style loops on either engine; qwen3-coder clears it on both. This is risk #2 (edit-format/tool-call non-adherence) observed first-hand, and is why `twin.config.json` gained the `agentic` alias and `editor.model` pins qwen3-coder for `/edit`.

### Stage 1 — OpenCode zero-key multi-step edit (Ollama `/v1`, qwen3-coder)

Task: add `subtract()` to `calc.py`, create `test_calc.py`, run it. Executed with `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` unset against `localhost:11434/v1`. Result: both edits applied via native tool calls, generated unittest suite ran `OK` (2 tests). Caveat: first call pays ~1 min of 18GB model load — budget timeouts accordingly.

### Stage 2 — twin `openai-compat` adapter vs llama-server

`build_engine({provider: openai-compat, base_url: http://127.0.0.1:8080/v1})` → non-streaming round trip 0.7s, streaming 29 chunks 0.7s, `num_ctx`/`keep_alive` correctly withheld (server-side concerns). Engine swap is a 2-line config change, zero harness code touched.

### Stage 3 — OpenCode → twin MCP → RAG

`opencode mcp list` shows `twin connected`. Live run: qwen3-coder natively invoked `twin_repo_search {"query": "engine adapter harness contract", "path": "twin/lib"}` and summarised the top RAG hit correctly. Tool surface exposed: 1–3 tools (flat schemas), honouring the ≤8 ceiling.

---

## Sources

Primary sources re-verified 2026-06-10:

- llama.cpp server / function-calling docs — `--jinja`, chat templates, router mode: <https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md>, <https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md>
- OpenCode ↔ `llama-server` `--jinja` tool-call failure (primary evidence for risks 2–3): <https://github.com/anomalyco/opencode/issues/1890>
- `llama-swap` (Go front door, OpenAI/Anthropic-compatible, model-field routing): <https://github.com/mostlygeek/llama-swap>
- Qwen3-Coder SWE-bench Verified figures (vendor-reported; ≈70%): <https://qwen.ai/blog?id=qwen3-coder-next> — the Qwen3.6-27B 77.2% figure is **secondary/unverified** (see evaluation doc).
- `twin/` source audit: `twin/lib/session.py` (`_build_ollama_options`, `ollama.chat`, `_transition_to_aider`), `twin/lib/tools.py` (tool registrations, `_repo_search`, `_apply_patch`), `twin/twin.config.json`.
