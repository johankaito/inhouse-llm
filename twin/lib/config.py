"""
Configuration loader for twin
Reads ~/.claude/ configuration files
"""

import json
import yaml
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


class ConfigLoader:
    """Load configuration from ~/.claude/"""

    def __init__(self):
        self.claude_dir = Path.home() / ".claude"
        self.twin_dir = Path(__file__).parent.parent
        self.config = {}

    def load_all(self) -> Dict[str, Any]:
        """Load all configuration files"""
        self.config = {
            'claude_md': self.load_claude_md(),
            'settings': self.load_settings(),
            'mode_config': self.load_mode_config(),
            'twin_config': self.load_twin_config(),
            'agent_dir': str(self.claude_dir / "agents"),
            'context_dir': str(self.claude_dir / "context"),
        }
        return self.config

    def load_claude_md(self) -> str:
        """Load CLAUDE.md master configuration"""
        claude_md_path = self.claude_dir / "CLAUDE.md"
        if claude_md_path.exists():
            return claude_md_path.read_text()
        return ""

    def load_settings(self) -> Dict[str, Any]:
        """Load settings.json"""
        settings_path = self.claude_dir / "settings.json"
        if settings_path.exists():
            return json.loads(settings_path.read_text())
        return {}

    def load_mode_config(self) -> Dict[str, Any]:
        """Load mode-config.json"""
        mode_config_path = self.claude_dir / "mode-config.json"
        if mode_config_path.exists():
            return json.loads(mode_config_path.read_text())
        return self.get_default_mode_config()

    def load_local_settings(self, cwd: str) -> Dict[str, Any]:
        """Load .claude/settings.local.json from current directory"""
        local_settings_path = Path(cwd) / ".claude" / "settings.local.json"
        if local_settings_path.exists():
            return json.loads(local_settings_path.read_text())
        return {}

    def get_default_mode_config(self) -> Dict[str, Any]:
        """Default mode configuration"""
        return {
            'work_patterns': [
                '/gits/src/github.com/everlab',
                '/work/',
                '/projects/'
            ],
            'personal_patterns': [
                '/gits/src/github.com/johankaito',
                '/personal/',
                '/side-projects/'
            ],
            'work_emails': [
                '@everlab.com',
                '@everlab.au'
            ],
            'work_hours': {
                'days': [0, 1, 2, 3, 4],  # Monday-Friday
                'start': 9,
                'end': 18
            }
        }

    def load_twin_config(self) -> Dict[str, Any]:
        """Load twin.config.json from twin directory"""
        twin_config_path = self.twin_dir / "twin.config.json"
        if twin_config_path.exists():
            return json.loads(twin_config_path.read_text())
        return self.get_default_twin_config()

    def get_default_twin_config(self) -> Dict[str, Any]:
        """Default twin configuration if file doesn't exist"""
        return {
            'default_model': 'fast',
            'model_aliases': {
                'fast': {'model': 'qwen2.5-coder:7b'}
            }
        }

    def resolve_model_alias(self, model_or_alias: str) -> str:
        """
        Resolve model alias to actual model name.
        If input is already a model name, return as-is.

        Args:
            model_or_alias: Either an alias ('fast', 'balanced') or full model name ('qwen2.5-coder:7b')

        Returns:
            Actual model name to use with ollama
        """
        twin_config = self.config.get('twin_config', {})
        aliases = twin_config.get('model_aliases', {})

        # Check if it's an alias
        if model_or_alias in aliases:
            return aliases[model_or_alias]['model']

        # Not an alias, assume it's a full model name
        return model_or_alias

    def validate_model_exists(self, model_name: str) -> Tuple[bool, List[str]]:
        """
        Check if model exists in ollama list.

        Returns:
            Tuple of (exists: bool, available_models: List[str])
        """
        try:
            result = subprocess.run(
                ['ollama', 'list'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                return False, []

            # Parse ollama list output
            lines = result.stdout.strip().split('\n')
            if len(lines) < 2:  # Header + at least one model
                return False, []

            available_models = []
            for line in lines[1:]:  # Skip header
                if line.strip():
                    # Format: "NAME    ID    SIZE    MODIFIED"
                    model = line.split()[0]
                    available_models.append(model)

            # Check if requested model is in list
            exists = model_name in available_models
            return exists, available_models

        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            return False, []

    def get_model_for_agent(self, agent_name: str, mode: str = 'personal') -> str:
        """
        Get recommended model for specific agent, considering mode.

        Args:
            agent_name: Name of the agent
            mode: 'work' or 'personal'

        Returns:
            Model alias or name
        """
        twin_config = self.config.get('twin_config', {})

        # Check agent-specific preference first
        agent_prefs = twin_config.get('agent_model_preferences', {})
        if agent_name in agent_prefs:
            return agent_prefs[agent_name]

        # Fall back to mode default
        mode_defaults = twin_config.get('mode_defaults', {})
        if mode in mode_defaults:
            return mode_defaults[mode]

        # Ultimate fallback
        return twin_config.get('default_model', 'fast')

    def get_model_info(self, alias: str) -> Optional[Dict[str, Any]]:
        """Get information about a model alias"""
        twin_config = self.config.get('twin_config', {})
        aliases = twin_config.get('model_aliases', {})
        return aliases.get(alias)
