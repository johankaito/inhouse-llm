"""
Configuration loader for twin
Reads ~/.claude/ configuration files
"""

import json
import yaml
from pathlib import Path
from typing import Dict, Any


class ConfigLoader:
    """Load configuration from ~/.claude/"""

    def __init__(self):
        self.claude_dir = Path.home() / ".claude"
        self.config = {}

    def load_all(self) -> Dict[str, Any]:
        """Load all configuration files"""
        self.config = {
            'claude_md': self.load_claude_md(),
            'settings': self.load_settings(),
            'mode_config': self.load_mode_config(),
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
