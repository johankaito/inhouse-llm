#!/usr/bin/env python3
"""
Test script for twin online resource tools
"""

import sys
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from tools import ToolRegistry

def test_online_tools():
    """Test online resource tools"""
    print("Testing twin online resource tools...\n")

    # Initialize registry
    registry = ToolRegistry()

    # Test 1: Web search
    print("1. Testing web_search tool...")
    if registry.get("web_search"):
        result = registry.get("web_search").execute(
            query="Qwen2.5 Coder model",
            max_results=3
        )
        print(f"   Result: {result.success}")
        if result.success:
            print(f"   Found {result.metadata['count']} results")
            print(f"   First result:\n{result.output.split(chr(10))[0]}\n")
        else:
            print(f"   Error: {result.error}\n")
    else:
        print("   ⚠️  web_search not available (install duckduckgo-search)\n")

    # Test 2: Web fetch
    print("2. Testing web_fetch tool...")
    if registry.get("web_fetch"):
        result = registry.get("web_fetch").execute(
            url="https://www.python.org"
        )
        print(f"   Result: {result.success}")
        if result.success:
            print(f"   Fetched {result.metadata['length']} characters")
            print(f"   Preview: {result.output[:100]}...\n")
        else:
            print(f"   Error: {result.error}\n")
    else:
        print("   ⚠️  web_fetch not available (install requests, beautifulsoup4, html2text)\n")

    # Test 3: GitHub search
    print("3. Testing gh_search_code tool...")
    if registry.get("gh_search_code"):
        print("   ⚠️  Skipping (requires GITHUB_TOKEN)\n")
    else:
        print("   ⚠️  gh_search_code not available (install PyGithub or set GITHUB_TOKEN)\n")

    # Test 4: GitHub PR
    print("4. Testing gh_get_pr tool...")
    if registry.get("gh_get_pr"):
        print("   ⚠️  Skipping (requires GITHUB_TOKEN)\n")
    else:
        print("   ⚠️  gh_get_pr not available (install PyGithub or set GITHUB_TOKEN)\n")

    # List all tools
    print("5. Listing all available tools...")
    tools = registry.list_tools()
    print(f"   Total tools: {len(tools)}")
    for tool in tools:
        print(f"   - {tool['name']}")

    print("\n✅ Online resource tools tested!")

if __name__ == "__main__":
    test_online_tools()
