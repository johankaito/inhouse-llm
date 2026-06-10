# Evaluation: OSS Claude-Code-equivalents — leverage, ignore, or replace inhouse-llm?

**Tracking issue:** [#12](https://github.com/johankaito/inhouse-llm/issues/12)
**Date:** 2026-06-10
**Status:** Decided
**Author:** John Keto

---

## TL;DR (headline verdict)

**Do not wholesale-replace inhouse-llm. Keep the core (twin + Aider + Ollama + Qwen2.5-Coder), and *leverage* OpenCode as the daily-driver local agent loop.** Ignore the other two candidates: OpenClaude (as pitched) is vaporware and its real namesake carries a licence-integrity flag; Open Design is a real, well-built tool but the wrong product category (a GUI design studio, not a coding agent).

| | Verdict | Confidence |
|---|---|---|
| **OpenClaude** | **Ignore** | 96% |
| **OpenCode** | **Leverage** | 90% |
| **Open Design** | **Ignore** | 96% |
| **Headline (inhouse-llm)** | **Keep core + leverage OpenCode; do not replace** | 93% |

All three user-supplied descriptions were treated as unverified and checked against primary sources (GitHub API, `LICENSE` files, official docs) with an adversarial second pass. The candidate facts below are primary-source verified except where flagged.

---

## Method

A multi-agent research pass ran three independent discovery angles per candidate (official-repo, capability, skeptic), merged each into a fact sheet, then ran an adversarial verifier that tried to refute every load-bearing claim against a second source. Verdicts were then assessed against the owner's trade-off hierarchy. Anything that could not be independently confirmed is listed as a residual uncertainty, not stated as fact.

---

## What inhouse-llm actually is (baseline)

- **Goal:** self-hosted, terminal-native, Claude-Code-equivalent coding setup on open models. **Hard tenet: privacy/offline.**
- **Stack:** Ollama (local serving) + Aider (Apache-2.0, automated file editing) + Qwen2.5-Coder 7B/14B/32B (Apache-2.0) + the custom `twin` CLI.
- **`twin` is not just a planner.** `twin/lib/session.py` runs a real agentic tool-use loop over Ollama (parses `TOOL_CALL:` markers). `twin/lib/tools.py` provides read/write/edit, bash, glob, grep, `apply_patch`, `repo_search` (local `nomic-embed-text` embeddings + cosine similarity = lightweight RAG), `web_search`, `web_fetch` (+ optional local Jina proxy), `gh` code/PR tools, and a self-improve tool. Plus: agent system (`~/.claude/agents/`), work/personal mode detection, 5-Whys enforcement, Claude-Code-format context tracking, learning loop. **`twin` has no MCP support today.**
- **Owner trade-off hierarchy:** (1) never sacrifice data integrity/accuracy → (2) protect DX/simplicity/time → (3) flex on performance/cost → (4) trade flexibility/bleeding-edge.
- **Owner preferences:** TypeScript-first; lightweight over heavyweight; accept one-time complexity to avoid recurring cost; privacy/offline is non-negotiable for the core loop.

---

## Evaluation matrix

| Attribute | OpenClaude *(as pitched)* | OpenClaude *(real: `Gitlawb/openclaude`)* | OpenCode *(`anomalyco/opencode`)* | Open Design *(`nexu-io/open-design`)* |
|---|---|---|---|---|
| Real & as-described? | **No — vaporware** (repo 404, no crate) | Real, but **mismatched** vs pitch | **Yes — accurate** | **Yes — accurate, but wrong category** |
| Repo | `github.com/OpenClaudia/openclaude` → **404** | `github.com/Gitlawb/openclaude` | `github.com/anomalyco/opencode` (ex-`sst/opencode`) | `github.com/nexu-io/open-design` |
| Licence | claimed MIT (unverifiable) | **NOASSERTION** (derived from Anthropic proprietary; unauthorised redistribution) | **MIT** (verified) | **Apache-2.0** (verified, full text) |
| Language | claimed Rust (**none exists**) | TypeScript / Node ≥22 | TypeScript / Bun | TypeScript (Next.js 16 + Electron) |
| Popularity | none (no repo) | 28.5k★ | **172k★** | ~62.5k★ *(steep star/age curve — caution)* |
| Maintenance | none | very active (v0.18.0, 2026-06-10) | very active (v1.17.0, 2026-06-10) | active (v0.9.0, 2026-06-02) |
| Local / offline | claimed air-gapped (unverifiable) | partial (Ollama mode only; cloud-client by design) | **Yes** (Ollama/llama.cpp/LM Studio, no key on local path) | partial — **data-local only; BYOK inference required** |
| GGUF / Ollama | claimed any GGUF (unverifiable) | Ollama yes; GGUF no | Ollama yes; GGUF indirect (via local server) | Ollama indirect; GGUF no |
| Autonomous file editing | — | Yes | **Yes** (build agent) | indirect (delegates to external CLI) |
| Agent loop | — | Yes | **Yes** (build/plan agents, subagents) | **No** (orchestrates external agents) |
| Built-in RAG | — | No | No | No |
| MCP | — | Yes | **Yes (strong: local + remote, OAuth/DCR)** | Yes (**server** side only) |
| Terminal-native | — | Yes (CLI) | **Yes** (TUI; also desktop/IDE/web) | No (GUI/desktop/web-first) |
| **Verdict** | **Ignore** | **Ignore** | **Leverage** | **Ignore** |
| **Confidence** | **96%** | **96%** | **90%** | **96%** |

---

## Per-candidate findings

### 1. OpenClaude — Ignore (96%)

**The pitched tool does not exist.** The "fully open-source (MIT), built in Rust, any GGUF, no API keys / no internet" description traces near-verbatim to the marketing page `openclaudia.com`, but its linked repo `github.com/OpenClaudia/openclaude` returns **HTTP 404** and there is **no `openclaude` crate on crates.io** (`cargo install openclaude` fails). The only real artifact in that org is `OpenClaudia/openclaudia-skills` — a pack of marketing *skills* for Claude Code (by Quanlai Li / quanl.ai), not a standalone Rust assistant. The pitched profile is effectively vaporware.

**The real namesake is a different, licence-tainted tool.** The dominant tool that owns the bare name is `Gitlawb/openclaude` (28.5k★) — a **TypeScript** Claude Code fork with a strong agent loop, file editing, MCP, and an Ollama backend. But its `LICENSE` is **NOASSERTION**: a NOTICE stating the code is "derived from Anthropic's Claude Code CLI … proprietary software, Copyright (c) Anthropic PBC, all rights reserved" and "redistributed **without** Anthropic's authorization." Only its own diffs are MIT "where legally permissible." Adopting it as the core of a self-hosted product imports unauthorised-redistribution risk — a **tier-1 (data integrity / clean foundation) violation** before cost is even considered. It is also a multi-provider cloud client by design (breaks the offline tenet), has no GGUF and no RAG. Seven-plus repos share the name, so any "just install openclaude" instruction is ambiguous.

> **Adjacent real find (not OpenClaude):** `opencrust-org/opencrust` (Rust, MIT, RAG, MCP, ~133★) is a genuine Rust multi-agent assistant that loosely matches the *vibe* of the pitch. It is **not** OpenClaude and does not claim GGUF/air-gapped — but if a Rust + offline + RAG assistant is ever wanted, evaluate it on its own merits rather than the false OpenClaude claim.

**Why ignore:** there is nothing real to leverage (vaporware), and the one real tool of the name fails the highest tier of the hierarchy on licence integrity and breaches the offline tenet.

### 2. OpenCode — Leverage (90%)

**Real and accurately described.** Canonical project is `anomalyco/opencode` (formerly `sst/opencode`, which redirects), site `opencode.ai`, **MIT**, **TypeScript/Bun**, **172k★**, latest release **v1.17.0 (2026-06-10)**, very actively maintained by the SST/Anomaly team. Every part of the user's claim checks out: open-source coding agent replicating Claude Code (file editing, refactoring, command execution via build/plan agents), free, bring-your-own keys for 75+ providers, **and** fully local models (Ollama, llama.cpp, LM Studio, any OpenAI-compatible endpoint) with no key on the local path.

**It closes twin's single biggest gap — MCP** — with strong support (local + remote servers, OAuth/Dynamic Client Registration), where twin has none. It overlaps almost entirely with twin's *generic* agent loop and Aider's editing role, and matches the privacy/offline tenet on the local path.

**Where twin still wins:** built-in lightweight RAG (`repo_search`), and the Claude-Code-ecosystem glue the owner uses daily (`~/.claude/agents/` loading, mode detection, 5-Whys, Claude-format context, self-improve). OpenCode has **no built-in RAG** (only `@`-file fuzzy search) and none of that glue.

**Name-collision caveat (verified):** a separate, now-archived **Go** project `opencode-ai/opencode` (by Kujtim Hoxha) was renamed to **Crush** under the Charm team (`charmbracelet/crush`, licence NOASSERTION). The SST team kept the OpenCode name and rewrote it in TypeScript — that rewrite is today's canonical project. Any source calling OpenCode "written in Go" means the dead project. Pin to `anomalyco/opencode`.

**Why leverage (not replace, not ignore):**
- **Not replace** — retiring twin would discard its differentiated RAG + ecosystem glue (a tier-1 working-state regression).
- **Not ignore** — it closes the MCP gap, fits TS-first / lightweight / one-time-complexity-over-recurring-cost, and runs on the existing Ollama/Qwen stack at zero recurring cost.
- **Leverage, additively** — two paths:
  - **Path A (cheapest, hours):** adopt OpenCode as the daily local agent on the existing Ollama + Qwen2.5-Coder stack. Validate the zero-key offline path first and raise Ollama `num_ctx` to ~16–32k or tool calls fail.
  - **Path B (higher value, days):** stand up an MCP **server** exposing twin's unique tools (`repo_search`/RAG, `gh` search, self-improve, mode/5-Whys context) and have OpenCode consume them. This closes the MCP gap *by inversion* — no need to write MCP into 4500 LOC of Python — and lets OpenCode also absorb Aider's editing role over time, shrinking the stack.

### 3. Open Design — Ignore (96%)

**Real, accurate, well-maintained — but the wrong category.** `nexu-io/open-design` (site `open-design.ai`) is a genuine **Apache-2.0** (verified full LICENSE text), TypeScript-dominant, local-first **design-artifact studio** built on Next.js 16 + Electron. "Claude Design" is itself a real Anthropic Labs product (announced 2026-04-17), so the positioning is not hallucinated.

But it is a **design tool, not a coding agent**: it generates UI prototypes, decks, images, video and dashboards from Markdown Skills + `DESIGN.md` design systems. It has **no autonomous agent loop** (it orchestrates external coding-agent CLIs), no Aider-style autonomous file editing, **no RAG**, no GGUF, and is GUI/desktop/web-first — not a terminal TUI. Its MCP support is the **server** side (twin would need a brand-new MCP **client** to consume it). "Local-first" refers to data/app residency (local SQLite, no telemetry), **not inference** — it is BYOK and generally requires credentials, **breaching the hard offline tenet** for the core loop. The Electron + Next.js stack also contradicts the lightweight preference. A ~62.5k★ count on a repo created 2026-04-28 is an anomalous star/age curve — treat star count as a weak maturity proxy.

**Why ignore:** relevance-driven, not hallucination-driven. Near-zero functional overlap with a coding agent; cannot replace or augment twin or Aider; the only conceivable touchpoint (generate a UI mockup from a brief) is not an inhouse-llm goal and would be high-cost, recurring, and offline-breaching to integrate. Revisit only if inhouse-llm ever adds a non-core UI-mockup feature — and even then prefer a lighter, fully-local path.

---

## Headline recommendation — 5-Whys

**Recommendation: keep inhouse-llm's core (twin + Aider + Ollama + Qwen2.5-Coder) and leverage OpenCode as the daily local agent loop, additively (ideally exposing twin's differentiated tools to OpenCode over MCP). Ignore OpenClaude and Open Design. Do not wholesale-replace inhouse-llm.** Confidence: 93%.

1. **Why not wholesale-replace inhouse-llm with one of these tools?**
   Because only one candidate (OpenCode) is both real-as-described *and* category-correct. OpenClaude (as pitched) is vaporware and its real namesake is licence-tainted; Open Design is the wrong product category. A wholesale replacement needs a single tool that covers the whole job — none does without losing capability.

2. **Why not even replace `twin` with OpenCode, the one good fit?**
   Because `twin` still owns differentiated capability OpenCode lacks — built-in local RAG (`repo_search` via `nomic-embed-text`) and the Claude-Code-ecosystem glue (loads `~/.claude/agents/`, mode detection, 5-Whys, Claude-format context, self-improve). Replacing would sacrifice working, integrated capability — a tier-1 violation (never sacrifice data integrity / working state).

3. **Why leverage OpenCode at all, rather than keep building `twin`'s loop?**
   Because `twin`'s *generic* agent loop is commodity work that a 172k★, MIT, TypeScript, actively-maintained project now does better — and in the owner's preferred language. Maintaining a bespoke Python loop is exactly the recurring cost the preferences say to avoid (TS-first; lightweight over heavyweight; one-time complexity over recurring cost). OpenCode also closes twin's single biggest gap: MCP.

4. **Why does leveraging not breach the privacy/offline hard tenet?**
   Because OpenCode runs fully against local Ollama with no API key on the local path (verified — with the caveat to validate that path and raise `num_ctx`). It uses the same local stack twin/Aider already run on. By contrast OpenClaude breaches the tenet by design (cloud multi-provider client) and Open Design breaches it (BYOK inference required) — which is part of why both are ignored.

5. **Why is the additive split (OpenCode loop + `twin` glue, ideally over MCP) the optimal structure, rather than just running both side by side?**
   Because the highest-leverage move is to invert the MCP gap: expose twin's unique tools as an MCP **server** that OpenCode (the maintained TS host) consumes — gaining MCP without writing it into 4500 LOC of Python, and letting OpenCode absorb Aider's editing role over time to shrink the stack. This satisfies every tier: tier-1 integrity preserved (keep twin's working tools), tier-2 DX/simplicity improved (offload the commodity loop, fewer hand-maintained components), tier-3 cost flat (MIT, local, zero recurring), tier-4 flexibility retained (MCP is an open standard, not lock-in).

**Why 93% and not higher:** identity, licence, language, maintenance, MCP and local-model support are all primary-source verified (per-candidate confidence 90–98%). The headline is held below the >99.2% certainty bar by two live residuals: (a) OpenCode's fully-offline zero-key path is documented as a prerequisite and proven mainly via a third-party demo, so it must be validated locally before being trusted as the core loop; and (b) OpenCode's rapid release cadence (~817 releases) is a DX-churn risk — pin a version, do not auto-track `dev`.

---

## Recommended next actions

1. **Validate OpenCode's offline path** on the existing Ollama + Qwen2.5-Coder stack; confirm zero-key operation and set `num_ctx` ≈ 16–32k. Pin a specific OpenCode version.
2. **Trial OpenCode as the daily local agent** for a week against current twin/Aider usage; compare editing quality and tool-loop reliability on Qwen2.5-Coder.
3. **Prototype Path B:** wrap twin's differentiated tools (`repo_search`/RAG, `gh` search, self-improve, mode/5-Whys context) as an MCP server and consume from OpenCode. This is the route that closes twin's MCP gap without a Python rewrite.
4. **Do not adopt** `Gitlawb/openclaude` (licence integrity) or `nexu-io/open-design` (wrong category, offline breach).
5. **Park for later:** if a Rust + offline + RAG assistant is ever genuinely wanted, evaluate `opencrust-org/opencrust` on its own merits — not as "OpenClaude".

---

## Sources & verification notes

Primary sources used (verified): GitHub API (`stars`, `language`, `spdx_id`, `archived`, releases), raw `LICENSE` files, and official docs/sites.

- OpenClaude: `github.com/Gitlawb/openclaude` (+ its `LICENSE`), `openclaudia.com`, `github.com/OpenClaudia/openclaude` (404), `crates.io` (no `openclaude` crate), `github.com/opencrust-org/opencrust`.
- OpenCode: `opencode.ai` (+ `/docs/providers`, `/docs/mcp-servers`), `github.com/anomalyco/opencode` (+ `LICENSE`), `github.com/sst/opencode` (redirect), `github.com/opencode-ai/opencode` (archived Go), `github.com/charmbracelet/crush`.
- Open Design: `github.com/nexu-io/open-design` (+ `LICENSE`, releases), `open-design.ai`, `anthropic.com/news/claude-design-anthropic-labs`.

Residual uncertainties (do not change any verdict): OpenCode's documented-vs-actual zero-key offline path; vendor-reported popularity figures (OpenCode "7.5M monthly developers", Open Design self-reported skill/system counts) are not independently audited; Open Design's steep star/age curve; some GitHub code-search figures required authentication and were confirmed indirectly via README reads.
