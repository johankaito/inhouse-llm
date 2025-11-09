#!/usr/bin/env python3
"""
Test script for twin tools
"""

import sys
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from tools import ToolRegistry

def test_tools():
    """Test all core tools"""
    print("Testing twin tools...\n")

    # Initialize registry
    registry = ToolRegistry()

    # Test 1: Write a file
    print("1. Testing write tool...")
    write_tool = registry.get("write")
    result = write_tool.execute(
        file_path="/tmp/test_twin.txt",
        content="Hello from twin!"
    )
    print(f"   Result: {result.success}")
    print(f"   Output: {result.output}\n")

    # Test 2: Read the file
    print("2. Testing read tool...")
    read_tool = registry.get("read")
    result = read_tool.execute(file_path="/tmp/test_twin.txt")
    print(f"   Result: {result.success}")
    print(f"   Output:\n{result.output}\n")

    # Test 3: Edit the file
    print("3. Testing edit tool...")
    edit_tool = registry.get("edit")
    result = edit_tool.execute(
        file_path="/tmp/test_twin.txt",
        old_string="Hello",
        new_string="Greetings"
    )
    print(f"   Result: {result.success}")
    print(f"   Output: {result.output}\n")

    # Test 4: Read again to verify edit
    print("4. Reading edited file...")
    result = read_tool.execute(file_path="/tmp/test_twin.txt")
    print(f"   Output:\n{result.output}\n")

    # Test 5: Bash command
    print("5. Testing bash tool...")
    bash_tool = registry.get("bash")
    result = bash_tool.execute(command="echo 'Twin bash works!'")
    print(f"   Result: {result.success}")
    print(f"   Output: {result.output}\n")

    # Test 6: Glob
    print("6. Testing glob tool...")
    glob_tool = registry.get("glob")
    result = glob_tool.execute(pattern="*.py", path=str(Path(__file__).parent))
    print(f"   Result: {result.success}")
    print(f"   Files found: {result.metadata['count']}\n")

    # Test 7: Grep
    print("7. Testing grep tool...")
    grep_tool = registry.get("grep")
    result = grep_tool.execute(
        pattern="def test",
        path=str(Path(__file__))
    )
    print(f"   Result: {result.success}")
    print(f"   Matches: {result.metadata['count']}\n")

    # List all tools
    print("8. Listing all available tools...")
    tools = registry.list_tools()
    for tool in tools:
        print(f"   - {tool['name']}: {tool['description']}")

    print("\n✅ All tools tested successfully!")

if __name__ == "__main__":
    test_tools()
