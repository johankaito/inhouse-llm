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
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.spinner import Spinner
from rich.live import Live
from rich.text import Text

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.clipboard import ClipboardData

# For system clipboard access
try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
except ImportError:
    PYPERCLIP_AVAILABLE = False

from tools import ToolRegistry, ToolResult

# For ESC interrupt - using pynput instead of keyboard (works on macOS without permissions)
try:
    from pynput import keyboard as pynput_keyboard
    KEYBOARD_AVAILABLE = True

    # Global flag for ESC press
    _esc_pressed = False
    _keyboard_listener = None

    def _on_press(key):
        global _esc_pressed
        try:
            if key == pynput_keyboard.Key.esc:
                _esc_pressed = True
        except AttributeError:
            pass

    def _start_keyboard_listener():
        global _keyboard_listener
        if _keyboard_listener is None or not _keyboard_listener.is_alive():
            _keyboard_listener = pynput_keyboard.Listener(on_press=_on_press)
            _keyboard_listener.daemon = True
            _keyboard_listener.start()

    def _reset_esc_flag():
        global _esc_pressed
        _esc_pressed = False

    def _is_esc_pressed():
        return _esc_pressed

except ImportError:
    KEYBOARD_AVAILABLE = False

    def _start_keyboard_listener():
        pass

    def _reset_esc_flag():
        pass

    def _is_esc_pressed():
        return False

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

        # Initialize session metrics
        self.session_metrics = {
            'queries': 0,
            'total_time': 0.0,
            'start_time': time.time(),
            'responses': []
        }
        self.last_query_time = 0.0

        # Initialize prompt session with multiline by default
        self.prompt_session = self._create_prompt_session()

        # Track paste events
        self.paste_detected = False

    def _create_prompt_session(self) -> PromptSession:
        """Create prompt session with multiline input (Enter to submit, Escape+Enter for newline)"""
        # Create custom key bindings
        kb = KeyBindings()

        # Enter submits the input
        @kb.add('enter')
        def _(event):
            """Submit on Enter"""
            event.current_buffer.validate_and_handle()

        # Escape followed by Enter adds a newline
        @kb.add('escape', 'enter')
        def _(event):
            """Add newline on Escape+Enter"""
            event.current_buffer.insert_text('\n')

        # Ctrl+V paste detection and system clipboard access
        @kb.add('c-v')
        def _(event):
            """Detect paste event, check system clipboard for images, and paste text"""
            # Mark that a paste happened (for image detection)
            self.paste_detected = True

            # Get text from system clipboard using pyperclip
            if PYPERCLIP_AVAILABLE:
                try:
                    clipboard_text = pyperclip.paste()
                    if clipboard_text:
                        event.current_buffer.insert_text(clipboard_text)
                    # If no text but there's an image, that's fine - we'll detect it after
                except Exception:
                    # Fallback to prompt_toolkit's internal clipboard
                    try:
                        data = event.app.clipboard.get_data()
                        event.current_buffer.insert_text(data.text)
                    except:
                        pass  # Silent fail - no clipboard content
            else:
                # Fallback to prompt_toolkit's clipboard if pyperclip not available
                try:
                    data = event.app.clipboard.get_data()
                    event.current_buffer.insert_text(data.text)
                except:
                    pass

        return PromptSession(
            multiline=True,
            complete_while_typing=False,
            enable_history_search=False,
            mouse_support=False,
            prompt_continuation='... ',  # Show continuation on new lines
            key_bindings=kb
        )

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
                # Get user input with Alt+Enter support
                console.print()  # Add newline before prompt
                user_input = self.prompt_session.prompt(">>> ")

                if not user_input.strip():
                    continue

                # Check for multiline mode
                if user_input.strip() == '/multiline':
                    user_input = self._get_multiline_input()
                    if not user_input:
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

                # Check for images (clipboard or paths)
                image_paths = []

                # Check clipboard only if user pressed Ctrl+V (paste_detected flag)
                if self.paste_detected:
                    clipboard_image = self._check_clipboard_for_image()
                    if clipboard_image:
                        console.print(f"[green]📸 Image detected in clipboard → {clipboard_image}[/green]")
                        image_paths.append(clipboard_image)
                    # Reset the flag after checking
                    self.paste_detected = False

                # Check for image paths in text
                text_images = self._detect_image_paths(user_input)
                if text_images:
                    for img_path in text_images:
                        console.print(f"[green]📸 Image detected: {img_path}[/green]")
                        image_paths.append(img_path)

                # If images detected, check for vision model
                if image_paths:
                    vision_model = self._get_vision_model()
                    if vision_model:
                        console.print(f"[cyan]🔄 Switching to {vision_model} for vision support[/cyan]\n")
                        # Temporarily use vision model
                        original_model = self.model
                        self.model = vision_model
                        # Add images to input (Ollama vision format)
                        user_input = f"{user_input}\n\nImages to analyze: {', '.join(image_paths)}"
                    else:
                        console.print(f"[yellow]⚠️  No vision model found. Install with: ollama pull llava:7b[/yellow]\n")

                # Call Ollama
                response = self._call_ollama(system_prompt, user_input)

                # Restore original model if we switched
                if image_paths and vision_model:
                    self.model = original_model

                if response:
                    # Check for tool calls in response
                    tool_calls = self._parse_tool_calls(response)

                    if tool_calls:
                        # Execute tools
                        tool_results = self._execute_tools(tool_calls)

                        # Check if restart is required (self-improvement)
                        requires_restart = any(
                            r.metadata.get('requires_restart', False) for r in tool_results
                        )

                        # Format results and send back to model
                        tool_results_text = self._format_tool_results(tool_results)

                        # Continue conversation with tool results
                        # Use minimal prompt to focus on results, not old context
                        followup_prompt = f"""The tools you requested have been executed.

{tool_results_text}

Based on the above tool results, provide your complete response to the user's original question."""
                        response = self._call_ollama("", followup_prompt)

                        # Handle restart if needed
                        if requires_restart:
                            self._handle_restart()

                    if response:
                        # Display final response (strip out any remaining tool call markers)
                        clean_response = re.sub(r'TOOL_CALL:.*?ARGS:.*?\}', '', response, flags=re.DOTALL)
                        console.print()
                        console.print(Markdown(clean_response))

                        # Display timing
                        if hasattr(self, 'last_query_time') and self.last_query_time > 0:
                            console.print(f"\n[dim]⏱️  {self.last_query_time:.1f}s | {self.model}[/dim]")

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

        # Add self-improvement capability
        if hasattr(self.tool_registry, 'self_improver'):
            prompt_parts.append("""
## Self-Improvement Capability

You can improve your own code when you identify:
- Bugs in your implementation
- Performance optimizations
- Missing features that would be useful
- Better error handling
- Code quality improvements

Use the improve_self() tool:

```
TOOL_CALL: improve_self
ARGS: {
  "description": "Brief description of improvement",
  "reasoning": "5 Whys analysis:\\n1. Why L1: ...\\n2. Why L2: ...\\n3. Why L3: ...\\n4. Why L4: ...\\n5. Why L5: ...",
  "files": {
    "lib/session.py": "<complete new file content>",
    "lib/tools.py": "<complete new file content>"
  }
}
```

The improvement will be:
1. Automatically applied to your code
2. Logged in IMPROVEMENTS.md
3. Committed to git with [SELF-IMPROVEMENT] tag
4. Available immediately

**Be thoughtful:**
- Only improve when there's clear value
- Apply 5 Whys to justify the change
- Test mentally before applying
- Include complete file contents (not diffs)

**When to self-improve:**
- User reports a bug → Fix it immediately
- You encounter an error in your own code → Fix it
- You realize a feature is missing → Add it
- You find inefficient code → Optimize it
""")

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
        """Call Ollama with live timer, ESC interrupt, and progress indicator"""
        try:
            # Start keyboard listener and reset ESC flag
            if KEYBOARD_AVAILABLE:
                _start_keyboard_listener()
                _reset_esc_flag()

            # Combine system prompt with user input for first message
            # Ollama doesn't have system role, so we prepend it
            full_prompt = f"{system_prompt}\n\n---\n\nUser: {user_input}\n\nAssistant:"

            # Track timing
            start_time = time.time()

            # Start subprocess (non-blocking)
            process = subprocess.Popen(
                ['ollama', 'run', self.model, full_prompt],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Live display with timer and ESC detection
            with Live(console=console, refresh_per_second=4) as live:
                while process.poll() is None:
                    elapsed = int(time.time() - start_time)

                    # Update display with timer
                    display = Text()
                    display.append("🤔 Thinking... ", style="cyan")
                    display.append(f"{elapsed}s", style="yellow bold")
                    if KEYBOARD_AVAILABLE:
                        display.append(" (Press ESC to cancel)", style="dim")
                    live.update(display)

                    # Check for ESC key
                    if KEYBOARD_AVAILABLE and _is_esc_pressed():
                        console.print("\n\n[yellow]⚠️  Cancelled (ESC pressed)[/yellow]\n")
                        process.terminate()
                        try:
                            process.wait(timeout=2)
                        except:
                            process.kill()
                        _reset_esc_flag()  # Reset for next time
                        return None

                    time.sleep(0.25)

            # Get output
            stdout, stderr = process.communicate()
            elapsed = time.time() - start_time

            # Clear the live display
            console.print()

            if process.returncode == 0:
                response = stdout.strip()

                # Track metrics
                self.session_metrics['queries'] += 1
                self.session_metrics['total_time'] += elapsed
                self.session_metrics['responses'].append({
                    'duration': elapsed,
                    'timestamp': time.time()
                })
                self.last_query_time = elapsed

                return response
            else:
                console.print(f"[red]Ollama error: {stderr}[/red]")
                return None

        except FileNotFoundError:
            console.print("[red]Ollama not found. Is it installed?[/red]")
            return None
        except Exception as e:
            console.print(f"[red]Error calling Ollama: {e}[/red]")
            if os.getenv('DEBUG'):
                raise
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

        elif cmd == 'model':
            if args:
                # Import ConfigLoader to access validation methods
                from config import ConfigLoader
                config_loader = ConfigLoader()
                config_loader.config = self.config  # Use already loaded config

                # Resolve alias to model name
                resolved_model = config_loader.resolve_model_alias(args)

                # Validate model exists
                exists, available_models = config_loader.validate_model_exists(resolved_model)

                if exists:
                    self.model = resolved_model
                    self.session_data['model'] = resolved_model

                    # Show model info if it was an alias
                    model_info = config_loader.get_model_info(args)
                    if model_info:
                        console.print(f"\n[green]✓ Switched to {args}: {model_info.get('description', '')}[/green]")
                        console.print(f"[dim]Model: {resolved_model}[/dim]\n")
                    else:
                        console.print(f"\n[green]✓ Switched to model: {resolved_model}[/green]\n")
                else:
                    console.print(f"\n[yellow]⚠️  Model '{resolved_model}' not found[/yellow]")
                    console.print(f"[yellow]Available models:[/yellow]")
                    for m in available_models:
                        console.print(f"  - {m}")
                    console.print(f"\n[dim]Current model unchanged: {self.model}[/dim]\n")
            else:
                twin_config = self.config.get('twin_config', {})
                aliases = twin_config.get('model_aliases', {})
                console.print(f"\n[yellow]Usage: /model <alias or model-name>[/yellow]\n")
                console.print(f"[cyan]Model Aliases:[/cyan]")
                for alias_name, alias_info in aliases.items():
                    console.print(f"  [green]{alias_name:12}[/green] → {alias_info['model']:25} [dim]{alias_info.get('description', '')}[/dim]")
                console.print(f"\n[dim]Current model: {self.model}[/dim]\n")
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

        elif cmd == 'reload':
            self._reload_modules()
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
- `/multiline` - Enter multiline mode with line numbers (press Enter twice to submit)
- `/mode work|personal` - Switch between work and personal mode
- `/agent <name>` - Switch to a different agent
- `/model <alias>` - Switch model (fast/balanced/quality/reasoning or full name)
- `/context` - Show context summary
- `/save` - Manually save session checkpoint
- `/edit` - Transition to Aider for implementation
- `/reload` - Reload twin modules (after manual code changes)
- `/bye` - Save and exit session

**Input Mode:**
- **Press Enter** to submit your message
- **Press Escape then Enter** (Esc → Enter) to add a new line
- Use `/multiline` for numbered-line mode with line numbers (Enter twice to submit)

**Image Support:**
- Include image file paths in your message (e.g., `/path/to/image.png`)
- **Press Ctrl+V** to paste from clipboard (detects both text and images)
- Vision support requires a vision model (e.g., `ollama pull llava:7b`)

**Tips:**
- Ask planning questions naturally
- Agent will apply 5 Whys for major decisions
- Switch models mid-session: `/model balanced`
- Context is saved automatically on exit
- Twin auto-restarts after self-improvements
"""
        console.print(Markdown(help_text))

    def _save_session(self):
        """Save session to context file"""
        cwd = os.getcwd()
        self.context_manager.append_session(cwd, self.session_data)

        # Show session summary if had queries
        if self.session_metrics['queries'] > 0:
            total_duration = time.time() - self.session_metrics['start_time']
            avg_response = self.session_metrics['total_time'] / self.session_metrics['queries']

            console.print(f"""
[cyan]📊 Session Summary:[/cyan]
  Duration:     {int(total_duration//60)}m {int(total_duration%60)}s
  Queries:      {self.session_metrics['queries']}
  Avg response: {avg_response:.1f}s
  Agent:        {self.agent['name']}
  Mode:         {self.mode.upper()}
""")

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

    def _reload_modules(self):
        """Reload twin modules to get latest code changes"""
        import importlib
        
        console.print("\n[cyan]🔄 Reloading twin modules...[/cyan]\n")
        
        modules_to_reload = [
            'tools',
            'config', 
            'modes',
            'agents',
            'context',
            'self_improver'
        ]
        
        reloaded = []
        failed = []
        
        for module_name in modules_to_reload:
            try:
                if module_name in sys.modules:
                    module = sys.modules[module_name]
                    importlib.reload(module)
                    reloaded.append(module_name)
                    console.print(f"[green]✓ Reloaded {module_name}[/green]")
            except Exception as e:
                failed.append(f"{module_name}: {e}")
                console.print(f"[yellow]⚠ Failed to reload {module_name}: {e}[/yellow]")
        
        # Reinitialize tool registry
        if reloaded:
            try:
                from tools import ToolRegistry
                self.tool_registry = ToolRegistry(self.config)
                console.print(f"[green]✓ Tool registry reinitialized ({len(self.tool_registry.tools)} tools)[/green]")
            except Exception as e:
                console.print(f"[red]✗ Failed to reinitialize tools: {e}[/red]")
        
        console.print(f"\n[green]✅ Reload complete: {len(reloaded)} modules updated[/green]\n")
        
        if failed:
            console.print(f"[yellow]⚠ {len(failed)} modules failed to reload[/yellow]\n")

    def _handle_restart(self):
        """Handle restart after self-improvement"""
        console.print("\n[cyan]🔄 Twin improved itself! Restarting to load changes...[/cyan]")
        console.print("[dim]Your conversation context will be preserved[/dim]\n")
        
        # Save current session
        self._save_session()
        
        # Try hot reload first (faster, keeps context)
        try:
            self._reload_modules()
            console.print("[green]✅ Changes loaded successfully![/green]\n")
            console.print("[dim]You can continue your session normally[/dim]\n")
        except Exception as e:
            console.print(f"[yellow]⚠ Hot reload failed: {e}[/yellow]")
            console.print("[yellow]Please restart twin manually to use the improvements[/yellow]\n")

    def _get_multiline_input(self) -> str:
        """Get multiline input from user. Enter blank line to submit."""
        console.print("\n[cyan]📝 Multiline mode:[/cyan] [dim]Enter your text. Press Enter twice (blank line) to submit.[/dim]")

        if KEYBOARD_AVAILABLE:
            console.print("[dim]Press [bold]ESC[/bold] or type [bold]/cancel[/bold] to cancel.[/dim]\n")
            # Start keyboard listener and reset ESC flag
            _start_keyboard_listener()
            _reset_esc_flag()
        else:
            console.print("[dim]Type [bold]/cancel[/bold] on a line by itself to cancel.[/dim]\n")

        lines = []
        line_num = 1

        while True:
            try:
                # Check for ESC press before prompting
                if KEYBOARD_AVAILABLE and _is_esc_pressed():
                    console.print("[yellow]Cancelled (ESC pressed)[/yellow]\n")
                    _reset_esc_flag()
                    return ""

                # Show line number prompt
                line = Prompt.ask(f"[dim]{line_num:2d}|[/dim]", console=console, default="")

                # Check for ESC press after input (in case pressed during typing)
                if KEYBOARD_AVAILABLE and _is_esc_pressed():
                    console.print("[yellow]Cancelled (ESC pressed)[/yellow]\n")
                    _reset_esc_flag()
                    return ""

                # Check for /cancel command
                if line.strip() == '/cancel':
                    console.print("[yellow]Cancelled[/yellow]\n")
                    return ""

                # Empty line = submit
                if not line.strip() and lines:  # Need at least one line of content
                    break

                if line.strip():  # Only add non-empty lines
                    lines.append(line)
                    line_num += 1
                elif lines:  # Empty line after content = submit
                    break

            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Cancelled[/yellow]\n")
                if KEYBOARD_AVAILABLE:
                    _reset_esc_flag()
                return ""

        result = "\n".join(lines)
        console.print(f"\n[green]✓ Captured {len(lines)} lines ({len(result)} chars)[/green]\n")
        if KEYBOARD_AVAILABLE:
            _reset_esc_flag()
        return result

    def _check_clipboard_for_image(self) -> Optional[str]:
        """Check if clipboard contains an image, save to temp file"""
        try:
            from PIL import ImageGrab
            import tempfile

            image = ImageGrab.grabclipboard()
            if image:
                # Save to temp file
                temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False, dir='/tmp')
                image.save(temp_file.name)
                return temp_file.name
        except Exception as e:
            # Silently fail if clipboard check doesn't work
            pass
        return None

    def _detect_image_paths(self, text: str) -> list[str]:
        """Detect image file paths in user input"""
        import re
        
        # Common image extensions
        image_pattern = r'([^\s]+\.(?:png|jpg|jpeg|gif|bmp|webp|svg))'
        matches = re.findall(image_pattern, text, re.IGNORECASE)
        
        # Verify files exist
        valid_paths = []
        for match in matches:
            path = Path(match).expanduser()
            if path.exists() and path.is_file():
                valid_paths.append(str(path))
        
        return valid_paths

    def _get_vision_model(self) -> Optional[str]:
        """Get available vision model from ollama"""
        try:
            result = subprocess.run(
                ['ollama', 'list'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                # Check for vision models
                vision_models = ['llava', 'bakllava', 'llava-phi3', 'llava:7b', 'llava:13b']
                for model in vision_models:
                    if model in result.stdout:
                        return model
        except:
            pass
        return None
