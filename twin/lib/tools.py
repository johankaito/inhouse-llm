"""
Tool system for twin
Implements core tools: Read, Write, Edit, Bash, Glob, Grep
Plus online resources: web_search, web_fetch, GitHub API
"""

import os
import re
import subprocess
import glob as glob_module
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

# Online resources
try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False

try:
    import requests
    from bs4 import BeautifulSoup
    import html2text
    WEB_FETCH_AVAILABLE = True
except ImportError:
    WEB_FETCH_AVAILABLE = False

try:
    from github import Github
    GITHUB_AVAILABLE = True
except ImportError:
    GITHUB_AVAILABLE = False

# Self-improvement
try:
    from self_improver import SelfImprover
    SELF_IMPROVEMENT_AVAILABLE = True
except ImportError:
    SELF_IMPROVEMENT_AVAILABLE = False


class ToolResult:
    """Result from tool execution"""
    def __init__(self, success: bool, output: Any, error: Optional[str] = None, metadata: Optional[Dict] = None):
        self.success = success
        self.output = output
        self.error = error
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'output': self.output,
            'error': self.error,
            'metadata': self.metadata
        }


class Tool:
    """Base tool class"""
    def __init__(self, name: str, description: str, execute_fn: Callable, args_schema: Dict[str, Any]):
        self.name = name
        self.description = description
        self.execute = execute_fn
        self.args_schema = args_schema

    def __repr__(self):
        return f"Tool({self.name})"


class ToolRegistry:
    """Registry for managing tools"""
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.tools = {}
        self.config = config or {}
        self._register_core_tools()
        self._register_online_tools()
        self._register_github_tools()
        self._register_self_improvement_tool()

    def register(self, tool: Tool):
        """Register a tool"""
        self.tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        """Get tool by name"""
        return self.tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        """List all available tools"""
        return [
            {
                'name': tool.name,
                'description': tool.description,
                'args': tool.args_schema
            }
            for tool in self.tools.values()
        ]

    def get_tool_descriptions(self) -> str:
        """Get formatted tool descriptions for prompt"""
        descriptions = []
        for tool in self.tools.values():
            args_str = ", ".join(f"{k}: {v}" for k, v in tool.args_schema.items())
            descriptions.append(f"{tool.name}({args_str})\n   {tool.description}")
        return "\n\n".join(descriptions)

    def _register_core_tools(self):
        """Register core built-in tools"""
        # File operations
        self.register(Tool(
            name="read",
            description="Read file contents. Returns file content with line numbers.",
            execute_fn=self._read_file,
            args_schema={"file_path": "string", "offset": "int (optional)", "limit": "int (optional)"}
        ))

        self.register(Tool(
            name="write",
            description="Create or overwrite a file with new content.",
            execute_fn=self._write_file,
            args_schema={"file_path": "string", "content": "string"}
        ))

        self.register(Tool(
            name="edit",
            description="Edit existing file by replacing old_string with new_string. Exact match required.",
            execute_fn=self._edit_file,
            args_schema={"file_path": "string", "old_string": "string", "new_string": "string"}
        ))

        # Shell operations
        self.register(Tool(
            name="bash",
            description="Execute bash command. Use for git, npm, docker, etc. Returns stdout and stderr.",
            execute_fn=self._bash,
            args_schema={"command": "string", "timeout": "int (optional, default 120)"}
        ))

        # File search
        self.register(Tool(
            name="glob",
            description="Find files matching glob pattern (e.g., '**/*.py', 'src/**/*.ts'). Returns list of paths.",
            execute_fn=self._glob,
            args_schema={"pattern": "string", "path": "string (optional, default cwd)"}
        ))

        self.register(Tool(
            name="grep",
            description="Search file contents for pattern using regex. Returns matching lines with context.",
            execute_fn=self._grep,
            args_schema={"pattern": "string", "path": "string (optional, default cwd)", "context": "int (optional, lines of context)"}
        ))

    # Tool implementations

    def _read_file(self, file_path: str, offset: int = 0, limit: int = None) -> ToolResult:
        """Read file with optional line range"""
        try:
            path = Path(file_path).expanduser()

            if not path.exists():
                return ToolResult(False, None, f"File not found: {file_path}")

            if not path.is_file():
                return ToolResult(False, None, f"Not a file: {file_path}")

            lines = path.read_text().splitlines()

            # Apply offset and limit
            start = offset
            end = offset + limit if limit else len(lines)
            selected_lines = lines[start:end]

            # Format with line numbers
            formatted = "\n".join(
                f"{i+start+1:6d}\t{line}"
                for i, line in enumerate(selected_lines)
            )

            metadata = {
                'total_lines': len(lines),
                'returned_lines': len(selected_lines),
                'offset': start,
                'file_path': str(path)
            }

            return ToolResult(True, formatted, metadata=metadata)

        except Exception as e:
            return ToolResult(False, None, f"Error reading file: {e}")

    def _write_file(self, file_path: str, content: str) -> ToolResult:
        """Write content to file"""
        try:
            path = Path(file_path).expanduser()

            # Create parent directories
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write content
            path.write_text(content)

            metadata = {
                'file_path': str(path),
                'bytes_written': len(content.encode()),
                'lines': len(content.splitlines())
            }

            return ToolResult(True, f"Created {file_path}", metadata=metadata)

        except Exception as e:
            return ToolResult(False, None, f"Error writing file: {e}")

    def _edit_file(self, file_path: str, old_string: str, new_string: str) -> ToolResult:
        """Edit file by replacing text"""
        try:
            path = Path(file_path).expanduser()

            if not path.exists():
                return ToolResult(False, None, f"File not found: {file_path}")

            content = path.read_text()

            if old_string not in content:
                return ToolResult(False, None, f"String not found in file: '{old_string[:50]}...'")

            # Count occurrences
            count = content.count(old_string)
            if count > 1:
                return ToolResult(False, None,
                    f"String appears {count} times. Be more specific or use replace_all.")

            # Replace
            new_content = content.replace(old_string, new_string)
            path.write_text(new_content)

            metadata = {
                'file_path': str(path),
                'replacements': 1,
                'old_length': len(old_string),
                'new_length': len(new_string)
            }

            return ToolResult(True, f"Edited {file_path}", metadata=metadata)

        except Exception as e:
            return ToolResult(False, None, f"Error editing file: {e}")

    def _bash(self, command: str, timeout: int = 120) -> ToolResult:
        """Execute bash command"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"

            metadata = {
                'returncode': result.returncode,
                'command': command,
                'timeout': timeout
            }

            if result.returncode == 0:
                return ToolResult(True, output, metadata=metadata)
            else:
                return ToolResult(False, output, f"Command failed with code {result.returncode}", metadata)

        except subprocess.TimeoutExpired:
            return ToolResult(False, None, f"Command timed out after {timeout}s")
        except Exception as e:
            return ToolResult(False, None, f"Error executing command: {e}")

    def _glob(self, pattern: str, path: str = None) -> ToolResult:
        """Find files matching glob pattern"""
        try:
            search_path = Path(path or os.getcwd()).expanduser()

            if not search_path.exists():
                return ToolResult(False, None, f"Path not found: {path}")

            # Use glob to find files
            matches = list(search_path.glob(pattern))

            # Sort by modification time (most recent first)
            matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)

            # Convert to relative paths if possible
            try:
                cwd = Path.cwd()
                file_list = [str(m.relative_to(cwd)) for m in matches]
            except:
                file_list = [str(m) for m in matches]

            metadata = {
                'count': len(matches),
                'pattern': pattern,
                'search_path': str(search_path)
            }

            if not file_list:
                return ToolResult(True, "No files found", metadata=metadata)

            output = "\n".join(file_list)
            return ToolResult(True, output, metadata=metadata)

        except Exception as e:
            return ToolResult(False, None, f"Error searching files: {e}")

    def _grep(self, pattern: str, path: str = None, context: int = 0) -> ToolResult:
        """Search file contents for pattern"""
        try:
            search_path = Path(path or os.getcwd()).expanduser()

            if not search_path.exists():
                return ToolResult(False, None, f"Path not found: {path}")

            matches = []
            regex = re.compile(pattern)

            # Search files
            if search_path.is_file():
                files_to_search = [search_path]
            else:
                files_to_search = [
                    f for f in search_path.rglob('*')
                    if f.is_file() and not self._should_ignore(f)
                ]

            for file_path in files_to_search:
                try:
                    lines = file_path.read_text().splitlines()

                    for i, line in enumerate(lines):
                        if regex.search(line):
                            # Add context lines
                            start = max(0, i - context)
                            end = min(len(lines), i + context + 1)

                            match_info = {
                                'file': str(file_path.relative_to(search_path) if search_path.is_dir() else file_path.name),
                                'line_number': i + 1,
                                'line': line,
                                'context': lines[start:end] if context > 0 else None
                            }
                            matches.append(match_info)

                except (UnicodeDecodeError, PermissionError):
                    # Skip binary files and files we can't read
                    continue

            # Format output
            if not matches:
                return ToolResult(True, "No matches found", metadata={'count': 0, 'pattern': pattern})

            output_lines = []
            for match in matches:
                output_lines.append(f"{match['file']}:{match['line_number']}: {match['line']}")
                if context > 0 and match['context']:
                    for ctx_line in match['context']:
                        output_lines.append(f"    {ctx_line}")
                    output_lines.append("")  # Blank line between matches

            output = "\n".join(output_lines)
            metadata = {
                'count': len(matches),
                'pattern': pattern,
                'search_path': str(search_path)
            }

            return ToolResult(True, output, metadata=metadata)

        except Exception as e:
            return ToolResult(False, None, f"Error searching: {e}")

    def _should_ignore(self, path: Path) -> bool:
        """Check if file should be ignored in search"""
        ignore_patterns = [
            '.git', '__pycache__', 'node_modules', '.venv', 'venv',
            '.pyc', '.so', '.dylib', '.bin', '.exe'
        ]

        path_str = str(path)
        return any(pattern in path_str for pattern in ignore_patterns)

    # Online resource tools

    def _register_online_tools(self):
        """Register online resource tools (web search, fetch)"""
        if DDGS_AVAILABLE:
            self.register(Tool(
                name="web_search",
                description="Search the web for current information using DuckDuckGo. Returns top results with titles, summaries, and URLs.",
                execute_fn=self._web_search,
                args_schema={"query": "string", "max_results": "int (optional, default 5)"}
            ))

        if WEB_FETCH_AVAILABLE:
            self.register(Tool(
                name="web_fetch",
                description="Fetch and read content from a URL. Converts HTML to readable markdown format.",
                execute_fn=self._web_fetch,
                args_schema={"url": "string"}
            ))

    def _web_search(self, query: str, max_results: int = 5) -> ToolResult:
        """Search the web with DuckDuckGo"""
        try:
            ddgs = DDGS()
            results = list(ddgs.text(query, max_results=max_results))

            if not results:
                return ToolResult(True, "No results found", metadata={'count': 0, 'query': query})

            formatted = []
            for i, result in enumerate(results, 1):
                formatted.append(f"{i}. **{result.get('title', 'No title')}**")
                formatted.append(f"   {result.get('body', 'No description')}")
                formatted.append(f"   URL: {result.get('href', 'No URL')}\n")

            output = "\n".join(formatted)
            metadata = {'count': len(results), 'query': query}

            return ToolResult(True, output, metadata=metadata)

        except Exception as e:
            return ToolResult(False, None, f"Web search failed: {e}")

    def _web_fetch(self, url: str) -> ToolResult:
        """Fetch and convert URL to readable text"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            content_type = response.headers.get('content-type', '')

            if 'text/html' in content_type:
                # Convert HTML to markdown
                soup = BeautifulSoup(response.content, 'html.parser')

                # Remove script and style elements
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.decompose()

                h = html2text.HTML2Text()
                h.ignore_links = False
                h.body_width = 0
                markdown = h.handle(str(soup))

                # Truncate if too long
                if len(markdown) > 10000:
                    markdown = markdown[:10000] + "\n\n[Content truncated - too long]"

                return ToolResult(True, markdown, metadata={'url': url, 'length': len(markdown)})
            else:
                # Return raw text
                text = response.text[:10000]
                return ToolResult(True, text, metadata={'url': url, 'content_type': content_type})

        except Exception as e:
            return ToolResult(False, None, f"Failed to fetch URL: {e}")

    def _register_github_tools(self):
        """Register GitHub API tools"""
        if not GITHUB_AVAILABLE:
            return

        github_token = os.getenv('GITHUB_TOKEN')
        if not github_token:
            return  # Skip if no token

        try:
            self.gh = Github(github_token)

            self.register(Tool(
                name="gh_search_code",
                description="Search GitHub code repositories. Requires GITHUB_TOKEN environment variable.",
                execute_fn=self._gh_search_code,
                args_schema={"query": "string", "repo": "string (optional, e.g., 'owner/repo')"}
            ))

            self.register(Tool(
                name="gh_get_pr",
                description="Get GitHub pull request details. Requires GITHUB_TOKEN environment variable.",
                execute_fn=self._gh_get_pr,
                args_schema={"repo": "string (e.g., 'owner/repo')", "pr_number": "int"}
            ))
        except Exception as e:
            # Silently skip if GitHub setup fails
            pass

    def _gh_search_code(self, query: str, repo: str = None) -> ToolResult:
        """Search GitHub code"""
        try:
            if not hasattr(self, 'gh'):
                return ToolResult(False, None, "GitHub not configured (missing GITHUB_TOKEN)")

            if repo:
                results = self.gh.search_code(f"{query} repo:{repo}")
            else:
                results = self.gh.search_code(query)

            formatted = []
            count = 0
            for result in results[:10]:  # Limit to 10 results
                formatted.append(f"{count + 1}. {result.repository.full_name}/{result.path}")
                formatted.append(f"   {result.html_url}\n")
                count += 1

            if not formatted:
                return ToolResult(True, "No results found", metadata={'count': 0})

            return ToolResult(True, "\n".join(formatted), metadata={'count': count, 'query': query})

        except Exception as e:
            return ToolResult(False, None, f"GitHub search failed: {e}")

    def _gh_get_pr(self, repo: str, pr_number: int) -> ToolResult:
        """Get GitHub PR details"""
        try:
            if not hasattr(self, 'gh'):
                return ToolResult(False, None, "GitHub not configured (missing GITHUB_TOKEN)")

            repo_obj = self.gh.get_repo(repo)
            pr = repo_obj.get_pull(pr_number)

            output = f"""# PR #{pr.number}: {pr.title}

**Status:** {pr.state}
**Author:** {pr.user.login}
**Created:** {pr.created_at}

## Description
{pr.body or 'No description'}

## Stats
- Files Changed: {pr.changed_files}
- Commits: {pr.commits}
- Comments: {pr.comments}
- Additions: +{pr.additions}
- Deletions: -{pr.deletions}
"""
            return ToolResult(True, output, metadata={'pr_number': pr_number, 'repo': repo})

        except Exception as e:
            return ToolResult(False, None, f"Failed to get PR: {e}")

    # Self-improvement tools

    def _register_self_improvement_tool(self):
        """Register self-improvement tool"""
        if not SELF_IMPROVEMENT_AVAILABLE:
            return

        twin_dir = Path(__file__).parent.parent
        self.self_improver = SelfImprover(twin_dir)

        self.register(Tool(
            name="improve_self",
            description="Improve twin's own code. Automatically commits changes to git with [SELF-IMPROVEMENT] tag. Use when you identify bugs, optimizations, or missing features in twin itself.",
            execute_fn=self._improve_self,
            args_schema={
                "description": "string (brief description of improvement)",
                "reasoning": "string (5 Whys analysis explaining why this improvement is needed)",
                "files": "dict (file_path: new_content pairs, relative to twin/ directory)"
            }
        ))

    def _improve_self(self, description: str, reasoning: str, files: Dict[str, str]) -> ToolResult:
        """Improve twin's own code"""
        try:
            if not hasattr(self, 'self_improver'):
                return ToolResult(False, None, "Self-improvement not available")

            result = self.self_improver.propose_improvement(
                description=description,
                reasoning=reasoning,
                files=files
            )

            # Format output with diff
            commit_hash = result['commit_hash']
            diff = result['diff']
            improvement_id = result['improvement_id']
            files_changed = result['files_changed']

            output = f"""
✅ Improvement {improvement_id} applied and committed

**Commit:** {commit_hash[:7]}
**Files Changed:** {', '.join(files_changed)}

**Changes Made:**
```diff
{diff}
```

See IMPROVEMENTS.md for full details.
"""

            return ToolResult(
                True,
                output,
                metadata={
                    'auto_committed': True,
                    'requires_restart': True,
                    'commit_hash': commit_hash,
                    'improvement_id': improvement_id
                }
            )

        except Exception as e:
            return ToolResult(False, None, f"Self-improvement failed: {e}")
