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
from rich.prompt import Prompt, Confirm
from rich.spinner import Spinner
from rich.live import Live
from rich.text import Text

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.clipboard import ClipboardData
from prompt_toolkit.input.ansi_escape_sequences import ANSI_SEQUENCES
from prompt_toolkit.keys import Keys

# CSI u keyboard protocol support for Shift+Enter
# This allows iTerm2 and other modern terminals to send disambiguated key events
# Shift+Enter: \x1b[13;2u where 13 = Enter keycode, 2 = Shift modifier
# We map it to 'c-m' which is technically Ctrl+M (Enter's control code)
# but with modifier information that prompt_toolkit can't normally see
# The actual handling will be done by checking for this specific sequence
ANSI_SEQUENCES['\x1b[13;2u'] = 'c-j'  # Map to a control sequence we can intercept

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
        # Static system messages are always included (prompts + prior summaries)
        self.static_system_messages: List[Dict[str, Any]] = []
        # Full message buffer for chat-based calls
        self.messages: List[Dict[str, Any]] = []
        self.running_summary: str = ""
        self.env_context: str = ""
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

        # Track pasted images for vision support
        self.pasted_images = []  # List of {'id': N, 'path': '/tmp/...', 'placeholder': '[Image #N]'}
        self.image_counter = 0

    def _create_prompt_session(self) -> PromptSession:
        """Create prompt session with multiline input (Enter to submit, Shift+Enter for newline)"""
        # Create custom key bindings
        kb = KeyBindings()

        # Enter submits the input
        @kb.add('enter')
        def _(event):
            """Submit on Enter"""
            event.current_buffer.validate_and_handle()

        # Shift+Enter adds a newline (requires terminal setup - see /terminal-setup)
        # We map Shift+Enter to Ctrl+J, which we intercept here
        @kb.add('c-j')
        def _(event):
            """Add newline on Shift+Enter (CSI u protocol mapped to Ctrl+J)"""
            event.current_buffer.insert_text('\n')

        # Escape followed by Enter adds a newline (fallback for terminals without CSI u)
        @kb.add('escape', 'enter')
        def _(event):
            """Add newline on Escape+Enter (fallback)"""
            event.current_buffer.insert_text('\n')

        # Ctrl+V paste - check for images first, then text
        @kb.add('c-v')
        def _(event):
            """Detect paste event, check clipboard for images (insert placeholder) or text"""
            # First, check if clipboard contains an image
            clipboard_image = self._check_clipboard_for_image()

            if clipboard_image:
                # Found an image - add placeholder and track it
                self.image_counter += 1
                placeholder = f"[Image #{self.image_counter}]"

                self.pasted_images.append({
                    'id': self.image_counter,
                    'path': clipboard_image,
                    'placeholder': placeholder
                })

                # Insert placeholder into buffer
                event.current_buffer.insert_text(placeholder)

                # Show feedback
                console.print(f"[green]📸 {placeholder} pasted[/green]")
            else:
                # No image, paste text normally
                if PYPERCLIP_AVAILABLE:
                    try:
                        clipboard_text = pyperclip.paste()
                        if clipboard_text:
                            event.current_buffer.insert_text(clipboard_text)
                    except Exception:
                        # Fallback to prompt_toolkit's internal clipboard
                        try:
                            data = event.app.clipboard.get_data()
                            event.current_buffer.insert_text(data.text)
                        except:
                            pass  # Silent fail
                else:
                    # Fallback to prompt_toolkit's clipboard
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

        # Build environment context snapshot (cwd, git, readme, files)
        self.env_context = self._build_env_context(cwd)

        # Build system prompt
        system_prompt = self._build_system_prompt()

        # Seed message buffers
        self.static_system_messages = [{'role': 'system', 'content': system_prompt}]

        prior_context_summary = self._build_prior_context_summary(cwd)
        if prior_context_summary:
            self.static_system_messages.append({
                'role': 'system',
                'content': f"Prior context summary:\n{prior_context_summary}"
            })

        self.messages = list(self.static_system_messages)

        # Handle non-interactive (piped) mode as one-shot
        if not sys.stdin.isatty():
            user_input = sys.stdin.read().strip()
            if not user_input:
                console.print("[yellow]⚠️  No input provided on stdin. Provide a prompt via piping.[/yellow]")
                return

            # Track conversation textually for saving
            self.session_data['planning_discussion'] += f"\n{user_input}\n"

            augmented = self._augment_with_env(user_input)
            augmented = self._augment_with_tools(augmented)

            response = self._call_ollama(augmented)
            if response:
                console.print()
                console.print(Markdown(response))
                self.session_data['planning_discussion'] += f"\n{response}\n"
                self._save_session()
            return

        # Main loop
        current = self
        while True:
            try:
                # Get user input with Alt+Enter support
                console.print()  # Add newline before prompt
                user_input = current.prompt_session.prompt(">>> ")

                if not user_input.strip():
                    continue

                # Check for multiline mode
                if user_input.strip() == '/multiline':
                    user_input = current._get_multiline_input()
                    if not user_input:
                        continue

                # Handle commands
                if user_input.startswith('/'):
                    result = current._handle_command(user_input.strip())
                    if result == 'exit':
                        break
                    elif result == 'continue':
                        continue
                    elif isinstance(result, SessionOrchestrator):
                        # Swap orchestrator instance and continue loop
                        current = result
                        continue
                    # Otherwise continue to process as regular input

                # Track conversation textually for saved context
                current.session_data['planning_discussion'] += f"\n{user_input}\n"

                # Check for images (from pasted placeholders or file paths in text)
                image_paths = []

                # Check for pasted images (from Ctrl+V)
                if current.pasted_images:
                    image_paths = [img['path'] for img in current.pasted_images]
                    console.print(f"[green]📸 Sending {len(image_paths)} image(s) with your message[/green]")

                # Check for image file paths mentioned in text
                text_images = current._detect_image_paths(user_input)
                if text_images:
                    for img_path in text_images:
                        console.print(f"[green]📸 Image path detected: {img_path}[/green]")
                        image_paths.append(img_path)

                # If images detected, check for vision model and prepare to use it
                vision_model = None
                if image_paths:
                    vision_model = self._get_vision_model()
                    if vision_model:
                        console.print(f"[cyan]🔄 Using {vision_model} for vision support[/cyan]\n")
                    else:
                        console.print(f"[yellow]⚠️  No vision model found. Install with: ollama pull llava:7b[/yellow]\n")
                        image_paths = []  # Can't use images without vision model

                # Auto-augment with env and tool context
                augmented_input = current._augment_with_env(user_input)
                augmented_input = current._augment_with_tools(augmented_input)

                # Call Ollama (with images if present)
                response = current._call_ollama(augmented_input, image_paths, vision_model)

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
                        response = self._call_ollama(followup_prompt)

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

        # Add environment context (cwd, git, files, README)
        if self.env_context:
            prompt_parts.append(f"\n\nEnvironment Context:\n{self.env_context}")

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

**Environment awareness:**
- You are running from the working directory shown in Environment Context.
- When asked about current directory, files, or project purpose, use Environment Context first; if more detail is needed, call `bash`/`glob`/`read` to inspect.
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

    def _call_ollama(self, user_input: str, images: Optional[List[str]] = None, vision_model: Optional[str] = None) -> Optional[str]:
        """Call Ollama with live timer, ESC interrupt, optional image support, and full history"""
        try:
            # Start keyboard listener and reset ESC flag
            if KEYBOARD_AVAILABLE:
                _start_keyboard_listener()
                _reset_esc_flag()

            # Track timing
            start_time = time.time()

            # Compact history if needed before adding new turn
            self._maybe_compact_messages()

            # Build user message
            user_message: Dict[str, Any] = {'role': 'user', 'content': user_input}
            if images:
                user_message['images'] = images

            # Build final message list for this call (do not mutate yet)
            messages_for_call = list(self.messages) + [user_message]

            # Build Ollama options from config
            options = self._build_ollama_options()

            # Choose model for this call (vision override if needed)
            model_name = vision_model if (images and vision_model) else self.model

            # Use Ollama Python library for chat (supports streaming and images)
            import ollama as ollama_lib
            import threading  # ensure available for timer

            # Show live elapsed timer while thinking
            stop_timer = False

            def _timer():
                with Live(console=console, refresh_per_second=4) as live:
                    while not stop_timer:
                        elapsed_sec = int(time.time() - start_time)
                        display = Text()
                        display.append("🤔 Thinking... ", style="cyan")
                        display.append(f"{elapsed_sec}s", style="yellow bold")
                        display.append(" (Ctrl+C to cancel)", style="dim")
                        live.update(display)
                        time.sleep(1)

            timer_thread = threading.Thread(target=_timer, daemon=True)
            timer_thread.start()

            try:
                response_text = ollama_lib.chat(
                    model=model_name,
                    messages=messages_for_call,
                    options=options
                )
            finally:
                stop_timer = True
                timer_thread.join(timeout=2)
                console.print()

            elapsed = time.time() - start_time

            # Extract response text
            assistant_reply = response_text['message']['content']

            # Track metrics
            self.session_metrics['queries'] += 1
            self.session_metrics['total_time'] += elapsed
            self.session_metrics['responses'].append({
                'duration': elapsed,
                'timestamp': time.time()
            })
            self.last_query_time = elapsed

            # Clear pasted images after sending
            if self.pasted_images:
                self.pasted_images = []

            # Persist messages to buffer for next turn
            self.messages.append(user_message)
            self.messages.append({'role': 'assistant', 'content': assistant_reply})

            return assistant_reply

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

        elif cmd == 'ctx':
            if args:
                try:
                    num_ctx = int(args)
                    if num_ctx < 512:
                        console.print("[yellow]⚠️  num_ctx too small; set >= 512[/yellow]\n")
                        return 'continue'
                    # Update in twin_config for this session
                    self.config.setdefault('twin_config', {}).setdefault('generation_params', {})['num_ctx'] = num_ctx
                    console.print(f"[green]✓ Set num_ctx to {num_ctx}[/green]\n")
                except ValueError:
                    console.print("[yellow]Usage: /ctx <num_ctx>[/yellow]\n")
            else:
                gp = self.config.get('twin_config', {}).get('generation_params', {})
                console.print(f"\n[cyan]Current num_ctx:[/cyan] {gp.get('num_ctx', 'default')}\n")
            return 'continue'

        elif cmd == 'temp':
            if args:
                try:
                    temp = float(args)
                    if temp < 0 or temp > 1.5:
                        console.print("[yellow]⚠️  temp out of expected range (0..1.5)[/yellow]\n")
                        return 'continue'
                    self.config.setdefault('twin_config', {}).setdefault('generation_params', {})['temperature'] = temp
                    console.print(f"[green]✓ Set temperature to {temp}[/green]\n")
                except ValueError:
                    console.print("[yellow]Usage: /temp <value>[/yellow]\n")
            else:
                gp = self.config.get('twin_config', {}).get('generation_params', {})
                console.print(f"\n[cyan]Current temperature:[/cyan] {gp.get('temperature', 'default')}\n")
            return 'continue'

        elif cmd == 'context':
            summary = self.context_manager.get_context_summary(os.getcwd())
            console.print(f"\n[cyan]{summary}[/cyan]\n")
            return 'continue'

        elif cmd == 'env':
            console.print("\n[cyan]Environment Context:[/cyan]")
            console.print(self.env_context or "No environment context available")
            console.print()
            return 'continue'

        elif cmd == 'sessions':
            # Parse subcommand
            subparts = args.split(maxsplit=1) if args else []
            subcmd = subparts[0].lower() if subparts else 'list'
            subargs = subparts[1] if len(subparts) > 1 else ""

            if subcmd == 'list' or not subcmd:
                self._list_sessions_verbose()
            elif subcmd == 'show':
                try:
                    index = int(subargs)
                    self._show_session(index)
                except ValueError:
                    console.print("\n[yellow]Usage: /sessions show <number>[/yellow]\n")
            elif subcmd == 'delete':
                try:
                    index = int(subargs)
                    self._delete_session(index)
                except ValueError:
                    console.print("\n[yellow]Usage: /sessions delete <number>[/yellow]\n")
            elif subcmd == 'clear':
                self._clear_sessions()
            elif subcmd == 'resume':
                try:
                    index = int(subargs)
                    self._resume_session(index)
                except ValueError:
                    console.print("\n[yellow]Usage: /sessions resume <number>[/yellow]\n")
            else:
                console.print(f"\n[yellow]Unknown subcommand: {subcmd}[/yellow]")
                console.print("[dim]Available: list, show, delete, resume, clear[/dim]\n")

            return 'continue'

        elif cmd == 'save':
            self._save_session()
            console.print(f"\n[green]✓ Session saved[/green]\n")
            return 'continue'

        elif cmd == 'edit':
            self._transition_to_aider()
            return 'continue'

        elif cmd == 'reload':
            replacement = self._reload_modules()
            if replacement:
                # Return a sentinel to instruct caller to swap orchestrator
                return replacement
            return 'continue'

        elif cmd == 'terminal-setup':
            self._setup_terminal()
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
- `/terminal-setup` - Configure your terminal for Shift+Enter support
- `/sessions` - List all sessions (or /sessions list)
- `/sessions show <N>` - View specific session content
- `/sessions delete <N>` - Delete specific session
- `/sessions clear` - Delete all sessions (with archive)
- `/multiline` - Enter multiline mode with line numbers (press Enter twice to submit)
- `/mode work|personal` - Switch between work and personal mode
- `/agent <name>` - Switch to a different agent
- `/model <alias>` - Switch model (fast/balanced/quality/reasoning or full name)
- `/context` - Show context summary
- `/ctx <num>` - Set num_ctx for this session (context window)
- `/temp <value>` - Set temperature for this session
- `/env` - Show current working directory, git info, README summary, and top files
- `/save` - Manually save session checkpoint
- `/edit` - Transition to Aider for implementation
- `/reload` - Reload twin modules (after manual code changes)
- `/bye` - Save and exit session

**Input Mode:**
- **Press Enter** to submit your message
- **Press Shift+Enter** to add a new line (requires `/terminal-setup` first)
- **Press Escape then Enter** (Esc → Enter) also adds new line (fallback)
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
        # Persist running summary if available
        if self.running_summary and 'reasoning' in self.session_data:
            self.session_data['reasoning'] = f"Running summary:\n{self.running_summary}"
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

        # Refresh environment context snapshot after reload
        try:
            self.env_context = self._build_env_context(os.getcwd())
            console.print(f"[green]✓ Environment context refreshed[/green]")
        except Exception as e:
            console.print(f"[yellow]⚠ Failed to refresh environment context: {e}[/yellow]")
        
        console.print(f"\n[green]✅ Reload complete: {len(reloaded)} modules updated[/green]\n")
        
        if failed:
            console.print(f"[yellow]⚠ {len(failed)} modules failed to reload[/yellow]\n")

        # Attempt to rebuild SessionOrchestrator from reloaded module and migrate state
        try:
            import session as session_module
            NewOrchestrator = session_module.SessionOrchestrator
            if NewOrchestrator is self.__class__:
                # Already current class, nothing to swap
                return None

            # Snapshot current state to transfer
            state = {
                'mode': self.mode,
                'agent': self.agent,
                'context': self.context,
                'model': self.model,
                'session_id': self.session_id,
                'session_data': self.session_data,
                'messages': self.messages,
                'static_system_messages': self.static_system_messages,
                'running_summary': self.running_summary,
                'env_context': self.env_context,
                'tool_registry': self.tool_registry,
                'session_metrics': self.session_metrics,
                'last_query_time': self.last_query_time,
                'prompt_session': self.prompt_session,
                'pasted_images': self.pasted_images,
                'image_counter': self.image_counter,
            }

            # Build new instance
            new_instance = NewOrchestrator(
                config=self.config,
                mode=self.mode,
                agent=self.agent,
                context=self.context,
                model=self.model,
                agent_loader=self.agent_loader,
                mode_detector=self.mode_detector,
                context_manager=self.context_manager
            )

            # Restore state
            new_instance.session_id = state['session_id']
            new_instance.session_data = state['session_data']
            new_instance.messages = state['messages']
            new_instance.static_system_messages = state['static_system_messages']
            new_instance.running_summary = state['running_summary']
            new_instance.env_context = state['env_context']
            new_instance.tool_registry = state['tool_registry']
            new_instance.session_metrics = state['session_metrics']
            new_instance.last_query_time = state['last_query_time']
            new_instance.prompt_session = state['prompt_session']
            new_instance.pasted_images = state['pasted_images']
            new_instance.image_counter = state['image_counter']

            console.print("[green]✓ Swapped to reloaded SessionOrchestrator (state migrated)[/green]")
            return new_instance
        except Exception as e:
            console.print(f"[yellow]⚠ Failed to hot-swap SessionOrchestrator: {e}[/yellow]")
            return None

    def _setup_terminal(self):
        """Configure terminal for Shift+Enter support"""
        console.print("\n[cyan]🔧 Terminal Setup for Shift+Enter[/cyan]\n")

        # Detect terminal type
        term_program = os.getenv('TERM_PROGRAM', '')
        term = os.getenv('TERM', '')

        if term_program == 'iTerm.app':
            console.print("[green]✓ Detected iTerm2[/green]\n")
            self._setup_iterm2()
        elif 'kitty' in term:
            console.print("[green]✓ Detected Kitty terminal[/green]")
            console.print("[dim]Kitty natively supports CSI u protocol - Shift+Enter should work![/dim]\n")
        elif 'wezterm' in term_program.lower():
            console.print("[green]✓ Detected WezTerm[/green]")
            console.print("[dim]WezTerm natively supports CSI u protocol - Shift+Enter should work![/dim]\n")
        elif term_program == 'Apple_Terminal':
            console.print("[yellow]⚠️  Detected Apple Terminal[/yellow]")
            console.print("[dim]Terminal.app has limited key mapping support.[/dim]")
            console.print("[dim]Consider using iTerm2 for full Shift+Enter support.[/dim]\n")
            self._show_manual_instructions()
        else:
            console.print(f"[yellow]⚠️  Terminal not recognized: {term_program or term}[/yellow]")
            console.print("[dim]Showing manual setup instructions...[/dim]\n")
            self._show_manual_instructions()

    def _setup_iterm2(self):
        """Configure iTerm2 for Shift+Enter"""
        console.print("[cyan]Configuring iTerm2 key bindings...[/cyan]")

        try:
            # Use defaults command to configure iTerm2 GlobalKeyMap
            # Key format: "0xd-0x20000" where 0xd = Enter, 0x20000 = Shift modifier
            cmd = [
                'defaults', 'write', 'com.googlecode.iterm2',
                'GlobalKeyMap', '-dict-add', '0xd-0x20000',
                '<dict><key>Action</key><integer>10</integer><key>Text</key><string>[13;2u</string></dict>'
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                console.print("[green]✅ iTerm2 configured successfully![/green]\n")
                console.print("[yellow]⚠️  Important: You must restart iTerm2 for changes to take effect[/yellow]")
                console.print("[dim]   Close all iTerm2 windows and reopen[/dim]\n")
                console.print("[green]After restart, Shift+Enter will add newlines[/green]")
                console.print("[dim]   • Press Enter to submit[/dim]")
                console.print("[dim]   • Press Shift+Enter to add new line[/dim]")
                console.print("[dim]   • Escape+Enter also works as fallback[/dim]\n")
            else:
                console.print(f"[red]✗ Configuration failed: {result.stderr}[/red]\n")
                self._show_manual_instructions()

        except Exception as e:
            console.print(f"[red]✗ Error configuring iTerm2: {e}[/red]\n")
            self._show_manual_instructions()

    def _show_manual_instructions(self):
        """Show manual setup instructions for iTerm2"""
        instructions = """
[cyan]**Manual Setup Instructions for iTerm2:**[/cyan]

1. Open iTerm2 → **Settings** (Cmd+,)
2. Go to **Profiles** → **Keys** → **Key Mappings**
3. Click **+** to add a new key mapping
4. Press **Shift+Enter** when prompted for keyboard shortcut
5. In the dropdown, select **"Send Escape Sequence"**
6. In the text field, enter: `[13;2u`
7. Click **OK**
8. Restart iTerm2

[green]After setup, Shift+Enter will add newlines[/green]
"""
        console.print(Markdown(instructions))

    def _list_sessions_verbose(self):
        """Display verbose list of all sessions"""
        cwd = os.getcwd()
        sessions = self.context_manager.list_sessions_verbose(cwd)

        if not sessions:
            console.print("\n[yellow]No sessions found[/yellow]\n")
            return

        total_lines = sum(s['line_count'] for s in sessions)

        console.print(f"\n[cyan]📂 Context Sessions for:[/cyan] [dim]{cwd}[/dim]")
        console.print(f"[cyan]Found {len(sessions)} session(s) ({total_lines} lines total)[/cyan]\n")

        for s in sessions:
            mode_color = "cyan" if s['mode'] == 'work' else "green"
            console.print(f"[bold]{s['index']:2d}.[/bold] [{mode_color}][{s['timestamp']}][/{mode_color}] [{mode_color}]{s['mode'].upper()} MODE[/{mode_color}] [dim]({s['line_count']} lines)[/dim]")
            console.print(f"    [yellow]Agent:[/yellow] {s['agent']}")
            console.print(f"    [dim]Topic: {s['topic']}[/dim]\n")

        console.print("[dim]Commands:[/dim]")
        console.print("[dim]  /sessions show <num> - View full session content[/dim]")
        console.print("[dim]  /sessions delete <num> - Delete specific session[/dim]")
        console.print("[dim]  /sessions resume <num> - Inject prior session context into this run[/dim]")
        console.print("[dim]  /sessions clear - Delete all sessions[/dim]\n")

    def _show_session(self, index: int):
        """Display full content of specific session"""
        cwd = os.getcwd()
        session = self.context_manager.get_session_by_index(cwd, index)

        if not session:
            console.print(f"\n[red]Session #{index} not found[/red]\n")
            return

        console.print(f"\n[cyan]Session #{index}: {session['timestamp']} [{session['mode'].upper()} MODE][/cyan]\n")
        console.print(Panel(session['content'], border_style="dim"))
        console.print()

    def _delete_session(self, index: int):
        """Delete specific session with confirmation"""
        cwd = os.getcwd()
        session = self.context_manager.get_session_by_index(cwd, index)

        if not session:
            console.print(f"\n[red]Session #{index} not found[/red]\n")
            return

        # Show what will be deleted
        console.print(f"\n[yellow]⚠️  Delete session #{index}?[/yellow]")
        console.print(f"[dim]Timestamp: {session['timestamp']}[/dim]")
        console.print(f"[dim]Mode: {session['mode'].title()}[/dim]")

        # Show topic preview
        topic = session.get('topic', '')
        if topic:
            console.print(f"[dim]Topic: {topic}[/dim]")

        console.print()

        # Confirmation
        if Confirm.ask("Delete this session?", default=False):
            success = self.context_manager.delete_session_by_index(cwd, index)
            if success:
                console.print("[green]✅ Session deleted[/green]\n")
            else:
                console.print("[red]Failed to delete session[/red]\n")
        else:
            console.print("[yellow]Cancelled[/yellow]\n")

    def _clear_sessions(self):
        """Clear all sessions with confirmation and archiving"""
        cwd = os.getcwd()
        context = self.context_manager.load_context(cwd)

        if not context:
            console.print("\n[yellow]No sessions to clear[/yellow]\n")
            return

        sessions = context.get('sessions', [])
        session_count = len(sessions)
        line_count = len(context['raw_content'].split('\n'))

        # Show warning
        console.print(f"\n[red bold]⚠️  DELETE ALL SESSIONS?[/red bold]")
        console.print(f"[yellow]This will delete {session_count} session(s) ({line_count} lines)[/yellow]")
        console.print(f"[yellow]Sessions will be archived before deletion[/yellow]\n")

        # Confirmation
        if Confirm.ask("Are you sure?", default=False):
            success, archive_path = self.context_manager.clear_context_with_archive(cwd)
            if success:
                console.print(f"[green]✅ Cleared {session_count} sessions[/green]")
                if archive_path:
                    console.print(f"[dim]📦 Archived to: {archive_path}[/dim]\n")
            else:
                console.print("[red]Failed to clear sessions[/red]\n")
        else:
            console.print("[yellow]Cancelled[/yellow]\n")

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

    def _resume_session(self, index: int):
        """Inject a prior session's content into the current conversation"""
        cwd = os.getcwd()
        session = self.context_manager.get_session_by_index(cwd, index)

        if not session:
            console.print(f"\n[red]Session #{index} not found[/red]\n")
            return

        content = session.get('content', '')
        stamp = session.get('timestamp', 'unknown')
        mode = session.get('mode', 'personal')
        topic = session.get('topic') or self._extract_topic_from_session_content(content)

        planning_match = re.search(r'### Planning Discussion\n(.+?)(?=\n###|\Z)', content, re.DOTALL)
        planning_block = planning_match.group(1).strip() if planning_match else ""

        # Build a concise summary
        summary_lines = [
            f"Resuming from session #{index} ({stamp}, {mode} mode).",
            f"Topic: {topic}" if topic else "Topic: (unknown)"
        ]
        if planning_block:
            summary_lines.append("Planning discussion summary:")
            summary_lines.append(self._summarize_text(planning_block, max_chars=1200))
        else:
            summary_lines.append("Planning discussion summary: (not found)")

        truncated = self._summarize_text(content, max_chars=2000) if content else "(no content)"
        summary_lines.append("Excerpt:")
        summary_lines.append(truncated)

        resume_message = {
            'role': 'system',
            'content': "\n".join(summary_lines)
        }

        # Persist into static system messages and current buffer
        self.static_system_messages.append(resume_message)
        self.messages.append(resume_message)
        self.running_summary = "\n".join(summary_lines)
        self.session_data['reasoning'] = self.running_summary

        # Track in session data
        self.session_data['planning_discussion'] += f"\n[Resumed session #{index}]\n"

        console.print(f"\n[green]✓ Injected session #{index} into current context[/green]\n")

    def _augment_with_env(self, user_input: str) -> str:
        """Auto-append environment snapshot when the user asks about cwd/files/project"""
        lowered = user_input.lower()
        triggers = [
            "what directory", "current directory", "pwd", "where am i",
            "what files", "list files", "show files", "what's here",
            "what is this project about", "what's this project about",
            "project about", "what repository"
        ]
        if not any(t in lowered for t in triggers):
            return user_input

        info = self.env_context or self._build_env_context(os.getcwd())
        console.print("[dim]↪ Injecting environment context for this question[/dim]")
        return f"{user_input}\n\n[Auto context]\n{info}"

    def _augment_with_tools(self, user_input: str) -> str:
        """Auto-run lightweight tools (pwd/ls/readme) for common env/file intents"""
        lowered = user_input.lower()
        intents = []
        context_blocks = []

        def add_block(title: str, content: str):
            context_blocks.append(f"{title}:\n{content}")

        try:
            # Intent: current directory
            if any(k in lowered for k in ["what directory", "current directory", "pwd", "where am i"]):
                tool = self.tool_registry.get("bash")
                if tool:
                    res = tool.execute(command="pwd")
                    if res.success and res.output:
                        add_block("pwd", res.output.strip())

            # Intent: list files
            if any(k in lowered for k in ["what files", "list files", "show files", "what's here", "ls"]):
                tool = self.tool_registry.get("bash")
                if tool:
                    res = tool.execute(command="ls -1 | head -n 50")
                    if res.success and res.output:
                        add_block("ls (top 50)", res.output.strip())

            # Intent: project about / README
            if any(k in lowered for k in ["what is this project about", "project about", "readme", "project summary"]):
                readme = None
                for name in ["README.md", "README"]:
                    candidate = Path(os.getcwd()) / name
                    if candidate.exists():
                        readme = candidate
                        break
                if readme:
                    try:
                        text = readme.read_text(errors='ignore')
                        summary = self._summarize_text(text, max_chars=1000)
                        add_block(f"README ({readme.name})", summary)
                    except Exception:
                        pass
        except Exception:
            # Fail silently; do not block main flow
            pass

        if not context_blocks:
            return user_input

        console.print("[dim]↪ Added tool context (pwd/ls/readme) for this question[/dim]")
        return f"{user_input}\n\n[Tool context]\n" + "\n\n".join(context_blocks)

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

    def _build_env_context(self, cwd: str) -> str:
        """Construct an environment snapshot for the system prompt"""
        parts = []

        # CWD and basic listing
        parts.append(f"CWD: {cwd}")

        try:
            entries = sorted(os.listdir(cwd))[:20]
            parts.append("Top-level entries (max 20): " + ", ".join(entries))
        except Exception as e:
            parts.append(f"Top-level entries: <error: {e}>")

        # Git info if available
        try:
            git_root = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=cwd, text=True).strip()
            branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=cwd, text=True).strip()
            status = subprocess.check_output(['git', 'status', '--short'], cwd=cwd, text=True).strip()
            status_display = status if status else "clean"
            parts.append(f"Git repo: {git_root}")
            parts.append(f"Branch: {branch}, Status: {status_display}")
        except Exception:
            parts.append("Git: not a repository or unavailable")

        # README summary if present
        readme_path = None
        for name in ["README.md", "README"]:
            candidate = Path(cwd) / name
            if candidate.exists():
                readme_path = candidate
                break
        if readme_path:
            try:
                text = readme_path.read_text(errors='ignore')
                summary = self._summarize_text(text, max_chars=800)
                parts.append(f"README summary ({readme_path.name}):\n{summary}")
            except Exception as e:
                parts.append(f"README summary error: {e}")

        return "\n".join(parts)

    def _build_prior_context_summary(self, cwd: str) -> str:
        """Summarize recent sessions for initial system message"""
        recent_sessions = self.context_manager.get_recent_sessions(cwd, count=2) or []
        if not recent_sessions:
            return ""

        parts = []
        for session in recent_sessions:
            topic = self._extract_topic_from_session_content(session.get('content', ''))
            parts.append(f"- {session.get('timestamp', '')}: {topic}")

        summary = "\n".join(parts)
        return summary[:800] + ("..." if len(summary) > 800 else "")

    def _extract_topic_from_session_content(self, content: str) -> str:
        """Lightweight topic extraction (first non-empty line of planning discussion)"""
        planning_match = re.search(r'### Planning Discussion\n(.+?)(?=\n###|\Z)', content, re.DOTALL)
        if planning_match:
            line = planning_match.group(1).strip().split('\n')[0]
            return line[:120] + ("..." if len(line) > 120 else "")
        # Fallback to first non-empty line
        for line in content.splitlines():
            clean = line.strip()
            if clean:
                return clean[:120] + ("..." if len(clean) > 120 else "")
        return "(no topic)"

    def _build_ollama_options(self) -> Dict[str, Any]:
        """Build Ollama generation options from config"""
        twin_config = self.config.get('twin_config', {})
        generation_params = twin_config.get('generation_params', {})
        ollama_cfg = twin_config.get('ollama', {})

        options: Dict[str, Any] = {}
        if 'temperature' in generation_params:
            options['temperature'] = generation_params['temperature']
        if 'top_p' in generation_params:
            options['top_p'] = generation_params['top_p']
        if 'num_ctx' in generation_params:
            options['num_ctx'] = generation_params['num_ctx']
        elif 'context_window' in ollama_cfg:
            options['num_ctx'] = ollama_cfg['context_window']
        if 'keep_alive' in ollama_cfg:
            options['keep_alive'] = ollama_cfg['keep_alive']

        return options

    def _estimate_char_count(self, messages: List[Dict[str, Any]]) -> int:
        """Approximate size of the conversation in characters"""
        return sum(len(m.get('content', '')) for m in messages)

    def _summarize_text(self, text: str, max_chars: int = 800, max_items: int = 6) -> str:
        """Deterministic bulletized summarization to keep context concise"""
        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        bullets = []
        total = 0
        for sent in sentences:
            s = sent.strip()
            if not s:
                continue
            # Truncate long sentences
            if len(s) > 200:
                s = s[:200] + "..."
            candidate_len = total + len(s) + 3  # account for "- "
            if candidate_len > max_chars or len(bullets) >= max_items:
                break
            bullets.append(f"- {s}")
            total = candidate_len

        if bullets:
            summary = "\n".join(bullets)
            return summary[:max_chars]

        # Fallback to trimmed lines if no sentences found
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            return ""
        summary = "\n".join(lines[:max_items])
        return summary[:max_chars] + ("..." if len(summary) > max_chars else "")

    def _maybe_compact_messages(self) -> None:
        """Compact conversation into a running summary when nearing context limits"""
        twin_config = self.config.get('twin_config', {})
        ollama_cfg = twin_config.get('ollama', {})
        generation_params = twin_config.get('generation_params', {})

        num_ctx = generation_params.get('num_ctx') or ollama_cfg.get('context_window', 32768)
        max_chars = int(num_ctx * 4)  # rough character budget
        compact_threshold = int(max_chars * 0.7)

        current_chars = self._estimate_char_count(self.messages)
        if current_chars <= compact_threshold:
            return

        # Protect the most recent messages (last 6)
        protected = 6
        static_len = len(self.static_system_messages)
        if len(self.messages) <= static_len + protected:
            return

        dynamic_messages = self.messages[static_len:]
        old_messages = dynamic_messages[:-protected]
        recent_messages = dynamic_messages[-protected:]

        combined_text = "\n".join(m.get('content', '') for m in old_messages)
        summary_text = self._summarize_text(combined_text, max_chars=1000)

        if summary_text:
            summary_message = {
                'role': 'system',
                'content': f"Conversation so far (summarized):\n{summary_text}"
            }
            # Update running summary for saving
            self.running_summary = summary_text
            # Rebuild messages: static + summary + recent
            self.messages = list(self.static_system_messages) + [summary_message] + recent_messages
