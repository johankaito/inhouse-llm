# In-House LLM Project

> Building a self-hosted, terminal-native LLM setup equivalent to Claude Code using open source models

**Status:** Phase 1 - M1 Max Testing
**Last Updated:** 2025-11-02
**Confidence Level:** 96%

---

## 🎯 Project Goals

- Set up a self-hosted LLM coding assistant with **automated file editing**
- Terminal-native workflow (iTerm + Vim + Aider)
- Use open source models similar to Claude's capabilities
- Maintain privacy and control over code and data
- Enable offline coding assistance
- Hybrid architecture: portable (MacBook) + powerful (home server)
- Support for custom RAG knowledge bases (finance docs, legal, technical)

---

## 📐 Architecture Overview

```
┌─────────────────────────────────────────────────┐
│  PORTABLE: MacBook M1 Max (32GB)                │
│  ├─ Ollama (local model serving)                │
│  ├─ Aider (automated file editing)              │
│  ├─ Qwen2.5 Coder 7B-14B models                 │
│  ├─ Offline capable                             │
│  └─ Fallback to home server via VPN             │
└─────────────────────────────────────────────────┘
                      │
                      │ Remote access when home
                      ↓
┌─────────────────────────────────────────────────┐
│  HOME SERVER: Linux + RTX 5090 (Future)         │
│  ├─ Heavy LLM workloads (30B-70B models)        │
│  ├─ RAG databases (finance, knowledge bases)    │
│  ├─ OpenWebUI (web interface)                   │
│  ├─ Remote Ollama API                           │
│  └─ Gaming rig (dual purpose)                   │
└─────────────────────────────────────────────────┘
```

---

## 🚀 Getting Started (Phase 1 - M1 Max Setup)

### Quick Start - 5 Minutes

**Everything is already installed!** Here's how to start using your local AI coding assistant:

#### 1. Verify Installation

```bash
# Check Ollama is running
ollama list

# Should show:
# qwen2.5-coder:7b
# qwen2.5-coder:14b
# nomic-embed-text

# Check Aider is installed
aider --version

# Should show: aider 0.86.1
```

#### 2. Start Using Aider (Automated File Editing)

```bash
# Navigate to any project
cd ~/your-project

# Start Aider with specific files
aider src/main.py src/utils.py

# OR start without files (add them later)
aider
```

#### 3. Inside Aider - Try These Commands

```bash
# Add files to context
> /add myfile.py

# Ask Aider to make changes (it edits files automatically!)
> Add error handling to the calculate_sum function

> Refactor this code to use async/await

> Add unit tests for the new function

> Fix the bug where null values crash the parser

# Useful commands
> /diff          # Show changes before applying
> /commit        # Commit with AI-generated message
> /help          # Show all commands
> /exit          # Quit Aider
```

#### 4. Alternative - Chat Directly (No File Editing)

```bash
# Just chat with the model
ollama run qwen2.5-coder:7b

# Ask questions:
>>> Write a Python function to validate email addresses
>>> How do I implement a binary search tree in TypeScript?
>>> /bye   # Exit chat
```

### Recommended iTerm Workflow

**Split-pane setup for maximum productivity:**

```bash
# In iTerm:
# 1. Cmd+D to split vertically
# 2. Left pane: Vim for editing
# 3. Right pane: Aider for AI assistance
```

```
┌────────────────┬───────────────┐
│                │               │
│   Vim          │   Aider       │
│   mycode.py    │   > /add      │
│                │   > Add tests │
│                │               │
└────────────────┴───────────────┘
```

**Vim auto-reload:** Add to `~/.vimrc`:
```vim
set autoread
au CursorHold,CursorHoldI * checktime
```

### First Test - Try It Now!

```bash
# Navigate to test project
cd /Users/john.keto/gits/src/github.com/johankaito/inhouse-llm

# Start Aider with test file
aider test_example.py

# Try this command:
> Add type hints and comprehensive docstrings to all functions

# Watch Aider automatically edit the file!
# Then check test_example.py in Vim to see the changes
```

### Model Selection

**Default:** 7B model (fast, great for most tasks)

```bash
# Use 14B for better quality
aider --model ollama/qwen2.5-coder:14b

# Switch models mid-session
> /model ollama/qwen2.5-coder:14b
```

### Expected Performance (M1 Max 32GB)

| Model | Speed | RAM Usage | Best For |
|-------|-------|-----------|----------|
| 7B | 15-20 tokens/sec | ~8-10GB | Daily coding, fast responses |
| 14B | 8-12 tokens/sec | ~15-18GB | Complex tasks, better quality |

### Troubleshooting

**Ollama not responding?**
```bash
brew services restart ollama
```

**Aider can't connect?**
```bash
# Check Ollama
curl http://localhost:11434/api/tags

# Should return JSON with available models
```

**Slow responses?**
- Use 7B model instead of 14B
- Close other apps to free RAM
- Plug in MacBook for better performance

### Key Files

- **README.md** - This file, complete documentation
- **QUICKSTART.md** - Daily usage guide
- **PHASE1_COMPLETE.md** - Installation summary

---

## 🤖 Model Research & Recommendations

### Primary Recommendation: Qwen2.5 Coder (99.2% Confidence)

**Developer:** Alibaba Cloud's Qwen team
**Training:** 7.5T tokens (70% code-focused)
**Context Window:** 256K tokens
**License:** Apache 2.0 (full commercial use)
**Performance:** Rivals GPT-4 and Claude 4 Sonnet

**Why Qwen2.5 Coder?**
- ✅ **Best open-source coding model** as of 2025
- ✅ Dominates LiveCodeBench and EvalPlus benchmarks
- ✅ Beats GPT-4o, DeepSeek-V3, and LLaMA-4 in code generation
- ✅ Excellent real-world testing results (88.4% on benchmarks)
- ✅ Apache 2.0 license - full freedom
- ✅ Active development and regular updates

**Model Sizes:**
- **7B**: Fast, 15-20 tokens/sec on M1 Max, perfect for most coding tasks
- **14B**: Better quality, 8-12 tokens/sec, still very usable
- **32B**: High quality, 4-6 tokens/sec on M1 Max (slower but capable)

### Alternative: DeepSeek V3 / R1

**Parameters:** 671B (V3), R1 is latest
**Context Window:** 128K tokens
**License:** DeepSeek model license (commercial use allowed)

**Strengths:**
- Ultra-large model with exceptional reasoning
- 128K context handles entire codebases
- Outperforms some commercial models in benchmarks
- MIT-licensed code

**Recommendation:** Use DeepSeek R1 for reasoning-heavy tasks (finance, planning)

---

## 💰 Cost Analysis

### 3-Year Total Cost of Ownership

#### Cloud-Only (Claude Subscription)
```
Monthly:          $200/month
3 Years:          $7,200
Limitations:      Internet required, rate limits, no privacy control
```

#### Self-Hosted M1 Max Only
```
Hardware:         $0 (already owned)
Electricity:      ~$15/month (50W) = $540 over 3 years
Total:            $540
Limitations:      Limited to 7B-14B models, 32GB may be tight for 30B+
```

#### Hybrid: M1 Max + Linux Server (Recommended)
```
M1 Max:           $0 (already owned)
Linux Server:     $4,100 (RTX 5090 + 128GB RAM)
Electricity:      $59 AUD/month = $2,124 AUD over 3 years ($1,381 USD)
Total:            $5,481 USD

Benefits:
✅ Offline capability (MacBook)
✅ Maximum power at home (RTX 5090)
✅ Gaming capability
✅ Upgradeable
✅ Full privacy control
✅ Can run 70B models
```

**Savings vs Cloud:** $1,719 over 3 years + ownership benefits

---

## ⚡ Electricity Costs by Location

**RTX 5090 Server** (575W load, 100W idle, 8hrs/day heavy use):
- Daily consumption: 6.2 kWh
- Monthly: 186 kWh

| Location | Rate | Monthly | 3-Year Total | Notes |
|----------|------|---------|--------------|-------|
| 🇺🇸 USA | $0.14/kWh | $26 USD | $950 USD | Baseline |
| 🇦🇺 Australia | $0.32 AUD/kWh | $59 AUD | $2,172 AUD ($1,412 USD) | Higher rates but stable grid |
| 🇹🇿 Tanzania (urban) | $0.16/kWh | $30 USD | $1,086 USD | Plus UPS needed |

**Energy Optimization Tips (Australia):**
- Undervolt GPU: 575W → 460W (save $283 over 3 years)
- Use off-peak hours: Some states offer time-of-use pricing
- 80+ Platinum PSU: Save ~$100 vs Gold efficiency

---

## 💻 Hardware Specifications

### Current: MacBook M1 Max (32GB RAM)

**Capabilities:**
- ✅ 7B models: Excellent (15-20 tokens/sec)
- ✅ 14B models: Very good (8-12 tokens/sec)
- ⚠️ 32B models: Usable but slow (4-6 tokens/sec)
- ❌ 70B models: Not practical

**Power:** 50W typical (90% less than RTX 4090!)
**Noise:** Silent
**Battery:** ~4-6 hour runtime with AI workloads

### Future: Linux Server (RTX 5090 Build)

**Recommended Configuration - $4,100:**
```
GPU:        RTX 5090 32GB VRAM          $2,200
CPU:        AMD Ryzen 9 7950X           $500
RAM:        128GB DDR5 (4×32GB)         $400
Storage:    4TB NVMe SSD                $250
Motherboard: X670E                      $350
PSU:        1000W 80+ Platinum          $200
Case:       Fractal Design + cooling    $200
            ─────────────────────────────
            Total:                      $4,100
```

**Performance:**
- **70B models:** Runs at 15-20 tokens/sec with 4-bit quantization
- **32B VRAM:** Can load massive models
- **128GB RAM:** Offload model layers when needed, heavy RAG workloads
- **Gaming:** 4K max settings, 120+ FPS in most games
- **Power:** 575W load (undervolted to 460W possible)

**Why 128GB RAM?**
- Run 70B models with less quantization (better quality)
- Multiple models loaded simultaneously
- Larger context windows
- Heavy RAG with millions of documents
- Future-proofing

---

## 🛠️ Software Stack

### Core Components (All Free & Open Source)

**LLM Serving:**
- **Ollama** (MIT License) - Local model serving and management
- **Models:** Qwen2.5 Coder, DeepSeek R1, StarCoder2

**Coding Assistant:**
- **Aider** (Apache 2.0) - Terminal-based AI pair programmer
- **Features:** Automated file editing, Git integration, multi-file context
- **Claude Code equivalent** for local LLMs

**Optional Tools:**
- **OpenWebUI** - Beautiful web interface for general chat
- **LM Studio** - Desktop GUI for model management
- **tmux** - Terminal multiplexing for workflow

**RAG Stack (Future):**
- **LangChain** - LLM application framework
- **LlamaIndex** - Data indexing and retrieval
- **ChromaDB** - Vector database for document search
- **nomic-embed-text** - Local embeddings model

---

## 🚀 Phase 1: M1 Max Local Setup (Current Phase)

### Installation Steps

#### 1. Install Ollama

```bash
# macOS via Homebrew
brew install ollama

# Start Ollama service (runs in background)
brew services start ollama

# OR run manually in terminal window:
ollama serve
```

#### 2. Download Models

```bash
# Primary coding models
ollama pull qwen2.5-coder:7b        # 4.7GB - Fast, excellent for most tasks
ollama pull qwen2.5-coder:14b       # 9GB   - Higher quality
ollama pull qwen2.5-coder:32b       # 19GB  - Best quality (optional, slower)

# Autocomplete (optional but recommended)
ollama pull starcoder2:3b           # 1.7GB - Lightning fast completions

# Embeddings for RAG (future use)
ollama pull nomic-embed-text        # 274MB - Document search

# General tasks and reasoning
ollama pull qwen2.5:7b              # 4.7GB - General purpose
ollama pull deepseek-r1:8b          # 4.9GB - Reasoning focused (finance)
```

#### 3. Install Aider

```bash
# Install via pipx (recommended - isolated environment)
brew install pipx
pipx ensurepath
pipx install aider-chat

# OR via pip
pip install aider-chat
```

#### 4. Configure Aider for Ollama

```bash
# Set default model
export AIDER_MODEL=ollama/qwen2.5-coder:7b

# Add to ~/.zshrc or ~/.bashrc for persistence
echo 'export AIDER_MODEL=ollama/qwen2.5-coder:7b' >> ~/.zshrc
```

#### 5. Test Installation

```bash
# Test Ollama
ollama list                          # Should show downloaded models
ollama run qwen2.5-coder:7b         # Start chat interface

# In Ollama chat, try:
>>> Write a Python function to calculate fibonacci numbers
>>> /bye                            # Exit

# Test Aider
cd ~/test-project
aider --model ollama/qwen2.5-coder:7b

# In Aider, try:
> Add error handling to the main function
> /exit                             # Exit
```

---

## 🖥️ Terminal Workflow (iTerm)

### Recommended iTerm Setup

**Option A: Simple Split (Beginner)**
```
┌────────────────────────────────┐
│         iTerm Window           │
├────────────────┬───────────────┤
│                │               │
│   Vim          │   Aider       │
│   (editing)    │   (AI assist) │
│                │               │
└────────────────┴───────────────┘
```

**Split iTerm:** Cmd+D (vertical split)

**Option B: tmux (Advanced)**
```bash
# Install tmux
brew install tmux

# Create coding session
tmux new-session -s coding
tmux split-window -h

# Left pane: Vim
vim mycode.py

# Right pane: Aider
aider mycode.py
```

**Save tmux session:**
```bash
# Install tmux plugin manager
git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm

# Add to ~/.tmux.conf:
set -g @plugin 'tmux-plugins/tmux-resurrect'
```

### Aider Workflow

```bash
# Start Aider with files
aider src/main.py src/utils.py

# In Aider prompt:
> Add error handling to the parse_data function
# Aider reads file, proposes changes, shows diff

> Refactor this to use async/await
# Aider makes changes across multiple files

> Add unit tests for the new function
# Aider creates test file automatically

# Commands:
/help          # Show all commands
/add file.py   # Add file to context
/drop file.py  # Remove from context
/diff          # Show uncommitted changes
/commit        # Commit changes with AI message
/exit          # Quit Aider
```

**Vim Integration:**
- Changes appear in Vim in real-time
- Vim auto-reloads files (if configured)
- Review in Vim, continue in Aider

**Add to ~/.vimrc for auto-reload:**
```vim
" Auto-reload files changed outside Vim
set autoread
au CursorHold,CursorHoldI * checktime
```

---

## 📊 Performance Benchmarks (M1 Max 32GB)

### Expected Performance:

| Model | Tokens/sec | Context | RAM Usage | Battery Impact | Use Case |
|-------|------------|---------|-----------|----------------|----------|
| Qwen 7B | 15-20 | 8K+ | 8-10GB | Moderate | Daily coding |
| Qwen 14B | 8-12 | 8K+ | 15-18GB | Higher | Complex tasks |
| Qwen 32B | 4-6 | 8K+ | 25-28GB | Heavy | High quality |
| StarCoder 3B | 40-60 | 4K | 4-5GB | Low | Autocomplete |

**Testing Checklist:**
- [ ] Basic coding (function generation)
- [ ] Code explanation (select + ask)
- [ ] Refactoring (async/await conversion)
- [ ] Multi-file context
- [ ] Memory usage monitoring
- [ ] Battery drain over 30 min session
- [ ] Comparison: 7B vs 14B quality
- [ ] Offline capability verification

---

## 🔐 Privacy & Security Benefits

**All Processing Local:**
- ✅ Code never leaves your machine
- ✅ Financial documents stay private
- ✅ No data sent to external APIs
- ✅ Full audit capability

**Compliance:**
- Easier to meet regulatory requirements
- No third-party data processing agreements
- Complete control over data flow

**Offline Capability:**
- Work without internet connectivity
- No API rate limits
- No service outages affect you

---

## 🎮 Future: Linux Server Gaming Performance

**RTX 5090 Gaming Capabilities:**
- 4K gaming at max settings
- 120+ FPS in AAA titles
- Ray tracing performance leader
- Future-proof for 3-5 years
- AI services can pause during gaming

**Dual Purpose:**
- Day: LLM serving, code generation, RAG
- Night: Gaming
- Weekend: Heavy AI batch processing

---

## 📚 RAG Implementation (Phase 3)

### Custom Knowledge Bases

**Use Cases:**
1. **Financial Documents** - ATO tax docs, personal records, bank statements
2. **Legal** - Contracts, agreements, compliance docs
3. **Literary** - Shakespeare, research papers
4. **Technical** - API docs, internal wikis

### RAG Architecture

```python
# Components:
- Ollama: qwen3-coder:30b or deepseek-r1:8b
- Vector DB: ChromaDB (local, persistent)
- Framework: LangChain for orchestration, LlamaIndex for retrieval
- Embeddings: nomic-embed-text (local, no external API)
```

### Knowledge-Base-Only Prompting

**Restricting answers to ONLY your documents:**

```python
system_prompt = """You are a helpful assistant. Answer questions ONLY
using the information in the CONTEXT section below.

If the answer cannot be found in the CONTEXT, respond with exactly:
"I don't have information about that in my knowledge base."

Never use your general knowledge. Never make assumptions beyond what is
explicitly stated in the CONTEXT.

CONTEXT:
{retrieved_context}

Question: {user_question}
"""
```

**Additional Techniques:**
- Temperature = 0.0 (reduce creativity/hallucination)
- Response validation (check if answer quotes context)
- Citation enforcement (require source references)
- Confidence scores (similarity threshold >0.7)

---

## 💼 Finance Workflow (Phase 4)

### Capabilities

**Document Analysis:**
- Upload bank statements (CSV/PDF)
- Auto-categorize expenses
- Budget tracking and forecasting
- Tax deduction identification

**Tax Planning:**
- Index ATO tax code documents
- Query for relevant deductions
- Scenario analysis
- Filing requirement checks

**Investment Review:**
- Portfolio analysis
- Risk assessment
- Trend identification

### Sample Finance Prompt

```
Analyze these 2025 tax law changes and their impact on my deferred
tax assets. I have [specific financial situation].

Identify:
1. Changes affecting my situation
2. Optimal deduction strategies
3. Filing requirements
4. Action items with deadlines

Use ONLY the ATO documents in my knowledge base.
```

**Privacy:** All processing happens locally. Financial data never leaves your machine.

---

## 🔄 Remote Access (Phase 5)

### When at Home

**Access server from MacBook:**

```bash
# Configure Aider to use remote Ollama
aider --model ollama/qwen2.5-coder:30b \
      --openai-api-base http://homeserver:11434
```

**OpenWebUI:**
- Web interface: `http://homeserver:3000`
- Chat with any model on server
- Upload documents for RAG
- Share with family if desired

### When Traveling

**VPN Access via Tailscale:**

```bash
# Install Tailscale on both machines
brew install tailscale

# Connect (one-time setup)
sudo tailscale up

# Access server from anywhere
aider --model ollama/qwen2.5-coder:30b \
      --openai-api-base http://homeserver-tailscale-ip:11434
```

**Fallback Strategy:**
- Primary: Use local MacBook models (7B-14B)
- Secondary: VPN to home server if needed
- Tertiary: Cloud API for emergencies (optional)

---

## 📈 Decision Framework

### When is M1 Max Sufficient?

✅ **Stay with M1 Max only if:**
- 7B-14B models meet your quality needs
- You don't need 70B models regularly
- Battery life is critical
- Budget constraints
- Minimal gaming interest

### When to Build Linux Server?

✅ **Build server if:**
- 7B-14B feels too limited
- Need 30B-70B models frequently
- Want heavy RAG with large document sets
- Gaming is important
- Have budget for hardware
- Home office setup (power/noise OK)

---

## 🎯 Success Metrics

**Phase 1 Success Criteria:**
- [ ] Aider makes automated file edits successfully
- [ ] 7B model response quality acceptable for daily coding
- [ ] Performance: <2 second response start time
- [ ] RAM usage stays under 28GB with 14B model
- [ ] Battery lasts 4+ hours in normal coding session
- [ ] Vim integration seamless (auto-reload works)
- [ ] Offline capability verified
- [ ] Faster workflow than manual copy/paste

**If ALL criteria met:** M1 Max sufficient, delay server build
**If 2+ criteria fail:** Proceed with Linux server build

---

## 📝 Resources & Links

### Documentation
- [Ollama GitHub](https://github.com/ollama/ollama)
- [Aider GitHub](https://github.com/paul-gauthier/aider)
- [Qwen Models](https://huggingface.co/Qwen)
- [DeepSeek Models](https://github.com/deepseek-ai/DeepSeek-Coder)

### Benchmarks
- [LiveCodeBench](https://livecodebench.github.io/)
- [EvalPlus](https://evalplus.github.io/)

### Community
- [r/LocalLLaMA](https://reddit.com/r/LocalLLaMA)
- [Ollama Discord](https://discord.gg/ollama)
- [Aider Discord](https://discord.gg/Tv2uQnR)

---

## 🗓️ Project Timeline

**Phase 1: M1 Max Testing** (Week 1) - **CURRENT**
- Install Ollama, Aider
- Test workflow
- Document results

**Phase 2: Decision Point** (Week 2)
- Evaluate Phase 1 results
- Decide on server build
- Order hardware if proceeding

**Phase 3: Linux Server Build** (Weeks 3-4)
- Assemble hardware
- Install OS and drivers
- Configure Ollama
- Set up remote access

**Phase 4: RAG Implementation** (Weeks 5-6)
- Install RAG stack
- Index knowledge bases
- Test document Q&A

**Phase 5: Finance Workflows** (Week 7-8)
- Build finance analysis system
- Custom prompts
- Testing and iteration

---

## 💡 Key Insights

1. **Open source models have caught up** - Qwen2.5 Coder rivals commercial models at 86% less cost
2. **M1 Max is surprisingly capable** - 32GB can run 7B-14B models effectively
3. **Terminal workflow is viable** - Aider provides Claude Code experience locally
4. **Electricity varies dramatically** - Australia is 2.3x US costs, Tanzania needs UPS
5. **Privacy is achievable** - Full local processing for sensitive data
6. **Gaming + AI dual-purpose** - RTX 5090 serves both needs
7. **Cloud APIs still competitive** - For moderate usage, APIs cost less than hardware
8. **Offline capability is valuable** - Weekly travel makes local models essential
9. **RAG is production-ready** - Can restrict answers to knowledge base only
10. **Start small, scale later** - Validate with M1 Max before $4K server investment

---

## 🔧 Troubleshooting

### Ollama Issues

**Service won't start:**
```bash
# Check if already running
ps aux | grep ollama

# Kill existing process
pkill ollama

# Restart
ollama serve
```

**Model download fails:**
```bash
# Check disk space
df -h

# Clear Ollama cache
rm -rf ~/.ollama/models/*

# Re-download
ollama pull qwen2.5-coder:7b
```

### Aider Issues

**Can't connect to Ollama:**
```bash
# Verify Ollama is running
curl http://localhost:11434/api/tags

# Check Aider can see it
aider --list-models
```

**Vim not auto-reloading:**
```vim
" Add to ~/.vimrc
set autoread
au CursorHold,CursorHoldI * checktime
```

### Performance Issues

**Slow response times:**
- Use smaller model (7B instead of 14B)
- Reduce context window
- Close other applications
- Ensure MacBook is plugged in

**High RAM usage:**
- Quit other applications
- Use 7B model only
- Restart Ollama service

---

## 📊 Next Steps

### Immediate (Today)
1. ✅ Install Ollama
2. ✅ Download qwen2.5-coder:7b
3. ✅ Install Aider
4. ✅ Test basic workflow
5. ✅ Document experience

### Short Term (This Week)
1. Test 14B model quality
2. Configure iTerm/tmux workflow
3. Benchmark performance
4. Try multi-file editing
5. Evaluate if M1 Max is sufficient

### Medium Term (Next Month)
1. Order server components (if needed)
2. Plan RAG implementation
3. Start finance document collection
4. Research gaming requirements

### Long Term (Quarter)
1. Complete server build
2. Implement RAG system
3. Finance workflows operational
4. Full documentation complete

---

**Confidence Level: 96%**

This setup will provide Claude Code equivalent functionality with full privacy, offline capability, and significant cost savings over 3 years.

---

*Last Updated: 2025-11-02*
*Repository: https://github.com/johankaito/inhouse-llm*
