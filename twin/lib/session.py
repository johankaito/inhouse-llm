"""
Session orchestrator for twin
Handles interactive Ollama chat sessions
"""

import os
import sys
import uuid
import subprocess
import re
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.spinner import Spinner
from rich.live import Live

from tools import ToolRegistry, ToolResult

console = Console()


class SessionOrchestrator:
    """Orchestrate interactive planning sessions"""

    def __init__(
        self,
        config: Dict[str, Any],
        mode: str,
        agent: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        model: str,
        agent_loader,
        mode_detector,
        context_manager
    ):
        self.config = config
        self.mode = mode
        self.agent = agent
        self.context = context
        self.model = model
        self.agent_loader = agent_loader
        self.mode_detector = mode_detector
        self.context_manager = context_manager

        self.session_id = uuid.uuid4().hex[:8]
        self.conversation = []
        self.session_data = {
            'session_id': self.session_id,
            'mode': mode,
            'agent': agent['name'],
            'planning_discussion': '',
            'decisions': [],
            'reasoning': [],
            'next_steps': [],
            'files_discussed': []
        }

        # Initialize tool registry
        self.tool_registry = ToolRegistry(config)

    def run(self):
        """Run interactive session"""
        cwd = os.getcwd()

        # Display context summary if available
        if self.context:
            summary = self.context_manager.get_context_summary(cwd)
            console.print(f"\n[dim]{summary}[/dim]\n")

        # Build system prompt
        system_prompt = self._build_system_prompt()

        # Main loop
        while True:
            try:
                # Get user input
                user_input = Prompt.ask("\n[bold cyan]>>>[/bold cyan]", console=console)

                if not user_input.strip():
                    continue

                # Handle commands
                if user_input.startswith('/'):
                    result = self._handle_command(user_input.strip())
                    if result == 'exit':
                        break
                    elif result == 'continue':
                        continue
                    # Otherwise continue to process as regular input

                # Track conversation
                self.session_data['planning_discussion'] += f"\n{user_input}\n"

                # Call Ollama
                response = self._call_ollama(system_prompt, user_input)

                if response:
                    # Check for tool calls in response
                    tool_calls = self._parse_tool_calls(response)

                    if tool_calls:
                        # Execute tools
                        tool_results = self._execute_tools(tool_calls)

                        # Format results and send back to model
                        tool_results_text = self._format_tool_results(tool_results)

                        # Continue conversation with tool results
                        followup_prompt = f"Here are the tool results:\n\n{tool_results_text}\n\nPlease continue your response based on these results."
                        response = self._call_ollama(system_prompt, followup_prompt)

                    if response:
                        # Display final response (strip out any remaining tool call markers)
                        clean_response = re.sub(r'TOOL_CALL:.*?ARGS:.*?\}', '', response, flags=re.DOTALL)
                        console.print()
                        console.print(Markdown(clean_response))
                        console.print()

                        # Track conversation
                        self.session_data['planning_discussion'] += f"\n{response}\n"

            except KeyboardInterrupt:
                console.print("\n\n[yellow]Interrupted[/yellow]")
                if Prompt.ask("Save session before exiting?", choices=["y", "n"], default="y") == "y":
                    self._save_session()
                break
            except Exception as e:
                console.print(f"\n[red]Error: {e}[/red]")
                if os.getenv('DEBUG'):
                    raise

    def _build_system_prompt(self) -> str:
        """Build system prompt for Ollama"""
        # Start with agent master prompt
        prompt_parts = []

        if self.agent.get('master_prompt'):
            prompt_parts.append(self.agent['master_prompt'])

        # Add mode-specific behavior
        if self.mode == 'work':
            prompt_parts.append("""
Current Mode: WORK MODE

- Use professional, technical tone
- Focus on business value and technical accuracy
- Apply full 5 Whys protocol for architecture decisions
- Be concise and actionable
""")
        else:
            prompt_parts.append("""
Current Mode: PERSONAL MODE

- Use conversational, friendly tone
- Be exploratory and flexible
- Apply 3-5 Whys for major decisions, 1-3 for others
- Can be more verbose and discuss trade-offs
""")

        # Add 5 Whys protocol
        prompt_parts.append("""
5 Whys Protocol:
For non-trivial recommendations, you MUST provide:
1. Why Level 1: Direct reason
2. Why Level 2: Underlying benefit
3. Why Level 3: Goal alignment
4. Why Level 4: Value connection
5. Why Level 5: Root principle
6. Trade-offs considered
7. Confidence level and reasoning quality
""")

        # Add tool descriptions
        prompt_parts.append(self._get_tool_instructions())

        # Add context if available
        if self.context:
            recent_sessions = self.context_manager.get_recent_sessions(os.getcwd(), count=2)
            if recent_sessions:
                context_summary = "\n\n".join([
                    f"Previous session ({s['timestamp']}):\n{s['content'][:500]}..."
                    for s in recent_sessions
                ])
                prompt_parts.append(f"\n\nPrevious Context:\n{context_summary}")

        return "\n\n".join(prompt_parts)

    def _get_tool_instructions(self) -> str:
        """Generate tool calling instructions for prompt"""
        tool_list = self.tool_registry.list_tools()

        tool_descriptions = []
        for tool in tool_list:
            args_str = ", ".join(f"{k}: {v}" for k, v in tool['args'].items())
            tool_descriptions.append(
                f"**{tool['name']}({args_str})**\n   {tool['description']}"
            )

        return f"""
## Available Tools

You have access to these tools to help complete tasks:

{chr(10).join(tool_descriptions)}

To use a tool, output in this EXACT format:
```
TOOL_CALL: tool_name
ARGS: {{"arg1": "value1", "arg2": "value2"}}
```

After tool execution, you'll receive:
```
TOOL_RESULT: [success/error]
OUTPUT: [tool output]
```

Then continue your response based on the tool result.

**When to use tools:**
- To read file contents: use read()
- To create new files: use write()
- To edit existing files: use edit() for simple changes
- To run commands: use bash()
- To find files: use glob()
- To search file contents: use grep()

**Important:**
- Always use tools when you need to interact with files or the system
- Don't make assumptions about file contents - read them first
- Be precise with file paths
"""

    def _parse_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """Parse tool calls from model response"""
        tool_calls = []

        # Pattern to match TOOL_CALL and ARGS blocks
        pattern = r'TOOL_CALL:\s*(\w+)\s*\nARGS:\s*(\{[^}]+\})'

        matches = re.finditer(pattern, response, re.MULTILINE | re.DOTALL)

        for match in matches:
            tool_name = match.group(1).strip()
            args_str = match.group(2).strip()

            try:
                args = json.loads(args_str)
                tool_calls.append({
                    'tool': tool_name,
                    'args': args
                })
            except json.JSONDecodeError as e:
                console.print(f"[yellow]Warning: Failed to parse args for {tool_name}: {e}[/yellow]")

        return tool_calls

    def _execute_tools(self, tool_calls: List[Dict[str, Any]]) -> List[ToolResult]:
        """Execute tool calls and return results"""
        results = []

        for call in tool_calls:
            tool_name = call['tool']
            args = call['args']

            console.print(f"\n[dim]🔧 Executing: {tool_name}({', '.join(f'{k}={v}' for k, v in args.items())})[/dim]")

            tool = self.tool_registry.get(tool_name)

            if not tool:
                results.append(ToolResult(
                    success=False,
                    output=None,
                    error=f"Unknown tool: {tool_name}"
                ))
                continue

            try:
                with console.status(f"[cyan]Running {tool_name}...", spinner="dots"):
                    result = tool.execute(**args)
                results.append(result)

                # Show result summary
                if result.success:
                    console.print(f"[green]✓ {tool_name} completed[/green]")
                else:
                    console.print(f"[red]✗ {tool_name} failed: {result.error}[/red]")

            except Exception as e:
                console.print(f"[red]✗ Error executing {tool_name}: {e}[/red]")
                results.append(ToolResult(
                    success=False,
                    output=None,
                    error=str(e)
                ))

        return results

    def _format_tool_results(self, results: List[ToolResult]) -> str:
        """Format tool results to send back to model"""
        formatted = []

        for i, result in enumerate(results):
            status = "success" if result.success else "error"

            formatted.append(f"""
TOOL_RESULT: {status}
OUTPUT: {result.output if result.output else result.error}
""")

        return "\n".join(formatted)

    def _call_ollama(self, system_prompt: str, user_input: str) -> Optional[str]:
        """Call Ollama API"""
        try:
            # Combine system prompt with user input for first message
            # Ollama doesn't have system role, so we prepend it
            full_prompt = f"{system_prompt}\n\n---\n\nUser: {user_input}\n\nAssistant:"

            # Use subprocess to call ollama
            result = subprocess.run(
                ['ollama', 'run', self.model, full_prompt],
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode == 0:
                return result.stdout.strip()
            else:
                console.print(f"[red]Ollama error: {result.stderr}[/red]")
                return None

        except subprocess.TimeoutExpired:
            console.print("[red]Ollama request timed out[/red]")
            return None
        except FileNotFoundError:
            console.print("[red]Ollama not found. Is it installed?[/red]")
            return None
        except Exception as e:
            console.print(f"[red]Error calling Ollama: {e}[/red]")
            return None

    def _handle_command(self, command: str) -> str:
        """Handle slash commands"""
        parts = command[1:].split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd == 'help':
            self._show_help()
            return 'continue'

        elif cmd == 'mode':
            if args in ['work', 'personal']:
                self.mode = args
                self.session_data['mode'] = args
                console.print(f"\n[green]✓ Switched to {args.upper()} mode[/green]\n")
            else:
                console.print(f"\n[yellow]Usage: /mode work|personal[/yellow]\n")
            return 'continue'

        elif cmd == 'agent':
            if args:
                try:
                    self.agent = self.agent_loader.get_agent(args)
                    self.session_data['agent'] = args
                    console.print(f"\n[green]✓ Switched to agent: {args}[/green]\n")
                except ValueError as e:
                    console.print(f"\n[red]{e}[/red]\n")
            else:
                console.print(f"\n[yellow]Usage: /agent <name>[/yellow]\n")
                console.print(f"Available agents: {', '.join(self.agent_loader.agents.keys())}\n")
            return 'continue'

        elif cmd == 'context':
            summary = self.context_manager.get_context_summary(os.getcwd())
            console.print(f"\n[cyan]{summary}[/cyan]\n")
            return 'continue'

        elif cmd == 'save':
            self._save_session()
            console.print(f"\n[green]✓ Session saved[/green]\n")
            return 'continue'

        elif cmd == 'edit':
            self._transition_to_aider()
            return 'continue'

        elif cmd in ['bye', 'exit', 'quit']:
            self._save_session()
            console.print(f"\n[green]✓ Session saved. Goodbye![/green]\n")
            return 'exit'

        else:
            console.print(f"\n[yellow]Unknown command: {cmd}[/yellow]")
            console.print("[dim]Type /help for available commands[/dim]\n")
            return 'continue'

    def _show_help(self):
        """Show help message"""
        help_text = """
**Available Commands:**

- `/help` - Show this help message
- `/mode work|personal` - Switch between work and personal mode
- `/agent <name>` - Switch to a different agent
- `/context` - Show context summary
- `/save` - Manually save session checkpoint
- `/edit` - Transition to Aider for implementation
- `/bye` - Save and exit session

**Tips:**
- Ask planning questions naturally
- Agent will apply 5 Whys for major decisions
- Context is saved automatically on exit
"""
        console.print(Markdown(help_text))

    def _save_session(self):
        """Save session to context file"""
        cwd = os.getcwd()
        self.context_manager.append_session(cwd, self.session_data)

    def _transition_to_aider(self):
        """Transition from planning to Aider for implementation"""
        console.print("\n[cyan]Preparing to launch Aider...[/cyan]\n")

        # Save current session
        self._save_session()

        # Create planning summary
        summary = f"""
Planning Session Summary:
- Agent: {self.agent['name']}
- Mode: {self.mode}
- Session ID: {self.session_id}

Discussion:
{self.session_data['planning_discussion'][:1000]}

Decisions:
{chr(10).join('- ' + d for d in self.session_data['decisions'])}

Next Steps:
{chr(10).join('- ' + s for s in self.session_data['next_steps'])}
"""

        # Write to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(summary)
            temp_path = f.name

        console.print(f"[dim]Planning summary saved to: {temp_path}[/dim]\n")

        # Ask which files to edit
        files = Prompt.ask("Which files do you want to edit? (space-separated, or press Enter for none)")

        # Build aider command
        aider_cmd = ['aider', f'--model=ollama/{self.model}']

        if files.strip():
            aider_cmd.extend(files.split())

        # Add planning context as read-only
        aider_cmd.extend(['--read', temp_path])

        console.print(f"\n[cyan]Launching Aider:[/cyan] {' '.join(aider_cmd)}\n")

        try:
            subprocess.run(aider_cmd)
        except KeyboardInterrupt:
            console.print("\n[yellow]Aider interrupted[/yellow]\n")
        except Exception as e:
            console.print(f"\n[red]Error launching Aider: {e}[/red]\n")

        # Clean up temp file
        try:
            os.unlink(temp_path)
        except:
            pass

        console.print("\n[green]Returned from Aider[/green]\n")
