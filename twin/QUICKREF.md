# Twin - Quick Reference

## How Twin Connects to Digital Twin OS

**Twin** = Local LLM CLI that USES the Digital Twin Operating System

```
                   ┌──────────────────────────────────┐
                   │ Digital Twin Operating System    │
                   │  (Way of Thinking)               │
                   │                                  │
                   │  ~/.claude/                      │
                   │  ├── CLAUDE.md (orchestrator)    │
                   │  ├── mode-config.json           │
                   │  ├── agents/ (12 specialists)    │
                   │  └── learnings/ (feedback loop)  │
                   └──────────────────────────────────┘
                               ↑           ↑
                               │           │
                    Reads same config     Reads same config
                               │           │
              ┌────────────────┴───┐   ┌──┴──────────────┐
              │  Claude Code       │   │  Twin (Local)   │
              │  (Anthropic API)   │   │  (Ollama API)   │
              └────────────────────┘   └─────────────────┘
```

## Starting Twin

```bash
# Basic - uses config default (fast = qwen2.5-coder:7b)
twin

# With model alias
twin --model balanced        # qwen2.5-coder:14b
twin --model quality         # qwen2.5-coder:32b
twin --model reasoning       # deepseek-r1:8b

# With full model name
twin --model qwen2.5-coder:32b

# Force specific mode
twin --mode work

# Specific agent
twin --agent technical-lead

# Combined
twin --mode work --agent technical-lead --model balanced
```

## Model Aliases (from twin.config.json)

| Alias | Model | Speed | RAM | Use For |
|-------|-------|-------|-----|---------|
| `fast` | qwen2.5-coder:7b | 15-20 tok/s | 8-10GB | Daily coding, quick tasks (DEFAULT) |
| `balanced` | qwen2.5-coder:14b | 8-12 tok/s | 15-18GB | Complex code, better quality |
| `quality` | qwen2.5-coder:32b | 4-6 tok/s | 25-28GB | Critical architecture decisions |
| `reasoning` | deepseek-r1:8b | 10-15 tok/s | 10-12GB | Finance, planning, 5 Whys depth |

## In-Session Commands

```bash
/help               # Show all commands
/mode work          # Switch to work mode
/mode personal      # Switch to personal mode
/agent <name>       # Switch agent (technical-lead, travel-agent, etc.)
/model <alias>      # Switch model WITHOUT restarting
/model              # Show available models and current
/context            # Show context summary
/save               # Manually save checkpoint
/edit               # Transition to Aider for implementation
/bye                # Save and exit
```

## Mid-Session Model Switching

```bash
>>> /model
Model Aliases:
  fast         → qwen2.5-coder:7b           Fast responses, great for most coding
  balanced     → qwen2.5-coder:14b          Balanced quality and speed
  quality      → qwen2.5-coder:32b          Highest quality code generation
  reasoning    → deepseek-r1:8b             Reasoning-focused for planning

Current model: qwen2.5-coder:7b

>>> /model reasoning
✓ Switched to reasoning: Reasoning-focused for planning and decisions
Model: deepseek-r1:8b

>>> Continue planning with better reasoning model...
```

## Agent-Specific Model Auto-Selection

Twin automatically picks the right model for each agent (from twin.config.json):

**Reasoning Agents** (use deepseek-r1:8b):
- decision-framework
- wealth-planner
- startup-accelerator

**Balanced Agents** (use qwen2.5-coder:14b):
- technical-lead
- disaster-recovery-architect

**Fast Agents** (use qwen2.5-coder:7b):
- task-manager
- communication-handler
- learning-manager
- health-coach
- travel-agent
- budget-tracker
- repo-bootstrap-architect

## Configuration Priority

**Model selection order** (highest to lowest):
1. CLI `--model` flag
2. Agent-specific preference (from twin.config.json)
3. Mode default (work=balanced, personal=fast)
4. Global default (fast)

**Example**:
```bash
# Uses balanced (agent preference overrides mode default)
twin --agent technical-lead --mode personal

# Uses quality (CLI overrides everything)
twin --agent technical-lead --mode personal --model quality
```

## Model Validation

Twin validates models exist before starting:

```bash
$ twin --model nonexistent:model
⚠️  Model 'nonexistent:model' not found in Ollama
Available models:
  - qwen2.5-coder:7b
  - qwen2.5-coder:14b
  - qwen2.5-coder:32b
  - deepseek-r1:8b
  - nomic-embed-text:latest

✓ Falling back to 'fast' (qwen2.5-coder:7b)
```

## Context Integration

Twin saves sessions to same context files as Claude:

```
~/.claude/context/context-{hash}.txt

## 2025-11-09 00:15 - Twin Session [TWIN] [PERSONAL MODE]

### Planning Discussion
- Topic: RAG implementation for Phase 4
- Agent: decision-framework
- Model: deepseek-r1:8b (reasoning)

### Decisions Made
[...]
```

**Tagged with [TWIN]** so learning-manager knows source during pattern extraction.

## When to Use Twin vs Claude

**Use Twin** (local):
- ✅ Sensitive code/data (never leaves your machine)
- ✅ Offline/travel (no internet needed)
- ✅ Planning sessions (good for structured thinking)
- ✅ Finance/tax work (privacy critical)
- ✅ Learning experiments (free, unlimited)

**Use Claude** (API):
- ✅ Complex multi-file edits (better tool use)
- ✅ Latest model capabilities (Opus 4, Sonnet 4.5)
- ✅ When quality > privacy/cost
- ✅ Production work (proven reliability)

**Use Aider** (local implementation):
- ✅ Automated file editing
- ✅ After planning in Twin
- ✅ Simple refactors
- ✅ Multi-file changes

## Confidence: 99.5%

Twin now has:
- ✅ Model aliases with validation
- ✅ Mid-session model switching
- ✅ Agent-specific model preferences
- ✅ Fallback to "fast" if model missing
- ✅ CLI args override config
- ✅ Same Digital Twin OS as Claude
