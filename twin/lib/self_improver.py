"""
Self-improvement system for twin
Enables twin to autonomously improve its own code with full git tracking
"""

import os
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List


class SelfImprover:
    """Manages twin's self-improvement capabilities"""

    def __init__(self, twin_dir: Path):
        self.twin_dir = twin_dir
        self.improvements_log = twin_dir / "IMPROVEMENTS.md"
        self.ensure_improvements_log()

    def ensure_improvements_log(self):
        """Create improvements log if doesn't exist"""
        if not self.improvements_log.exists():
            self.improvements_log.write_text("""# Twin Self-Improvements Log

This file tracks all autonomous improvements made by twin to itself.

Each improvement includes:
- Timestamp
- Description
- Reasoning (5 Whys analysis)
- Files changed
- Git commit hash

---

""")

    def can_improve(self) -> bool:
        """Check if twin can make improvements"""
        try:
            # Check if in git repo
            result = subprocess.run(
                ['git', 'rev-parse', '--git-dir'],
                cwd=self.twin_dir,
                capture_output=True
            )
            if result.returncode != 0:
                return False

            # Check for uncommitted changes
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=self.twin_dir,
                capture_output=True,
                text=True
            )

            # Allow improvement if no changes or only IMPROVEMENTS.md changed
            changes = result.stdout.strip()
            if not changes:
                return True

            lines = changes.split('\n')
            return all('IMPROVEMENTS.md' in line for line in lines)

        except:
            return False

    def propose_improvement(
        self,
        description: str,
        reasoning: str,
        files: Dict[str, str]
    ) -> str:
        """Propose and apply an improvement"""

        if not self.can_improve():
            raise Exception("Cannot improve: Repository has uncommitted changes or not in git")

        timestamp = datetime.now().isoformat()
        improvement_id = datetime.now().strftime("%Y%m%d-%H%M%S")

        # Apply file changes
        for file_path, new_content in files.items():
            full_path = self.twin_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(new_content)

        # Log improvement
        self._log_improvement(improvement_id, timestamp, description, reasoning, list(files.keys()))

        # Git commit
        commit_hash = self._commit_improvement(improvement_id, description, list(files.keys()))

        return f"Improvement {improvement_id} applied and committed as {commit_hash[:7]}"

    def _log_improvement(
        self,
        improvement_id: str,
        timestamp: str,
        description: str,
        reasoning: str,
        files_changed: List[str]
    ):
        """Append improvement to log"""
        entry = f"""
## {improvement_id} - {description}

**Timestamp:** {timestamp}

**Reasoning (5 Whys):**
{reasoning}

**Files Changed:**
{chr(10).join(f'- {f}' for f in files_changed)}

**Status:** ✅ Applied

---

"""

        with self.improvements_log.open('a') as f:
            f.write(entry)

    def _commit_improvement(
        self,
        improvement_id: str,
        description: str,
        files_changed: List[str]
    ) -> str:
        """Commit improvement to git"""

        # Add changed files
        subprocess.run(
            ['git', 'add'] + files_changed + ['IMPROVEMENTS.md'],
            cwd=self.twin_dir,
            check=True
        )

        # Commit
        commit_message = f"""[SELF-IMPROVEMENT] {description}

Improvement ID: {improvement_id}
Autonomous improvement by twin

Files changed:
{chr(10).join(f'- {f}' for f in files_changed)}

See IMPROVEMENTS.md for full reasoning."""

        subprocess.run(
            ['git', 'commit', '-m', commit_message],
            cwd=self.twin_dir,
            check=True
        )

        # Get commit hash
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=self.twin_dir,
            capture_output=True,
            text=True,
            check=True
        )

        return result.stdout.strip()

    def get_recent_improvements(self, count: int = 5) -> str:
        """Get recent improvements summary"""
        if not self.improvements_log.exists():
            return "No improvements yet"

        content = self.improvements_log.read_text()
        entries = content.split('## ')[1:]  # Skip header

        recent = entries[-count:] if len(entries) > count else entries

        summaries = []
        for entry in reversed(recent):
            lines = entry.split('\n')
            title = lines[0] if lines else "Unknown"
            summaries.append(f"- {title}")

        return "\n".join(summaries) if summaries else "No improvements yet"
