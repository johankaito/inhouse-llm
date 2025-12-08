# Twin Testing Guide

## Quick Test Suite

Run the automated test suite to verify core functionality:

```bash
python3 twin/test_session.py
```

This tests:
- ✅ Module imports
- ✅ Key binding initialization
- ✅ Clipboard access (pyperclip)
- ✅ Image detection (PIL.ImageGrab)

Expected output: `🎉 All tests passed! Twin should work correctly.`

## Manual Testing Loop

### 1. Test Basic Startup
```bash
twin
```

**Expected**: Twin starts, shows session info, prompt appears

**If it fails**: Check error message, run test suite first

### 2. Test Enter Key (Submit)
- Type: `hello`
- Press: **Enter**

**Expected**: Message submits to Ollama, you get a response

### 3. Test Shift+Enter (Newline)
- Type: `line 1`
- Press: **Shift+Enter**
- Type: `line 2`
- Press: **Enter**

**Expected**: Both lines sent together as multiline message

### 4. Test Ctrl+V Text Paste
- Copy some text to clipboard: `echo "test text" | pbcopy`
- In twin, press: **Ctrl+V**
- Press: **Enter**

**Expected**: Text pastes and submits

### 5. Test Ctrl+V Image Paste
- Take a screenshot (Cmd+Shift+4) or copy an image
- In twin, type: `what's in this image?`
- Press: **Ctrl+V** (while image in clipboard)
- Press: **Enter**

**Expected**:
- `📸 Image detected in clipboard → /tmp/...`
- `🔄 Switching to llava:7b for vision support`
- Response analyzing the image

### 6. Test Commands
```bash
# In twin:
/help          # Shows help
/model fast    # Switches model
/context       # Shows context summary
/bye           # Exits
```

## Development Testing Workflow

When making changes to `twin/lib/session.py`:

```bash
# 1. Run automated tests first
python3 twin/test_session.py

# 2. If tests pass, do manual smoke test
twin
# Type "test" and press Enter
# Type /bye to exit

# 3. If manual test works, commit
git add -A
git commit -m "Your change description"
```

## Debugging Startup Issues

### Error: "Invalid key: ..."
**Problem**: Invalid key binding syntax

**Fix**: Check `_create_prompt_session()` in `session.py`
- Valid formats: `'enter'`, `'c-v'` (Ctrl+V), `'c-d'` (Ctrl+D)
- Invalid formats: `'s-enter'` (use shift detection in handler instead)

**Test**: `python3 twin/test_session.py` - should show "✅ Key bindings initialized"

### Error: "Expecting a bool or Filter instance"
**Problem**: Invalid filter parameter in key binding

**Fix**: Remove `filter=` parameter or use proper Filter import

**Test**: Key bindings test will catch this

### Clipboard Not Working
**Problem**: pyperclip not installed or system clipboard access denied

**Check**:
```bash
python3 -c "import pyperclip; print(pyperclip.paste())"
```

**Fix**:
```bash
pip3 install pyperclip
```

### Image Detection Not Working
**Problem**: PIL not installed or no vision model

**Check**:
```bash
python3 -c "from PIL import ImageGrab; print(ImageGrab.grabclipboard())"
ollama list | grep llava
```

**Fix**:
```bash
pip3 install pillow
ollama pull llava:7b
```

## Testing Checklist for New Features

Before committing changes:

- [ ] Automated tests pass: `python3 twin/test_session.py`
- [ ] Twin starts without errors: `twin` (then `/bye`)
- [ ] Key bindings work as expected
- [ ] No Python exceptions in normal operation
- [ ] Help text is accurate: `/help`
- [ ] Can exit cleanly: `/bye`

## Rollback if Broken

If you break twin and can't start it:

```bash
# 1. Check what you changed
git diff twin/lib/session.py

# 2. Run tests to see specific error
python3 twin/test_session.py

# 3. If totally broken, revert
git checkout HEAD -- twin/lib/session.py

# 4. Verify it works again
python3 twin/test_session.py
twin
```

## Common Test Scenarios

### Scenario: Changed key bindings
```bash
# 1. Test suite
python3 twin/test_session.py  # Must pass

# 2. Manual test each binding
twin
# Test Enter
# Test Shift+Enter
# Test Ctrl+V
/bye
```

### Scenario: Changed clipboard detection
```bash
# 1. Copy text, test Ctrl+V
echo "test" | pbcopy
twin  # Press Ctrl+V, Enter

# 2. Copy image, test detection
# Take screenshot (Cmd+Shift+4)
twin  # Press Ctrl+V, should see "📸 Image detected"
```

### Scenario: Changed system prompt or agent logic
```bash
# 1. Quick startup test
twin
# Type: "test"
# Verify response makes sense
/bye

# 2. Context test
twin
/context  # Should show previous sessions
/bye
```

## Performance Testing

### Response Time
```bash
twin
# Type a simple query
# Note the time at bottom: "⏱️  X.Xs | model-name"
```

**Expected**:
- Fast model (qwen2.5-coder:1.5b): 2-5s
- Balanced model (qwen2.5-coder:7b): 5-15s
- Large model (qwen2.5-coder:32b): 20-60s

If slower, check:
- `ollama ps` - ensure GPU acceleration
- System load
- Model size vs available RAM

## Test Coverage

Current automated tests cover:
- ✅ Module imports
- ✅ Key binding creation
- ✅ Clipboard access
- ✅ Image detection

Not yet automated (manual testing required):
- ⚠️ Actual Enter/Shift+Enter behavior (requires terminal)
- ⚠️ Ollama integration (requires running Ollama)
- ⚠️ Tool execution (requires full setup)
- ⚠️ Context persistence (requires multiple sessions)

## Adding New Tests

To add tests to `test_session.py`:

```python
def test_your_feature():
    """Test description"""
    print("\nTesting your feature...")
    try:
        # Your test code
        print("  ✅ Feature works")
        return True
    except Exception as e:
        print(f"  ❌ Feature failed: {e}")
        return False

# Then add to run_all_tests():
results.append(("Your Feature", test_your_feature()))
```
