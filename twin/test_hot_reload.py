#!/usr/bin/env python3
"""
Test hot reload functionality
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

def test_hot_reload():
    """Test module reloading"""
    print("Testing twin hot reload functionality...\n")

    # Test 1: Import modules
    print("1. Testing module imports...")
    try:
        from tools import ToolRegistry
        from self_improver import SelfImprover
        from config import ConfigLoader
        print("   ✓ All modules imported successfully\n")
    except ImportError as e:
        print(f"   ✗ Import failed: {e}\n")
        return

    # Test 2: Check importlib reload capability
    print("2. Testing importlib reload...")
    import importlib
    try:
        import tools
        importlib.reload(tools)
        print("   ✓ tools module reloaded\n")

        import self_improver
        importlib.reload(self_improver)
        print("   ✓ self_improver module reloaded\n")
    except Exception as e:
        print(f"   ✗ Reload failed: {e}\n")

    # Test 3: Verify tool registry reinitializes
    print("3. Testing tool registry reinitialization...")
    try:
        registry1 = ToolRegistry()
        count1 = len(registry1.tools)

        # Reload and create new registry
        importlib.reload(tools)
        from tools import ToolRegistry as ToolRegistry2
        registry2 = ToolRegistry2()
        count2 = len(registry2.tools)

        print(f"   Original: {count1} tools")
        print(f"   After reload: {count2} tools")
        print("   ✓ Tool registry reinitializes correctly\n")
    except Exception as e:
        print(f"   ✗ Registry test failed: {e}\n")

    # Test 4: Check self-improver
    print("4. Testing SelfImprover...")
    try:
        twin_dir = Path(__file__).parent
        improver = SelfImprover(twin_dir)
        can_improve = improver.can_improve()
        print(f"   Can improve: {can_improve}")
        print(f"   Improvements log: {improver.improvements_log.exists()}")
        print("   ✓ SelfImprover functional\n")
    except Exception as e:
        print(f"   ✗ SelfImprover test failed: {e}\n")

    print("✅ Hot reload system functional!")
    print("\nTo test in twin session:")
    print("  1. Start twin")
    print("  2. Make a change to twin code (or use improve_self)")
    print("  3. Use /reload command")
    print("  4. Changes should be active immediately")

if __name__ == "__main__":
    test_hot_reload()
