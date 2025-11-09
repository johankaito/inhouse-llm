"""
Context manager for twin
Manages context files in ~/.claude/context/
"""

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List


class ContextManager:
    """Manage context files for session resumption"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.context_dir = Path(config.get('context_dir', Path.home() / ".claude" / "context"))
        self.context_dir.mkdir(parents=True, exist_ok=True)

    def get_context_filename(self, cwd: str) -> str:
        """Generate context filename from cwd hash"""
        hash_obj = hashlib.sha256(cwd.encode())
        hash_str = hash_obj.hexdigest()[:8]
        return f"context-{hash_str}.txt"

    def get_context_path(self, cwd: str) -> Path:
        """Get full path to context file"""
        filename = self.get_context_filename(cwd)
        return self.context_dir / filename

    def load_context(self, cwd: str) -> Optional[Dict[str, Any]]:
        """Load context from file"""
        context_path = self.get_context_path(cwd)

        if not context_path.exists():
            return None

        content = context_path.read_text()

        # Parse context file
        return self.parse_context(content, cwd)

    def parse_context(self, content: str, cwd: str) -> Dict[str, Any]:
        """Parse context file into structured format"""
        # Extract repository path
        repo_match = re.search(r'# Repository: (.+)', content)
        repo_path = repo_match.group(1) if repo_match else cwd

        # Extract sessions
        sessions = []
        session_pattern = r'## (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) - (.*?)\n(.*?)(?=\n## \d{4}|\Z)'

        for match in re.finditer(session_pattern, content, re.DOTALL):
            timestamp = match.group(1)
            header = match.group(2)
            session_content = match.group(3)

            # Parse header for metadata
            session_id_match = re.search(r'Session ([a-f0-9]+)', header)
            commit_match = re.search(r'Commit ([a-f0-9]+)', header)
            branch_match = re.search(r'\(([^)]+)\)', header)
            mode_match = re.search(r'\[(TWIN|CLAUDE)\].*?\[([A-Z\s]+MODE)\]', header)

            sessions.append({
                'timestamp': timestamp,
                'session_id': session_id_match.group(1) if session_id_match else None,
                'commit': commit_match.group(1) if commit_match else None,
                'branch': branch_match.group(1) if branch_match else None,
                'source': mode_match.group(1) if mode_match else 'CLAUDE',
                'mode': mode_match.group(2).replace(' MODE', '').lower() if mode_match else 'personal',
                'content': session_content.strip()
            })

        return {
            'repository': repo_path,
            'sessions': sessions,
            'raw_content': content
        }

    def append_session(self, cwd: str, session_data: Dict[str, Any]) -> None:
        """Append session summary to context file"""
        context_path = self.get_context_path(cwd)

        # Check if this is a new file
        is_new = not context_path.exists()

        # Build session entry
        entry = self._build_session_entry(cwd, session_data, is_new)

        # Append to file
        with context_path.open('a') as f:
            f.write(entry)

    def _build_session_entry(self, cwd: str, session_data: Dict[str, Any], is_new: bool) -> str:
        """Build formatted session entry"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        mode = session_data.get('mode', 'personal').upper()
        agent = session_data.get('agent', 'assistant')
        session_id = session_data.get('session_id', '')

        # Header for new file
        header = ""
        if is_new:
            header = f"# Repository: {cwd}\n\n---\n\n"

        # Session header
        session_header = f"## {timestamp} - Session {session_id} [TWIN] [{mode} MODE]\n\n"

        # Session content sections
        sections = []

        if 'planning_discussion' in session_data:
            sections.append(f"### Planning Discussion\n{session_data['planning_discussion']}\n")

        if 'agent' in session_data:
            sections.append(f"### Agent Active\n{agent}\n")

        if 'decisions' in session_data and session_data['decisions']:
            decisions_text = "\n".join(f"- {d}" for d in session_data['decisions'])
            sections.append(f"### Decisions Made\n{decisions_text}\n")

        if 'reasoning' in session_data and session_data['reasoning']:
            sections.append(f"### 5 Whys Applied\n{session_data['reasoning']}\n")

        if 'next_steps' in session_data and session_data['next_steps']:
            next_steps_text = "\n".join(f"- {s}" for s in session_data['next_steps'])
            sections.append(f"### Next Steps\n{next_steps_text}\n")

        if 'files_discussed' in session_data and session_data['files_discussed']:
            files_text = "\n".join(f"- {f}" for f in session_data['files_discussed'])
            sections.append(f"### Files Discussed\n{files_text}\n")

        content = "\n".join(sections)

        return f"{header}{session_header}{content}\n---\n\n"

    def clear_context(self, cwd: str) -> bool:
        """Delete context file (used when PR merged)"""
        context_path = self.get_context_path(cwd)
        if context_path.exists():
            context_path.unlink()
            return True
        return False

    def get_recent_sessions(self, cwd: str, count: int = 3) -> List[Dict[str, Any]]:
        """Get most recent sessions"""
        context = self.load_context(cwd)
        if not context:
            return []

        sessions = context.get('sessions', [])
        return sessions[-count:] if len(sessions) > count else sessions

    def get_context_summary(self, cwd: str) -> str:
        """Get human-readable context summary"""
        context = self.load_context(cwd)
        if not context:
            return "No previous context found"

        sessions = context.get('sessions', [])
        if not sessions:
            return "Context file exists but no sessions found"

        last_session = sessions[-1]
        session_count = len(sessions)

        # Extract key info from last session
        summary_lines = [
            f"Found {session_count} previous session(s)",
            f"Last session: {last_session['timestamp']}",
            f"Mode: {last_session['mode'].title()}",
            f"Source: {last_session['source']}"
        ]

        # Try to extract a brief description
        content = last_session.get('content', '')
        planning_match = re.search(r'### Planning Discussion\n(.+?)(?=\n###|\Z)', content, re.DOTALL)
        if planning_match:
            planning_text = planning_match.group(1).strip()
            # First line or first 100 chars
            first_line = planning_text.split('\n')[0][:100]
            summary_lines.append(f"Topic: {first_line}")

        return "\n".join(summary_lines)
