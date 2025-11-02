# Quick Start Guide - Phase 1 Complete! ✅

## 🎉 Installation Summary

Everything is now installed and configured on your M1 Max MacBook!

### ✅ What's Installed:

1. **Ollama** (v0.12.9) - Running as background service
2. **Qwen2.5 Coder 7B** (4.7 GB) - Fast, primary coding model
3. **Qwen2.5 Coder 14B** (9.0 GB) - Higher quality model
4. **nomic-embed-text** (274 MB) - For RAG/document search
5. **Aider** (v0.86.1) - Terminal AI pair programmer

**Total Time:** ~20 minutes
**Total Download:** ~14 GB

---

## 🚀 How to Use Aider (Your New Terminal AI Assistant)

### Basic Usage:

Open iTerm and run:

```bash
# Navigate to your project
cd ~/your-project

# Start Aider with files you want to edit
aider src/main.py src/utils.py

# Or start without files (add them later)
aider
```

### Inside Aider:

```bash
# Add a file to context
> /add myfile.py

# Ask Aider to make changes (it edits files automatically!)
> Add error handling to the calculate_sum function

> Refactor this code to use async/await

> Add unit tests for the new function

> Fix the bug where null values crash the parser

# Review changes before applying
> /diff

# Commit changes with AI-generated message
> /commit

# Drop a file from context
> /drop myfile.py

# Get help
> /help

# Exit
> /exit
```

---

## 💬 Testing Basic Chat with Ollama

```bash
# Chat directly with the model (no file editing)
ollama run qwen2.5-coder:7b

# Try asking:
>>> Write a Python function to validate email addresses

>>> How do I implement a binary search tree in TypeScript?

>>> Explain this code: [paste code]

# Exit chat
>>> /bye
```

---

## 🖥️ Recommended iTerm Workflow

### Option 1: Split Panes (Simple)

1. Open iTerm
2. Split vertically: `Cmd+D`
3. Left pane: Vim for editing
4. Right pane: Aider for AI assistance

```
┌────────────────┬───────────────┐
│                │               │
│   Vim          │   Aider       │
│   (editing)    │   (AI assist) │
│                │               │
└────────────────┴───────────────┘
```

### Option 2: tmux (Advanced)

```bash
# Create coding session
tmux new-session -s coding

# Split horizontally
tmux split-window -h

# Left: Vim, Right: Aider
# Switch panes: Ctrl+b then arrow keys
```

---

## 🧪 Quick Test

Let's test the installation:

```bash
# Navigate to the test project
cd /Users/john.keto/gits/src/github.com/johankaito/inhouse-llm

# Start Aider with the test file
aider test_example.py

# Try this command:
> Add type hints and docstrings to all functions

# Watch Aider automatically edit the file!
# Then check the file in Vim to see the changes
```

---

## 📊 Expected Performance (M1 Max 32GB)

| Model | Speed | RAM Usage | Best For |
|-------|-------|-----------|----------|
| 7B | 15-20 tokens/sec | ~8-10GB | Daily coding, fast responses |
| 14B | 8-12 tokens/sec | ~15-18GB | Higher quality, complex tasks |

**Recommendation:** Start with 7B model. It's fast and handles most tasks well. Use 14B when you need better quality.

---

## 🔧 Configuration

Aider is configured to use **ollama/qwen2.5-coder:7b** by default (set in `~/.zshrc`).

### To use 14B model instead:

```bash
# Temporarily for one session
aider --model ollama/qwen2.5-coder:14b

# Or change default in ~/.zshrc
export AIDER_MODEL=ollama/qwen2.5-coder:14b
```

### To use different models:

```bash
# List available models
ollama list

# Use any model
aider --model ollama/qwen2.5-coder:7b
```

---

## ⚙️ Key Aider Commands

```bash
/add <file>      # Add file to context
/drop <file>     # Remove file from context
/diff            # Show uncommitted changes
/commit          # Commit with AI message
/undo            # Undo last change
/clear           # Clear chat history
/reset           # Reset conversation
/help            # Show all commands
/exit            # Quit Aider
```

---

## 🎯 Example Workflows

### Workflow 1: Add Feature

```bash
aider src/api.py

> Add a new endpoint /users/{id}/profile that returns user profile data
> Add error handling for when user is not found
> Add input validation for the id parameter
> /diff
> /commit
```

### Workflow 2: Refactor

```bash
aider src/legacy_code.py

> Refactor this code to use modern Python best practices
> Add type hints
> Split long functions into smaller ones
> /diff
```

### Workflow 3: Debug

```bash
aider src/buggy.py

> This function crashes when input is empty. Fix it.
> Add defensive checks for edge cases
> Add unit tests to prevent regression
```

### Workflow 4: Documentation

```bash
aider src/utils.py

> Add comprehensive docstrings to all functions
> Add usage examples in docstrings
> Add type hints
```

---

## 🔍 Troubleshooting

### Aider says "Can't connect to Ollama"

```bash
# Check if Ollama is running
brew services list | grep ollama

# If not running, start it
brew services start ollama

# Verify models are available
ollama list
```

### Model responses are slow

- **Solution 1:** Use 7B model instead of 14B
- **Solution 2:** Close other apps to free RAM
- **Solution 3:** Ensure MacBook is plugged in (better performance)

### Files not auto-reloading in Vim

Add to `~/.vimrc`:

```vim
set autoread
au CursorHold,CursorHoldI * checktime
```

---

## 📈 Next Steps

✅ **Phase 1 Complete!** You now have:
- Local LLM running on M1 Max
- Automated file editing with Aider
- Offline coding capability
- Privacy (all local processing)

**What to do now:**

1. **Test the workflow** - Try editing some real project files
2. **Evaluate performance** - Is 7B sufficient or do you need 14B?
3. **Monitor RAM usage** - Check if 32GB is enough
4. **Battery test** - See how long it lasts during coding session
5. **Decide on server** - Do you need the Linux server or is M1 Max good enough?

**Track your experience:**
- Quality of responses compared to Claude
- Speed of generation
- RAM/battery impact
- Workflow friction points

---

## 🎊 Congratulations!

You now have a **Claude Code equivalent running 100% locally** on your MacBook!

- **No internet required** (works offline)
- **No API costs** (just electricity)
- **Full privacy** (code never leaves your machine)
- **Automated file editing** (like Claude Code)

**Total Setup Time:** ~20 minutes
**Total Cost:** $0
**Ongoing Cost:** ~$0.05/month electricity (50W)

---

## 📚 Resources

- [Aider Documentation](https://aider.chat/docs/)
- [Ollama Models](https://ollama.ai/library)
- [Qwen2.5 Coder Info](https://huggingface.co/Qwen/Qwen2.5-Coder-7B)

---

**Ready to code! 🚀**
