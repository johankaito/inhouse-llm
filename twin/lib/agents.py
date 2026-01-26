"""
Agent loader for twin
Loads agent definitions from ~/.claude/agents/
"""

import re
from pathlib import Path
from typing import Dict, List, Any, Optional


class AgentLoader:
    """Load and manage agent definitions"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.agent_dir = Path(config.get('agent_dir', Path.home() / ".claude" / "agents"))
        self.agents = {}

    def load_all(self) -> Dict[str, Dict[str, Any]]:
        """Load all agents from ~/.claude/agents/"""
        if not self.agent_dir.exists():
            return {}

        for agent_path in self.agent_dir.iterdir():
            if agent_path.is_dir():
                agent = self.load_agent(agent_path.name)
                if agent:
                    self.agents[agent_path.name] = agent

        return self.agents

    def load_agent(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Load a specific agent"""
        agent_path = self.agent_dir / agent_name

        if not agent_path.exists():
            return None

        # Load MASTER_AGENT.md for system prompt
        master_path = agent_path / "MASTER_AGENT.md"
        master_prompt = ""
        if master_path.exists():
            master_prompt = master_path.read_text()

        # Load CLAUDE.md for keywords and metadata
        claude_path = agent_path / "CLAUDE.md"
        keywords = []
        mode_info = {}
        if claude_path.exists():
            claude_content = claude_path.read_text()
            keywords = self._extract_keywords(claude_content)
            mode_info = self._extract_mode_info(claude_content)

        return {
            'name': agent_name,
            'master_prompt': master_prompt,
            'keywords': keywords,
            'mode_info': mode_info,
            'path': str(agent_path)
        }

    def get_agent(self, agent_name: str) -> Dict[str, Any]:
        """Get specific agent by name"""
        if agent_name in self.agents:
            return self.agents[agent_name]

        # Try to load it
        agent = self.load_agent(agent_name)
        if agent:
            self.agents[agent_name] = agent
            return agent

        raise ValueError(f"Agent '{agent_name}' not found")

    def get_default_for_mode(self, mode: str) -> Dict[str, Any]:
        """Get default agent for mode"""
        # Priority agents by mode
        if mode == 'work':
            priority = ['technical-lead', 'task-manager', 'decision-framework']
        else:
            priority = ['health-coach', 'decision-framework', 'task-manager', 'technical-lead']

        for agent_name in priority:
            if agent_name in self.agents:
                return self.agents[agent_name]

        # Fallback to first available
        if self.agents:
            return list(self.agents.values())[0]

        # Ultimate fallback - generic agent
        return {
            'name': 'assistant',
            'master_prompt': 'You are a helpful AI assistant for planning and architecture discussions.',
            'keywords': [],
            'mode_info': {}
        }

    def match_agent_by_keywords(self, user_input: str, mode: str) -> Optional[Dict[str, Any]]:
        """Match agent based on keywords in user input"""
        user_input_lower = user_input.lower()
        matches = []

        for agent_name, agent in self.agents.items():
            keywords = agent.get('keywords', [])
            score = sum(1 for keyword in keywords if keyword.lower() in user_input_lower)

            if score > 0:
                matches.append((agent, score))

        if not matches:
            return None

        # Sort by score (highest first)
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[0][0]

    def select_agent_with_reason(self, user_input: str, mode: str, current_agent: Dict[str, Any]) -> Dict[str, Any]:
        """Heuristic agent selection with reasons"""
        text = user_input.lower()

        domain_keywords = {
            'health-coach': {'health', 'meal', 'nutrition', 'diet', 'calorie', 'macro', 'workout', 'exercise', 'recipe'},
            'travel-agent': {'travel', 'trip', 'flight', 'hotel', 'itinerary', 'visa'},
            'technical-lead': {'code', 'bug', 'deploy', 'pr', 'refactor', 'build', 'tests', 'api', 'repo'},
            'communication-handler': {'email', 'respond', 'reply', 'draft', 'message'},
        }

        best_agent = current_agent
        best_reason = f"default for mode {mode}"
        best_score = 0

        for agent_name, keywords in domain_keywords.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > best_score and agent_name in self.agents:
                best_score = score
                best_agent = self.agents[agent_name]
                matched = sorted({kw for kw in keywords if kw in text})
                best_reason = f"matched keywords: {', '.join(matched)}" if matched else f"domain: {agent_name}"

        if best_score == 0:
            keyword_match = self.match_agent_by_keywords(user_input, mode)
            if keyword_match:
                best_agent = keyword_match
                best_reason = "matched agent keywords"

        return {
            "agent": best_agent,
            "reason": best_reason
        }

    def _extract_keywords(self, content: str) -> List[str]:
        """Extract activation keywords from CLAUDE.md"""
        keywords = []

        # Look for keywords section
        keywords_section = re.search(r'##?\s*Keywords?.*?\n(.*?)(?=\n##|\Z)', content, re.DOTALL | re.IGNORECASE)
        if keywords_section:
            keywords_text = keywords_section.group(1)
            # Extract quoted keywords or bulleted keywords
            keywords.extend(re.findall(r'"([^"]+)"', keywords_text))
            keywords.extend(re.findall(r'[•\-\*]\s*`([^`]+)`', keywords_text))
            keywords.extend(re.findall(r'[•\-\*]\s*([^\n]+)', keywords_text))

        # Look for activation keywords section
        activation_section = re.search(r'##?\s*Activation.*?\n(.*?)(?=\n##|\Z)', content, re.DOTALL | re.IGNORECASE)
        if activation_section:
            activation_text = activation_section.group(1)
            keywords.extend(re.findall(r'"([^"]+)"', activation_text))
            keywords.extend(re.findall(r'`([^`]+)`', activation_text))

        # Clean keywords
        keywords = [k.strip().strip('`"\'') for k in keywords if k.strip()]

        return keywords

    def _extract_mode_info(self, content: str) -> Dict[str, Any]:
        """Extract mode-specific information"""
        mode_info = {
            'work_priority': False,
            'personal_priority': False
        }

        if re.search(r'work mode.*?primary', content, re.IGNORECASE):
            mode_info['work_priority'] = True
        if re.search(r'personal mode.*?primary', content, re.IGNORECASE):
            mode_info['personal_priority'] = True

        return mode_info
