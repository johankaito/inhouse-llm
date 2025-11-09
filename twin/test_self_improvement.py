#!/usr/bin/env python3
"""
Test twin's self-improvement capabilities
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from self_improver import SelfImprover

def test_self_improvement():
    """Test self-improvement system"""
    print("Testing twin self-improvement system...\n")

    twin_dir = Path(__file__).parent
    improver = SelfImprover(twin_dir)

    # Test 1: Check if can improve
    print("1. Checking if can improve...")
    can_improve = improver.can_improve()
    print(f"   Can improve: {can_improve}")
    if not can_improve:
        print("   Note: Repository may have uncommitted changes\n")
    else:
        print("   ✓ Ready for self-improvement\n")

    # Test 2: Check improvements log exists
    print("2. Checking improvements log...")
    log_exists = improver.improvements_log.exists()
    print(f"   Log exists: {log_exists}")
    print(f"   Log path: {improver.improvements_log}\n")

    # Test 3: Get recent improvements
    print("3. Recent improvements:")
    recent = improver.get_recent_improvements()
    print(f"   {recent}\n")

    # Test 4: Check git repo
    print("4. Checking git repository...")
    import subprocess
    result = subprocess.run(
        ['git', 'rev-parse', '--show-toplevel'],
        cwd=twin_dir,
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print(f"   Git repo root: {result.stdout.strip()}")
        print("   ✓ In git repository\n")
    else:
        print("   ✗ Not in git repository\n")

    print("✅ Self-improvement system ready!")
    print("\nTo test self-improvement:")
    print("  1. Ensure twin/ directory has no uncommitted changes")
    print("  2. Use twin and trigger improve_self tool")
    print("  3. Check git log for [SELF-IMPROVEMENT] commits")
    print("  4. Review IMPROVEMENTS.md")

if __name__ == "__main__":
    test_self_improvement()
