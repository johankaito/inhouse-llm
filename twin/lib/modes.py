"""
Mode detection for twin
Implements priority ladder: manual > repo lock > directory > git > time > default
"""

import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


class ModeDetector:
    """Detect work vs personal mode"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.mode_config = config.get('mode_config', {})

    def detect(self, cwd: str) -> str:
        """
        Detect mode using priority ladder
        Returns: 'work' or 'personal'
        """
        # 1. Check per-repo lock (.claude/settings.local.json)
        local_settings = self._load_local_settings(cwd)
        if 'mode' in local_settings:
            return local_settings['mode']

        # 2. Directory pattern match
        mode = self._check_directory_patterns(cwd)
        if mode:
            return mode

        # 3. Git config email
        mode = self._check_git_email(cwd)
        if mode:
            return mode

        # 4. Time-based (work hours)
        if self._is_work_hours():
            return 'work'

        # 5. Default to personal (safer)
        return 'personal'

    def _load_local_settings(self, cwd: str) -> Dict[str, Any]:
        """Load .claude/settings.local.json"""
        local_path = Path(cwd) / ".claude" / "settings.local.json"
        if local_path.exists():
            import json
            return json.loads(local_path.read_text())
        return {}

    def _check_directory_patterns(self, cwd: str) -> Optional[str]:
        """Check if cwd matches work or personal patterns"""
        work_patterns = self.mode_config.get('work_patterns', [])
        personal_patterns = self.mode_config.get('personal_patterns', [])

        for pattern in work_patterns:
            if pattern in cwd:
                return 'work'

        for pattern in personal_patterns:
            if pattern in cwd:
                return 'personal'

        return None

    def _check_git_email(self, cwd: str) -> Optional[str]:
        """Check git email to determine mode"""
        try:
            result = subprocess.run(
                ['git', 'config', 'user.email'],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                email = result.stdout.strip()
                work_emails = self.mode_config.get('work_emails', [])
                for work_email_pattern in work_emails:
                    if work_email_pattern in email:
                        return 'work'
                return 'personal'
        except:
            pass
        return None

    def _is_work_hours(self) -> bool:
        """Check if current time is work hours"""
        work_hours = self.mode_config.get('work_hours', {})
        now = datetime.now()

        work_days = work_hours.get('days', [0, 1, 2, 3, 4])  # Mon-Fri
        if now.weekday() not in work_days:
            return False

        start_hour = work_hours.get('start', 9)
        end_hour = work_hours.get('end', 18)

        return start_hour <= now.hour < end_hour
