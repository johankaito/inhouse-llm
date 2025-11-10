# twin - Digital Twin Local LLM Wrapper

> Replicates Claude Code planning experience with local LLMs (Ollama)

## Overview

`twin` is a unified CLI tool that brings your Claude Code configuration (agents, modes, context tracking, 5 Whys protocol) to local LLM planning sessions using Ollama.

**Key Features:**
- 🤖 **Agent System** - Loads specialized agents from `~/.claude/agents/`
- 🏢/🏠 **Mode Detection** - Auto-detects work vs personal context
- 📂 **Context Tracking** - Saves session history to `~/.claude/context/`
- 🧠 **5 Whys Protocol** - Structured reasoning for decisions
- 🔄 **Aider Integration** - Seamless planning → implementation workflow
- 📚 **Learning Integration** - Sessions contribute to Digital Twin learning loop

## Installation

Already installed! Twin is located at:
```
~/.llm-planner/bin/twin → ~/.local/bin/twin
```

**Dependencies:**
- Python 3.10+
- Ollama (with models installed)
- click, rich, pyyaml (already installed)

## Quick Start

```bash
# Basic usage - auto-detects everything
twin

# Force specific mode
twin --mode work

# Start with specific agent
twin --agent technical-lead

# Use different model
twin --model qwen2.5-coder:32b
```

## Usage Examples

### Planning Session

```bash
$ cd ~/my-project
$ twin

🧠 Digital Twin - Local Planning Mode
📍 Mode: PERSONAL (detected from directory)
🤖 Agent: decision-framework
📂 Context: Found 2 previous sessions

>>> Help me plan the RAG implementation for Phase 4
... I want to use vector embeddings for semantic search
... and need to handle 100k+ documents
... (Press Ctrl+D to submit)

[Agent provides structured planning with 5 Whys]

>>> What about scalability concerns?

[Continues discussion]

>>> /save
✓ Session saved

>>> /bye
💾 Session saved. Goodbye!
```

### With Agent Selection

```bash
$ twin --agent travel-agent --mode personal

>>> Plan a 2-week trip to Japan in spring

[travel-agent persona active]
```

### Transition to Implementation

```bash
>>> /edit
💾 Saved planning summary
🔧 Launching Aider with context...

Which files do you want to edit? src/rag/indexer.py src/rag/query.py

[Aider opens with planning context loaded]
```

## In-Session Commands

- `/help` - Show help message
- `/mode work|personal` - Switch modes
- `/agent <name>` - Switch agent
- `/model <alias>` - Switch model (fast/balanced/quality/reasoning)
- `/context` - Show context summary
- `/save` - Manually save checkpoint
- `/edit` - Transition to Aider
- `/reload` - Reload twin modules after code changes
- `/bye` - Save and exit

**Input Tips:**
- **Multiline by default:** Press Enter to add new lines as you type
- **Ctrl+D** - Submit your message (universal end-of-input signal)
- `/multiline` - Alternative numbered-line mode (press Enter twice to submit)
  _(Note: Shift+Enter and Option+Enter not reliably supported across terminals)_

## Configuration

Twin reads your existing `~/.claude/` configuration:

- **CLAUDE.md** - Master orchestrator, user profile
- **settings.json** - Permissions, model preferences
- **mode-config.json** - Mode detection rules
- **agents/** - Agent definitions
- **context/** - Session history

No additional configuration needed!

## Mode Detection

Twin uses the same priority ladder as Claude Code:

1. Manual override (`--mode` flag)
2. Per-repo lock (`.claude/settings.local.json`)
3. Directory patterns (work vs personal paths)
4. Git email (work vs personal)
5. Time-based (Mon-Fri 9am-6pm)
6. Default (Personal)

## Agent System

Twin automatically loads agents from `~/.claude/agents/`:

**Work Mode Priority:**
- technical-lead, task-manager, decision-framework

**Personal Mode Priority:**
- travel-agent, health-coach, wealth-planner, decision-framework

Agents activate based on keywords in your input.

## Context Tracking

Session summaries are saved to `~/.claude/context/context-{hash}.txt`:

- Filename hashed from current directory (SHA256[:8])
- Same format as Claude Code context files
- Tagged with `[TWIN]` for source tracking
- Compatible with Claude learning system
- Auto-loaded on next session in same directory

## 5 Whys Protocol

Twin enforces structured reasoning:

**5 Whys for:**
- Architecture decisions (work mode)
- Technology choices
- Major life decisions (personal mode)
- Financial decisions >$1K

**3 Whys for:**
- Tool usage, code reviews
- Health/fitness strategy
- Travel planning

## Aider Integration

The `/edit` command transitions from planning to implementation:

1. Saves planning summary to temp file
2. Asks which files to edit
3. Launches Aider with planning context
4. Returns to twin after Aider exits

## Learning Integration

Twin sessions contribute to your Digital Twin learning loop:

- Context files saved to `~/.claude/context/`
- Tagged with `[TWIN]` vs `[CLAUDE]`
- Monthly learning extraction includes twin sessions
- Patterns feed back into agent definitions

## File Structure

```
~/.llm-planner/
├── bin/
│   └── twin                 # Main executable
├── lib/
│   ├── config.py            # Configuration loader
│   ├── modes.py             # Mode detection
│   ├── agents.py            # Agent loader
│   ├── context.py           # Context manager
│   └── session.py           # Session orchestrator
├── requirements.txt
└── README.md
```

## Troubleshooting

**"Module not found" error:**
```bash
# Check Python path
python3 -c "import sys; print(sys.path)"

# Reinstall dependencies
pip3 install --user --break-system-packages -r ~/.llm-planner/requirements.txt
```

**Ollama connection issues:**
```bash
# Check Ollama is running
brew services list | grep ollama

# Start if needed
brew services start ollama

# Verify models
ollama list
```

**Agent not found:**
```bash
# Check agents directory
ls ~/.claude/agents/

# Verify agent has MASTER_AGENT.md or CLAUDE.md
ls ~/.claude/agents/technical-lead/
```

## Development

**Debug mode:**
```bash
DEBUG=1 twin
```

**Test configuration loading:**
```python
from config import ConfigLoader
loader = ConfigLoader()
config = loader.load_all()
print(config)
```

## Next Steps

1. **Test with real planning sessions**
2. **Validate context file format** with Claude learning
3. **Iterate based on usage patterns**
4. **Add to dotfiles** for cross-machine sync

## Credits

Part of the Digital Twin Operating System project.

Built with: click, rich, pyyaml, Ollama
