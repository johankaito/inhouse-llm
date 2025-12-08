#!/usr/bin/env python3
"""
Test script for twin session module
Tests imports and basic functionality without requiring full Ollama setup
"""

import sys
import os
from pathlib import Path

# Add twin/lib to path
sys.path.insert(0, str(Path(__file__).parent / 'lib'))

def test_imports():
    """Test that all imports work"""
    print("Testing imports...")
    try:
        from session import SessionOrchestrator, PYPERCLIP_AVAILABLE, KEYBOARD_AVAILABLE
        print("  ✅ SessionOrchestrator imported")
        print(f"  ✅ Pyperclip available: {PYPERCLIP_AVAILABLE}")
        print(f"  ✅ Keyboard listener available: {KEYBOARD_AVAILABLE}")
        return True
    except Exception as e:
        print(f"  ❌ Import failed: {e}")
        return False

def test_key_bindings():
    """Test that key bindings can be created without errors"""
    print("\nTesting key bindings...")
    try:
        from session import SessionOrchestrator
        from prompt_toolkit.key_binding import KeyBindings

        # Create a mock config for testing
        config = {
            'twin_config': {
                'model_aliases': {},
                'tools_enabled': []
            }
        }

        # Create mock objects
        class MockAgent:
            def __init__(self):
                self.name = "test-agent"
                self.master_prompt = "Test prompt"

        class MockLoader:
            def get_agent(self, name):
                return {'name': name, 'master_prompt': 'test'}

        class MockDetector:
            pass

        class MockManager:
            def get_context_summary(self, path):
                return "Test context"
            def get_recent_sessions(self, path, count=2):
                return []
            def append_session(self, path, data):
                pass

        agent = {'name': 'test-agent', 'master_prompt': 'test'}

        # Try to create session orchestrator
        orchestrator = SessionOrchestrator(
            config=config,
            mode='personal',
            agent=agent,
            context=None,
            model='qwen2.5-coder:7b',
            agent_loader=MockLoader(),
            mode_detector=MockDetector(),
            context_manager=MockManager()
        )

        print("  ✅ SessionOrchestrator created successfully")
        print("  ✅ Key bindings initialized without errors")
        return True

    except Exception as e:
        print(f"  ❌ Key binding test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_clipboard_access():
    """Test clipboard access via pyperclip"""
    print("\nTesting clipboard access...")
    try:
        import pyperclip
        # Try to access clipboard (may be empty, that's fine)
        content = pyperclip.paste()
        print(f"  ✅ Pyperclip can access clipboard")
        if content:
            print(f"  ℹ️  Current clipboard length: {len(content)} chars")
        else:
            print(f"  ℹ️  Clipboard is empty")
        return True
    except ImportError:
        print("  ⚠️  Pyperclip not available (optional)")
        return True
    except Exception as e:
        print(f"  ❌ Clipboard access failed: {e}")
        return False

def test_image_detection():
    """Test image clipboard detection"""
    print("\nTesting image clipboard detection...")
    try:
        from PIL import ImageGrab
        image = ImageGrab.grabclipboard()
        if image:
            print(f"  ✅ Image detected in clipboard: {type(image)}")
        else:
            print("  ✅ No image in clipboard (detection works)")
        return True
    except ImportError:
        print("  ⚠️  PIL not available (optional for image support)")
        return True
    except Exception as e:
        print(f"  ❌ Image detection failed: {e}")
        return False

def run_all_tests():
    """Run all tests and report results"""
    print("=" * 60)
    print("Twin Session Module Test Suite")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Key Bindings", test_key_bindings()))
    results.append(("Clipboard Access", test_clipboard_access()))
    results.append(("Image Detection", test_image_detection()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Twin should work correctly.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Review errors above.")
        return 1

if __name__ == '__main__':
    sys.exit(run_all_tests())
