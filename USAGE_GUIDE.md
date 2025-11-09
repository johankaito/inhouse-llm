# Usage Guide - When to Use What

## Tool Comparison

| Tool | Use Case | Strengths | Limitations |
|------|----------|-----------|-------------|
| **twin** | Planning, architecture, exploration | • Configuration-driven<br>• Agent system<br>• Mode-aware<br>• Context tracking<br>• 5 Whys protocol<br>• Learning integration | • No file editing<br>• Single conversation thread |
| **Aider** | Implementation, coding | • Automated file editing<br>• Git integration<br>• Multi-file context<br>• Fast iterations | • No agent system<br>• No mode awareness<br>• Manual file selection |
| **Claude Code** | Everything | • Full codebase awareness<br>• Multi-step autonomous<br>• Bash commands<br>• Rich tooling | • Requires internet<br>• API costs<br>• Rate limits |
| **Ollama (direct)** | Quick questions | • Fast<br>• Simple<br>• No overhead | • No context<br>• No file awareness<br>• One-off queries |

---

## Recommended Workflows

### Workflow 1: Planning → Implementation (Recommended)

**Use twin for planning, then Aider for implementation**

```bash
# 1. Planning phase
$ twin

>>> I want to refactor the auth system to use JWT tokens
>>> What's the best approach considering our current architecture?

[twin provides structured planning with 5 Whys]

>>> /edit
💾 Launching Aider...

# 2. Implementation phase
$ Which files? src/auth/jwt.py src/middleware/auth.py

[Aider opens with planning context]

> Implement the JWT auth approach we just planned
```

**Benefits:**
- Structured thinking before coding
- Context preserved across tools
- Learning from planning sessions
- Clean separation of concerns

---

### Workflow 2: Quick Iterations (Aider Only)

**For small, focused changes**

```bash
$ aider src/utils.py

> Add error handling to parse_config function
> Add unit tests for the new error cases
```

**When to use:**
- Small bug fixes
- Adding tests
- Refactoring single files
- Clear implementation path

---

### Workflow 3: Complex Multi-Phase (Claude Code)

**For complex, multi-step work requiring exploration**

Use Claude Code (me) for:
- Understanding large codebases
- Multi-file refactors with exploration
- Debugging complex issues
- System operations (git, docker, deploys)

Then use twin/Aider for offline work on same tasks.

---

### Workflow 4: Offline Development

**When internet unavailable or for sensitive code**

```bash
# Morning: Plan with twin
$ twin --mode work
>>> Plan today's tasks for the auth refactor

# Day: Implement with Aider
$ aider src/auth/*.py

# Evening: Review with twin
$ twin
>>> Review what I implemented today. Any issues?
```

---

## Decision Tree

```
Need to work on code?
│
├─ Have clear implementation plan?
│  ├─ YES → Use Aider
│  └─ NO  → Use twin to plan first
│
├─ Complex multi-step task?
│  ├─ Online  → Use Claude Code
│  └─ Offline → Use twin + Aider
│
├─ Need codebase exploration?
│  ├─ Online  → Use Claude Code
│  └─ Offline → Use twin with context
│
└─ Quick question?
   └─ Use ollama run qwen2.5-coder:7b
```

---

## Example Use Cases

### Case 1: Architecture Decision

**Use:** twin (planning mode)

```bash
$ twin --agent technical-lead

>>> Should we use microservices or monolith for this new feature?

[Agent applies 5 Whys, considers trade-offs]
```

**Why:** Needs structured reasoning, no implementation yet

---

### Case 2: Bug Fix

**Use:** Aider (if simple) or Claude Code (if complex)

```bash
# Simple bug (know the fix)
$ aider src/buggy.py
> Fix null pointer when user is not found

# Complex bug (need investigation)
$ claude code
> This function crashes randomly. Help me find the root cause.
```

---

### Case 3: Feature Implementation

**Use:** twin → Aider workflow

```bash
# 1. Plan with twin
$ twin
>>> I need to add rate limiting to the API
>>> What's the best approach?

# 2. Implement with Aider
>>> /edit
[Aider opens with rate limiting plan]
```

---

### Case 4: Travel Planning (Personal)

**Use:** twin (personal mode)

```bash
$ twin --agent travel-agent

>>> Plan a 2-week trip to Japan in spring
>>> Budget: $5000, interests: food, temples, hiking

[travel-agent persona with personal mode tone]
```

---

### Case 5: Code Review

**Use:** Claude Code (if online) or twin (offline)

```bash
# Online
$ claude code
> Review this PR for security issues and performance

# Offline
$ twin --mode work
>>> /read src/feature.py
>>> Review this implementation for issues
```

---

## Mode-Specific Usage

### Work Mode

**Best tools:**
- twin (technical-lead, task-manager agents)
- Claude Code (full exploration)
- Aider (implementation)

**Characteristics:**
- Professional tone
- Full 5 Whys for technical decisions
- Focus on business value

**Example:**
```bash
$ twin --mode work --agent technical-lead
>>> Architect the new payment gateway integration
```

---

### Personal Mode

**Best tools:**
- twin (travel-agent, health-coach, wealth-planner agents)
- Aider (side projects)
- Ollama (quick personal questions)

**Characteristics:**
- Conversational tone
- Flexible reasoning depth
- Exploratory discussions

**Example:**
```bash
$ twin --mode personal --agent wealth-planner
>>> Help me optimize my 2025 tax strategy
```

---

## Performance Considerations

### Speed

**Fastest → Slowest:**
1. Ollama direct (no context overhead)
2. Aider (focused on files)
3. twin (loads agents + context)
4. Claude Code (full exploration + network)

### Quality

**Best → Good:**
1. Claude Code (largest context, best reasoning)
2. twin with 14B model (structured, agent-based)
3. Aider (focused on code)
4. Ollama direct (no context)

### Privacy

**Most Private → Least:**
1. Ollama direct (fully local)
2. twin (fully local)
3. Aider (fully local)
4. Claude Code (cloud API)

---

## Tips & Best Practices

### Using twin Effectively

1. **Start sessions with context**
   ```bash
   >>> First, read my previous notes in context
   >>> Now help me plan the next phase
   ```

2. **Use agents appropriately**
   ```bash
   >>> /agent technical-lead  # For architecture
   >>> /agent travel-agent    # For trips
   ```

3. **Save important decisions**
   ```bash
   >>> /save  # Creates checkpoint
   ```

4. **Transition to implementation**
   ```bash
   >>> /edit  # When planning is done
   ```

### Using Aider Effectively

1. **Add relevant files only**
   ```bash
   aider src/main.py src/utils.py  # Not entire repo
   ```

2. **Use read-only context**
   ```bash
   aider --read README.md --read ARCHITECTURE.md
   ```

3. **Commit frequently**
   ```bash
   > /commit  # After each logical change
   ```

### Combining Tools

**Pattern: twin → Aider → Claude Code**

```bash
# 1. Plan offline with twin
$ twin
>>> Plan the feature

# 2. Implement offline with Aider
>>> /edit

# 3. Review online with Claude Code
$ claude code
> Review implementation for edge cases
```

---

## Summary

**Use twin when:**
- ✅ Planning and architecture
- ✅ Need agent system (specialized personas)
- ✅ Want context tracking and learning
- ✅ Work/personal mode awareness
- ✅ Offline or sensitive projects

**Use Aider when:**
- ✅ Implementing with file edits
- ✅ Have clear plan already
- ✅ Focused changes to known files
- ✅ Git integration needed

**Use Claude Code when:**
- ✅ Complex multi-step tasks
- ✅ Need codebase exploration
- ✅ Bash commands and operations
- ✅ Don't mind API costs

**Use Ollama directly when:**
- ✅ Quick one-off questions
- ✅ No file context needed
- ✅ Maximum speed required
