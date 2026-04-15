#!/usr/bin/env python3
"""Tests for twin/lib/agents.py"""

import tempfile
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from agents import AgentLoader


@pytest.fixture
def agent_dir(tmp_path):
    """Create a temporary agent directory with sample agents."""
    # technical-lead agent
    tl = tmp_path / "technical-lead"
    tl.mkdir()
    (tl / "MASTER_AGENT.md").write_text("You are a technical lead.")
    (tl / "CLAUDE.md").write_text(
        '## Keywords\n- `code`\n- `deploy`\n- `api`\n\n## Activation\n"refactor"\n'
    )

    # health-coach agent
    hc = tmp_path / "health-coach"
    hc.mkdir()
    (hc / "MASTER_AGENT.md").write_text("You are a health coach.")
    (hc / "CLAUDE.md").write_text(
        '## Keywords\n- `health`\n- `meal`\n- `nutrition`\n'
    )

    return tmp_path


@pytest.fixture
def loader(agent_dir):
    al = AgentLoader({"agent_dir": str(agent_dir)})
    al.load_all()
    return al


class TestLoadAgent:
    def test_loads_agents(self, loader):
        assert "technical-lead" in loader.agents
        assert "health-coach" in loader.agents

    def test_master_prompt(self, loader):
        assert "technical lead" in loader.agents["technical-lead"]["master_prompt"]

    def test_keywords_extracted(self, loader):
        kw = loader.agents["technical-lead"]["keywords"]
        assert "code" in kw
        assert "deploy" in kw

    def test_load_nonexistent(self, loader):
        assert loader.load_agent("nonexistent") is None

    def test_get_agent_raises(self, loader):
        with pytest.raises(ValueError):
            loader.get_agent("nonexistent")


class TestKeywordMatching:
    def test_match_technical(self, loader):
        agent = loader.match_agent_by_keywords("help me deploy the api", "work")
        assert agent is not None
        assert agent["name"] == "technical-lead"

    def test_match_health(self, loader):
        agent = loader.match_agent_by_keywords("plan my meals and nutrition", "personal")
        assert agent is not None
        assert agent["name"] == "health-coach"

    def test_no_match(self, loader):
        agent = loader.match_agent_by_keywords("tell me about quantum physics", "work")
        assert agent is None


class TestSelectAgentWithReason:
    def test_selects_technical(self, loader):
        current = loader.agents["health-coach"]
        result = loader.select_agent_with_reason("fix the bug in our api code", "work", current)
        assert result["agent"]["name"] == "technical-lead"
        assert "matched keywords" in result["reason"]

    def test_selects_health(self, loader):
        current = loader.agents["technical-lead"]
        result = loader.select_agent_with_reason("plan my meal for health", "personal", current)
        assert result["agent"]["name"] == "health-coach"

    def test_keeps_current_on_no_match(self, loader):
        current = loader.agents["technical-lead"]
        result = loader.select_agent_with_reason("something unrelated entirely", "work", current)
        # Should fall back — either current or keyword match
        assert result["agent"] is not None


class TestDefaultForMode:
    def test_work_default(self, loader):
        agent = loader.get_default_for_mode("work")
        assert agent["name"] == "technical-lead"

    def test_personal_default(self, loader):
        agent = loader.get_default_for_mode("personal")
        assert agent["name"] == "health-coach"

    def test_fallback_when_empty(self):
        al = AgentLoader({"agent_dir": "/nonexistent"})
        agent = al.get_default_for_mode("work")
        assert agent["name"] == "assistant"  # ultimate fallback
